"""Reproduce KG4 from explicit, hand-inspected real-source fixture fragments.

This is a review harness, not an input adapter or gather implementation. A JSON
spec names every file/range in compilation order; no root selection, traversal
or automatic include expansion is performed. All outputs stay outside Git.

Run from the repository root:
python -X utf8 -B -m tests.khang_review --spec <json> --output <data/review>
Alternatively execute this file directly; the checkout root is added to sys.path.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time
import subprocess

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parsing.contracts import Diagnostic, GatherResult, SourceFile, SourceSpan, VersionInput
from src.parsing.hierarchy import parse_version
from src.parsing.khang_lex import scan
from src.preparation import validate_prepared_corpus


def _read(path: Path) -> tuple[str, str, str]:
    data = path.read_bytes()
    try:
        text, encoding = data.decode('utf-8-sig'), 'utf-8-sig'
    except UnicodeDecodeError:
        text, encoding = data.decode('latin-1'), 'latin-1'
    return text, encoding, hashlib.sha256(data).hexdigest()


def run(spec_path: Path, output: Path) -> dict:
    """Validate signed raw datasets, then parse explicitly specified fixture spans."""
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for name, dataset in spec['datasets'].items():
        root = Path(dataset['root']).resolve()
        print('Validating raw dataset '+name,flush=True)
        check = validate_prepared_corpus(root)
        if not check['valid'] or check['snapshot_id'] != dataset['snapshot_id']:
            raise ValueError(f'Invalid/stale raw dataset: {name}')
        with (root/'inventory.csv').open(encoding='utf-8', newline='') as stream:
            inventory = {(r['arxiv_id'], int(r['version'])):r for r in csv.DictReader(stream)}
        datasets[name] = root, check, inventory
    counts, status_counts, rows = Counter(), Counter(), []
    for case_index,case in enumerate(spec['cases']):
        root, check, inventory = datasets[case['dataset']]
        row = inventory[case['arxiv_id'],case['version']]
        source_status={'ready_tex':'tex','empty_no_tex':'no_tex','blocked_input':'blocked'}[row['status']]
        source_dir = root/row['source_dir'] if row['source_dir'] else None
        receipt=(json.loads((source_dir.parent/f".v{case['version']}.receipt.json").read_text(encoding='utf-8'))
                 if source_dir is not None else None)
        cache, files, spans, fragments = {}, [], [], []
        offset = 0
        for part in case['parts']:
            if 'separator' in part:
                if part['separator'].strip():
                    raise ValueError('Synthetic separators must contain only whitespace')
                fragments.append(part['separator']); offset += len(part['separator'])
                continue
            rel = part['path']
            path = (source_dir/rel).resolve()
            if not path.is_relative_to(source_dir.resolve()) or path.is_symlink():
                raise ValueError('Fixture path escapes version source')
            if rel not in cache:
                text, encoding, sha256 = _read(path)
                if receipt['files_sha256'].get(rel)!=sha256:
                    raise ValueError('Source bytes changed after raw validation')
                cache[rel] = text
                files.append(SourceFile(path=rel, encoding=encoding, sha256=sha256))
            text = cache[rel]
            start,end = part.get('start',0),part.get('end',len(text))
            if not 0 <= start <= end <= len(text):
                raise ValueError('Fixture range outside source')
            fragment = text[start:end]
            fragments.append(fragment)
            spans.append(SourceSpan(path=rel,start=start,end=end,flat_start=offset,flat_end=offset+len(fragment)))
            offset += len(fragment)
        diagnostics=([Diagnostic(code='SOURCE_MISSING',severity='error',arxiv_id=case['arxiv_id'],
                     version=case['version'],message=row['reason']+'; '+row['m1_error'])] if source_status=='blocked' else [])
        g = GatherResult(version_input=VersionInput(arxiv_id=case['arxiv_id'],version=case['version'],
            source_dir=source_dir,source_status=source_status,source_fingerprint=row['source_fingerprint'] or None,
            diagnostics=diagnostics),
            root_path=case['root_path'],latex=''.join(fragments),source_map=spans,
            source_files=files,bib_paths=[],status={'tex':'ready','no_tex':'empty_no_tex','blocked':'blocked_input'}[source_status])
        started = time.perf_counter()
        tree = parse_version(g)
        elapsed = time.perf_counter()-started
        index = {n.local_id:n for n in tree.nodes}
        siblings = Counter()
        for node in tree.nodes:
            if node.parent_local_id is not None and node.parent_local_id not in index:
                raise AssertionError('Orphan node in real fixture')
            expected = siblings[node.parent_local_id]
            if node.position != expected:
                raise AssertionError('Non-contiguous sibling positions')
            siblings[node.parent_local_id] += 1
            for span in node.source_spans:
                if cache[span.path][span.start:span.end] != g.latex[span.flat_start:span.flat_end]:
                    raise AssertionError('Incorrect real source span')
        for block in tree.bibliography_blocks:
            for span in block.source_spans:
                if cache[span.path][span.start:span.end] != g.latex[span.flat_start:span.flat_end]:
                    raise AssertionError('Incorrect bibliography source span')
        stem = f"{case['arxiv_id'].replace('.','-').replace('/','-')}-v{case['version']}"
        target=output/stem
        target.mkdir(exist_ok=True)
        (target/'tree.json').write_text(json.dumps(asdict(tree),ensure_ascii=False,indent=2),encoding='utf-8')
        (target/'gathered_fixture.tex').write_bytes(g.latex.encode('utf-8'))
        (target/'source_map.json').write_text(json.dumps([asdict(s) for s in spans],indent=2),encoding='utf-8')
        # Human-readable outline and exact sentence/source locations for Khang/reviewers.
        depth={}
        outline=[]
        for node in tree.nodes:
            depth[node.local_id]=0 if node.parent_local_id is None else depth[node.parent_local_id]+1
            preview=node.content.replace('\r','').replace('\n',' ')[:140]
            outline.append('  '*depth[node.local_id]+f'{node.local_id} [{node.kind}] {preview}')
        (target/'outline.txt').write_text('\n'.join(outline),encoding='utf-8')
        kinds=Counter(n.kind for n in tree.nodes)
        counts.update(kinds); status_counts[tree.status]+=1
        rows.append(dict(arxiv_id=tree.arxiv_id,version=tree.version,dataset=case['dataset'],
            snapshot_id=check['snapshot_id'],status=tree.status,wall_seconds=elapsed,
            counts=dict(kinds),diagnostics=[asdict(d) for d in tree.diagnostics],
            fixture_kind='explicit source fragments; not production gathering',
            human_review='pending',output=str(target)))
        if (case_index+1)%100==0:
            print('Reviewed '+str(case_index+1)+' version fixtures',flush=True)
    repo=Path(__file__).resolve().parents[1]
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,check=True,
                            capture_output=True,text=True).stdout.strip()
    code_hashes={str(p.relative_to(repo)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (repo/'src/parsing/hierarchy.py',repo/'src/parsing/sentences.py',
                           repo/'src/parsing/khang_lex.py',repo/'src/parsing/khang_macros.py',Path(__file__).resolve())}
    result=dict(scope='KG hierarchy-only real-source fixtures; not full M2 or Colab benchmark',
        base_git_revision=revision,code_sha256=code_hashes,
        spec_sha256=hashlib.sha256(spec_path.read_bytes()).hexdigest(),python=sys.version,
        fixtures=len(rows),publications=len({r['arxiv_id'] for r in rows}),
        node_counts=dict(counts),provisional_status_counts=dict(status_counts),
        datasets={name:check for name,(_,check,_) in datasets.items()},cases=rows)
    (output/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def shard_spec(raw_parent: Path, overrides: Path | None = None) -> tuple[dict,list[dict]]:
    """Enumerate a whole shard's *review coverage*, selecting only unambiguous fixtures.

    Exactly one TeX file with documentclass and no active includes is an eligible
    self-contained fixture. Multiple files/includes are deferred, never flattened
    here. An override may supply previously hand-inspected fragment fixtures.
    Empty/blocked input versions are tested too, with their original evidence.
    """
    explicit={}
    if overrides:
        for case in json.loads(overrides.read_text(encoding='utf-8'))['cases']:
            explicit[case['dataset'],case['arxiv_id'],case['version']]=case
    spec={'purpose':'Whole Khang shard review coverage; no production gathering', 'datasets':{},'cases':[]}
    coverage=[]
    for name in ('Khang','Khang1','Khang2'):
        root=(raw_parent/name).resolve()
        signed=json.loads((root/'input_validation.json').read_text(encoding='utf-8'))
        spec['datasets'][name]={'root':str(root),'snapshot_id':signed['snapshot_id']}
        with (root/'inventory.csv').open(encoding='utf-8',newline='') as stream:
            for row in csv.DictReader(stream):
                key=name,row['arxiv_id'],int(row['version'])
                record=dict(dataset=name,arxiv_id=key[1],version=key[2],source_status=row['status'],
                            hierarchy_attempted=False,hierarchy_status=None,reason='',snapshot_id=signed['snapshot_id'])
                if row['status']!='ready_tex':
                    case=dict(dataset=name,arxiv_id=key[1],version=key[2],root_path=None,parts=[])
                elif key in explicit:
                    case=explicit[key]
                else:
                    source=root/row['source_dir']
                    receipt=json.loads((source.parent/f'.v{key[2]}.receipt.json').read_text(encoding='utf-8'))
                    tex=[p for p in receipt['files_sha256'] if p.lower().endswith('.tex')]
                    case=None
                    if len(tex)!=1:
                        record['reason']='NEEDS_GATHER: multiple TeX files; no root guessing in review harness'
                    else:
                        text,_,_=_read(source/tex[0]);tokens=list(scan(text))
                        if any(t.kind=='command' and t.name in ('input','include') for t in tokens):
                            record['reason']='NEEDS_GATHER: active input/include'
                        elif not any(t.kind=='command' and t.name=='documentclass' for t in tokens):
                            record['reason']='NEEDS_GATHER: no active documentclass in the unique TeX file'
                        else:
                            case=dict(dataset=name,arxiv_id=key[1],version=key[2],root_path=tex[0],parts=[{'path':tex[0]}])
                if case is not None:
                    spec['cases'].append(case);record['hierarchy_attempted']=True
                coverage.append(record)
    return spec,coverage


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--spec',type=Path)
    inputs.add_argument('--shard-parent',type=Path)
    parser.add_argument('--overrides',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    coverage=None
    if args.shard_parent:
        spec,coverage=shard_spec(args.shard_parent,args.overrides)
        args.output.mkdir(parents=True,exist_ok=True)
        args.spec=args.output/'source_spec.json'
        args.spec.write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Shard inventory: '+str(len(coverage))+' versions; '+str(len(spec['cases']))+' eligible fixtures',flush=True)
    result=run(args.spec,args.output)
    if coverage is not None:
        index={(r['dataset'],r['arxiv_id'],r['version']):r for r in result['cases']}
        for row in coverage:
            parsed=index.get((row['dataset'],row['arxiv_id'],row['version']))
            if parsed: row['hierarchy_status']=parsed['status']
        with (args.output/'shard_coverage.csv').open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(coverage[0]));writer.writeheader();writer.writerows(coverage)
        result['shard_coverage']=dict(publications=len({r['arxiv_id'] for r in coverage}),
            versions_expected=len(coverage),versions_reviewed=len(index),
            versions_needing_gather=sum(not r['hierarchy_attempted'] for r in coverage))
        (args.output/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False))


if __name__=='__main__':
    main()
