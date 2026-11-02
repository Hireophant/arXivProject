"""Typed m2-working-1.0 wire format and immutable publication writes (Danh / DA3).

Writes a sibling staging directory, fsyncs, hydrates/validates and compares it before a
single rename into a new destination. An identical rerun is idempotent; changed data
requires a fresh run destination rather than a non-atomic overwrite of a nonempty folder.
Runtime tuple/int maps and nullable bibliography fields retain their declared types.
"""
from __future__ import annotations

import json
import os
import shutil
import types
import uuid
from dataclasses import asdict, fields, is_dataclass, replace
from typing import Literal, Union, get_args, get_origin
from pathlib import Path
from .contracts import IdentityDecision, ParsedPublication
from . import contracts as c
from .validation import _hints, _type_errors, finalize_publication, validate_publication

_JSON_OPTIONS = dict(ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',', ':'))
_JSONL = {'elements':c.ElementRow,'hierarchy':c.HierarchyRow,'bibtex':c.BibEntry,
          'occurrences':c.ElementOccurrence,'bib_occurrences':c.BibOccurrence,'diagnostics':c.Diagnostic}
_JSON_LISTS = {'identity_decisions':c.IdentityDecision,'conflicts':c.FieldConflict}


def _canonical(value: object) -> str:
    return json.dumps(value, **_JSON_OPTIONS)


def _write_json(path: Path, value: object) -> None:
    with path.open('w',encoding='utf-8',newline='\n') as stream:
        stream.write(_canonical(value)+'\n'); stream.flush(); os.fsync(stream.fileno())


def _pairs(pairs: list[tuple[str,object]]) -> dict:
    result = {}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate JSON key '+key)
        result[key] = value
    return result


def _loads(text: str) -> object:
    def reject(value: str) -> None:
        raise ValueError('Non-finite JSON value '+value)
    return json.loads(text,object_pairs_hook=_pairs,parse_constant=reject)


def _hydrate(kind: object, value: object) -> object:
    origin, args = get_origin(kind), get_args(kind)
    if origin in (Union,types.UnionType):
        for candidate in args:
            try: return _hydrate(candidate,value)
            except (ValueError,TypeError): pass
        raise ValueError('Invalid union value')
    if origin is Literal:
        if _type_errors(value,kind): raise ValueError('Unknown enum value')
        return value
    if origin is list:
        if type(value) is not list: raise ValueError('Expected JSON list')
        return [_hydrate(args[0],item) for item in value]
    if origin is dict:
        if type(value) is not dict: raise ValueError('Expected JSON map')
        result = {}
        for key,item in value.items():
            if args[0] is int:
                if not isinstance(key,str) or not key.isdecimal() or str(int(key)) != key: raise ValueError('Invalid integer JSON key')
                key = int(key)
            else: key = _hydrate(args[0],key)
            result[key] = _hydrate(args[1],item)
        return result
    if isinstance(kind,type) and is_dataclass(kind):
        if type(value) is not dict or set(value) != {f.name for f in fields(kind)}: raise ValueError('Unexpected record columns: '+kind.__name__)
        return kind(**{name:_hydrate(t,value[name]) for name,t in _hints(kind).items()})
    if type(value) is not kind: raise ValueError('Invalid scalar type')
    return value


def _check_storage(publication: ParsedPublication) -> None:
    # Re-evaluate invariants even if an old diagnostic with the same text was supplied.
    problems = validate_publication(replace(publication,diagnostics=[]))
    structural = [d for d in problems if d.code in ('INVALID_SCHEMA','INVALID_STRUCTURE')]
    if structural: raise ValueError('Invalid publication for storage: '+'; '.join(d.message for d in structural))
    final = finalize_publication(publication)
    if publication.export_ready != final.export_ready or publication.version_states != final.version_states:
        raise ValueError('Finalize publication before storage')


def _owned_destination(destination: Path) -> Path:
    destination = Path(destination).absolute()
    if any(p.is_symlink() for p in (destination,*destination.parents)): raise ValueError('Symlink destination is not owned')
    if 'preparationM2' in destination.parts or 'raw_m1' in destination.parts: raise ValueError('Cannot write prepared raw input')
    destination = destination.resolve()
    if any((p/'preparation.json').is_file() and (p/'manifest.json').is_file() for p in (destination,*destination.parents)):
        raise ValueError('Cannot write inside a prepared raw snapshot')
    return destination


def write_publication(publication: ParsedPublication, destination: Path) -> list[Path]:
    """Ghi working format mô tả trực tiếp bên dưới bằng staging sibling + atomic publish.
    Elements/hierarchy/bibtex JSONL chỉ đúng cột TABLE_COLUMNS; Path/tuple keys không lọt vào JSON.
    Sidecars: publication.json, occurrences.jsonl, bib_occurrences.jsonl, citation_key_map.json,
    identity_decisions.json, conflicts.json, diagnostics.jsonl. Kèm contract/output schema + counts/root/status.
    Working partial hợp lệ được ghi; rows schema hỏng không được ghi. strict publish do pipeline quyết định.
    Không ghi raw source vào output tables; giữ spans/fingerprint. Không ghi vào preparationM2.
    Ghi lỗi không thay output tốt trước; chỉ replace sau đọc lại kiểm round-trip; destination phải owned.
    Test ngắt giữa write, duplicate rerun, read-back equality, Unicode/null/authors list.

    Định dạng cụ thể trong destination (đúng folder một publication, không tự thêm run):
    publication.json = asdict(PublicationRecord), các tables mỗi row asdict đúng TABLE_COLUMNS.
    occurrences.jsonl = ElementOccurrence; bib_occurrences.jsonl = BibOccurrence; diagnostics.jsonl = Diagnostic.
    identity_decisions.json/conflicts.json = lists typed objects. citation_key_map.json =
    {schema_version:'m2-working-1.0', arxiv_id, rows:[{version:1,old_key:'x',canonical_key:'y'}]}.
    Rows key-map sort (version,old_key); tuyệt đối không JSON stringify tuple làm key.
    JSON UTF-8 ensure_ascii=False/sort_keys=True/allow_nan=False; JSONL file rỗng hợp lệ.
    publication.json state/root keys ghi string số, đọc về int; None null, authors list không stringify.
    M3 chuyển kind/entry_type dictionary-encoded Parquet, authors list<string>, year nullable int;
    không bắt owner cài pyarrow lúc prototype. Không thêm field ngoài bảng đề.
    Kiểm tay mở JSON của một bài hai versions, so authors/year null/key-map/root/status rồi đọc lại.
    """
    _check_storage(publication)
    destination = _owned_destination(destination)
    # Publication artifacts are immutable: a changed result needs a fresh run destination.
    # This avoids a non-atomic two-directory overwrite on Windows and preserves prior good data.
    if destination.exists():
        if read_publication(destination) != publication: raise FileExistsError('Use a fresh run destination for changed output')
        return sorted(p for p in destination.iterdir() if p.is_file())
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging = destination.with_name('.'+destination.name+'.staging-'+uuid.uuid4().hex)
    staging.mkdir()
    try:
        record = c.PublicationRecord(arxiv_id=publication.arxiv_id,version_states=publication.version_states,
            root_ids=publication.root_ids,counts_before_after=publication.counts_before_after,export_ready=publication.export_ready)
        _write_json(staging/'publication.json',asdict(record))
        for name in _JSONL:
            with (staging/(name+'.jsonl')).open('w',encoding='utf-8',newline='\n') as stream:
                for row in getattr(publication,name): stream.write(_canonical(asdict(row))+'\n')
                stream.flush(); os.fsync(stream.fileno())
        for name in _JSON_LISTS: _write_json(staging/(name+'.json'),[asdict(row) for row in getattr(publication,name)])
        _write_json(staging/'citation_key_map.json',{'schema_version':c.OUTPUT_SCHEMA_VERSION,'arxiv_id':publication.arxiv_id,
            'rows':[{'version':v,'old_key':key,'canonical_key':canonical} for (v,key),canonical in sorted(publication.key_map.items())]})
        if read_publication(staging) != publication: raise ValueError('Publication round-trip mismatch')
        staging.rename(destination)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return sorted(p for p in destination.iterdir() if p.is_file())


def read_publication(destination: Path) -> ParsedPublication:
    """Đọc đúng schema m2-working-1.0, hydrate nested dataclasses; không trả dict tùy ý.
    Đọc citation_key_map list rows về tuple keys, version_states/root_ids keys về int.
    Đối chiếu publication identity các file, không parse lại TeX. Contract/schema unknown -> ValueError.
    Caller kiểm input/config/code cache signature ngoài publication record trước khi dùng cache.
    """
    destination = Path(destination)
    def read(name: str) -> object:
        path = destination/name
        if path.is_symlink(): raise ValueError('Symlink artifact')
        return _loads(path.read_text(encoding='utf-8'))
    record = _hydrate(c.PublicationRecord,read('publication.json'))
    if record.schema_version != c.OUTPUT_SCHEMA_VERSION or record.contract_version != c.CONTRACT_VERSION:
        raise ValueError('Unknown working schema/contract')
    data = {}
    for name,kind in _JSONL.items():
        path = destination/(name+'.jsonl')
        if path.is_symlink(): raise ValueError('Symlink artifact')
        with path.open(encoding='utf-8') as stream:
            data[name] = [_hydrate(kind,_loads(line)) for line in stream if line.strip()]
    for name,kind in _JSON_LISTS.items(): data[name] = _hydrate(list[kind],read(name+'.json'))
    mapping = read('citation_key_map.json')
    if not isinstance(mapping,dict) or set(mapping) != {'schema_version','arxiv_id','rows'} or mapping['schema_version'] != c.OUTPUT_SCHEMA_VERSION or mapping['arxiv_id'] != record.arxiv_id:
        raise ValueError('Invalid citation map envelope')
    if not isinstance(mapping['rows'],list): raise ValueError('Invalid citation map rows')
    key_map = {}
    for row in mapping['rows']:
        if not isinstance(row,dict) or set(row) != {'version','old_key','canonical_key'} or type(row['version']) is not int or type(row['old_key']) is not str or type(row['canonical_key']) is not str:
            raise ValueError('Invalid citation map row')
        key = (row['version'],row['old_key'])
        if key in key_map: raise ValueError('Duplicate citation key map row')
        key_map[key] = row['canonical_key']
    result = ParsedPublication(arxiv_id=record.arxiv_id,version_states=record.version_states,root_ids=record.root_ids,
        counts_before_after=record.counts_before_after,export_ready=record.export_ready,key_map=key_map,**data)
    _check_storage(result)
    return result


def read_review_decisions(path: Path | None, *, snapshot_id: str) -> list[IdentityDecision]:
    """None -> []; file có schema m2-reference-review-1.0 và snapshot_id phải khớp run.
    Đọc decisions thành typed objects; reviewer/evidence bắt buộc cho quyết định người.
    Outcome pending không được dùng như approved; malformed/duplicate decision IDs -> ValueError.
    Source fingerprint/occurrence matching còn được Nguyên kiểm khi unify; không chấp nhận review stale.
    Hash bytes file review phải tham gia cache key trong pipeline, kể cả khi path đổi mà nội dung giống.

    Envelope đúng ReviewFile; từng IdentityDecision.input_snapshot_id trùng envelope cho review người.
    Chưa có reviewers thật không bịa tên/xác nhận; quyết định auto giữ reviewer=None.
    """
    if path is None: return []
    review = _hydrate(c.ReviewFile,_loads(Path(path).read_text(encoding='utf-8')))
    if review.schema_version != 'm2-reference-review-1.0' or review.snapshot_id != snapshot_id: raise ValueError('Stale/unknown review file')
    ids = set()
    for decision in review.decisions:
        if not decision.decision_id or decision.decision_id in ids: raise ValueError('Duplicate/empty decision ID')
        ids.add(decision.decision_id)
        if not decision.reviewer or not decision.reviewer.strip() or not decision.evidence.strip() or decision.input_snapshot_id != snapshot_id:
            raise ValueError('Human review requires reviewer, evidence and matching snapshot')
        if not decision.occurrence_ids or len(set(decision.occurrence_ids)) != len(decision.occurrence_ids) or set(decision.source_fingerprints) != set(decision.occurrence_ids):
            raise ValueError('Review occurrence/fingerprint coverage mismatch')
        if any(not value for value in decision.source_fingerprints.values()): raise ValueError('Empty review fingerprint')
    return review.decisions

