"""Bounded background Drive backups of immutable, processed-paper snapshots.

The main thread freezes only completed tasks and their required OAI cache.
One worker compresses/uploads/verifies/acknowledges while collection continues.
At most two snapshots are in flight. Call close before ending measurement.
Stdlib concurrent.futures/threading/ZIP/filesystem APIs; citations and tradeoffs
are documented in KE_HOACH_MILESTONE_1.md section 13.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sys
from uuid import uuid4

from .backup import backup_run, _inventory
from .discover import OaiClient, METADATA_SOURCE
from .download import _cached as cached_source
from .references import _cached_result as cached_references
from .metrics import export_report_data, summarize_benchmark, _disk_bytes
from .pipeline import paper_directory, _cpu_only_environment
from .reports import write_session_breakdown
from .sessions import finish_session, register_final_report


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def _write_audit(report, rows):
    with (report/'integrity_audit.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['arxiv_id','artifact','valid','detail'])
        writer.writeheader()
        writer.writerows(rows)


def _subset(manifest, identifiers):
    selected = set(identifiers)
    result = {k:deepcopy(v) for k,v in manifest.items() if k not in ('papers','discovery','scope')}
    result['scope'] = dict(mode='ids', ids=list(identifiers), start_id=None, end_id=None)
    result['papers'] = {i:deepcopy(s) for i,s in manifest['papers'].items() if i in selected}
    d = deepcopy(manifest['discovery'])
    d.update(scope=result['scope'], requested_count=len(selected),
             papers=[p for p in d['papers'] if p['arxiv_id'] in selected],
             issues=[i for i in d['issues'] if i['arxiv_id'] in selected])
    d['scope_complete'] = all(i['status']=='not_found' for i in d['issues'])
    d['status'] = 'success' if not d['issues'] else 'partial' if d['papers'] or d['scope_complete'] else 'failed'
    result['discovery'] = d
    return result


def _artifact_audit(manifest, root, policy):
    """Revalidate immutable bytes before acknowledging any complete paper."""
    rows = []
    checker = OaiClient(policy=policy, cache_dir=root/'metadata_cache')
    for identifier, paper in manifest['papers'].items():
        directory = paper_directory(identifier, root)
        valid = True
        try:
            valid = json.loads((directory/'metadata.json').read_text(encoding='utf-8')) == paper['record']['metadata']
            valid = valid and checker._cached(identifier, require_fresh=False) == paper['record']
            for version, value in paper['downloads'].items():
                if value and value['status'] in ('success','no_tex'):
                    valid = valid and cached_source(identifier, int(version), directory/'sources'/f'v{version}') is not None
            refs = paper['references']
            if refs and refs['status']=='success':
                cached = cached_references(identifier,directory,require_fresh=False)
                valid = valid and cached is not None and cached['references']==refs['references'] and cached['all_references']==refs['all_references']
                for key, value in (refs['references'].items() if refs['metadata_source']==METADATA_SOURCE else []):
                    ref_id = key if '/' in key else key.replace('-','.')
                    record = checker._cached(ref_id,require_fresh=False)
                    valid = valid and record is not None and record['metadata']['submission_date']==value['submission_date']
        except (OSError,ValueError,KeyError,TypeError):
            valid = False
        rows.append(dict(arxiv_id=identifier, artifact='immutable snapshot', valid=bool(valid),
                         detail='metadata/source/receipt/reference/OAI validation'))
    return rows


class BackgroundCheckpoints:
    def __init__(self, root: Path, plan: dict, policy: dict, *, every: int = 40):
        if type(every) is not int or every < 1:
            raise ValueError('Checkpoint size must be positive.')
        self.root, self.plan, self.policy = Path(root), deepcopy(plan), dict(policy)
        self.every = every
        self.pending, self.futures = [], []
        self.latest = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='arxiv-drive-backup')
        self.closed = False
        self.audit_rows = []
        self.cpu_only = _cpu_only_environment()
        self.environment = f'{platform.system()} {platform.machine()}; Python {platform.python_version()}; ' + ('Colab' if 'google.colab' in sys.modules else 'local development')

    def paper_done(self, manifest, identifier, *, samples, errors, elapsed_seconds):
        if self.closed:
            raise ValueError('Checkpoint worker is closed.')
        self.pending.append(identifier)
        self.latest = manifest, samples, errors, elapsed_seconds
        if len(self.pending) >= self.every:
            self._submit()

    def _submit(self):
        # Backpressure prevents unbounded ZIP/staging disk growth on slow Drive.
        while len(self.futures) >= 2:
            self.futures.pop(0).result()
        for future in self.futures:
            if future.done():
                future.result()  # Surface upload errors before doing more work.
        manifest, samples, errors, elapsed = self.latest
        samples, errors = deepcopy(samples), list(errors)
        selected = self.pending[:]
        stage = self.root/'.checkpoint-stage'/uuid4().hex
        corpus, report = stage/'corpus', stage/'report'
        corpus.mkdir(parents=True)
        report.mkdir()
        snapshot = _subset(manifest, selected)
        _json(corpus/'manifest.json', snapshot)
        required_cache = set(selected)
        for identifier, paper in snapshot['papers'].items():
            source = paper_directory(identifier,self.root)
            if source.exists():
                target = paper_directory(identifier,corpus)
                target.mkdir()
                for item in _inventory(source):
                    copied = target/item.relative_to(source)
                    if item.is_dir(): copied.mkdir(parents=True,exist_ok=True)
                    else:
                        copied.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(item,copied)
            refs = paper['references']
            if refs:
                required_cache.update(r['arxiv_id'] for r in refs['all_references'] if r['arxiv_id'])
        for identifier in required_cache:
            key = hashlib.sha256(identifier.encode()).hexdigest()
            for suffix in ('.xml','.json'):
                source = self.root/'metadata_cache'/(key+suffix)
                if source.is_file():
                    target = corpus/'metadata_cache'/source.name
                    target.parent.mkdir(exist_ok=True)
                    shutil.copy2(source,target)
        # Snapshot/report generation happens off the network path in the worker.
        self.futures.append(self.pool.submit(self._upload,stage,snapshot,samples,errors,elapsed))
        self.pending.clear()
        print(f'Checkpoint queued: {len(selected)} processed IDs; crawl continues.', flush=True)

    def _upload(self, stage, manifest, samples, errors, elapsed):
        corpus, report = stage/'corpus',stage/'report'
        audit = _artifact_audit(manifest,corpus,self.policy)
        self.audit_rows.extend(audit)  # Single writer; finalize reads after close/join.
        invalid = [r['arxiv_id'] for r in audit if not r['valid']]
        tasks = [v for s in manifest['papers'].values() for v in [*s['downloads'].values(),s['references']] if v]
        mode = 'mixed' if any(v['used_cache'] for v in tasks) else 'cold'
        benchmark = summarize_benchmark(samples,wall_seconds=elapsed,final_disk_bytes=_disk_bytes(corpus),
            environment=self.environment,cpu_only=self.cpu_only,cache_mode=mode,sampling_interval_seconds=.25)
        export_report_data(manifest,benchmark,report)
        _json(report/'manifest.json',manifest)
        _json(report/'run_summary.json',dict(run_id=manifest['run_id'],kind='checkpoint',
            measurement='cumulative session prefix, not a completed-session benchmark',benchmark=benchmark))
        _json(report/'resource_samples.json',samples)
        _json(report/'resource_errors.json',errors)
        write_session_breakdown(report,self.plan,manifest,invalid)
        _write_audit(report,audit)
        backup=backup_run(corpus,report,Path(self.plan['backup_root'])/'checkpoints',run_id=manifest['run_id'],work_dir=stage/'zip')
        state=finish_session(Path(self.plan['state_path']),self.plan,manifest,backup,invalid_ids=invalid,final=False)
        print(f'Checkpoint VERIFIED: {len(manifest["scope"]["ids"])} IDs saved; {len(state["pending_ids"])} queued.',flush=True)
        self._remove_stage(stage)
        return backup

    def close(self):
        if self.closed: return
        try:
            if self.pending: self._submit()
            for future in self.futures: future.result()
        finally:
            self.closed=True
            self.pool.shutdown(wait=True)

    def finalize(self, output, manifest):
        """Save final measurements inside the running Python call, not a UI cell.

        Its corpus ZIP is a manifest-only stub. Source recovery continues to use
        per-paper checkpoint receipts. Report export/upload is outside crawl
        benchmarking, just like the notebook's final report export.
        """
        stage=self.root/'.checkpoint-stage'/uuid4().hex
        corpus,report=stage/'corpus',stage/'report'
        corpus.mkdir(parents=True); report.mkdir()
        _json(corpus/'manifest.json',manifest)
        export_report_data(manifest,output['benchmark'],report)
        _json(report/'manifest.json',manifest)
        _json(report/'run_summary.json',output)
        invalid = [r['arxiv_id'] for r in self.audit_rows if not r['valid']]
        write_session_breakdown(report,self.plan,manifest,invalid)
        _write_audit(report,self.audit_rows)
        for filename in ('resource_samples.json','resource_errors.json','reference_date_stats.json'):
            shutil.copy2(self.root/'metrics'/filename,report/filename)
        _json(report/'report_provenance.json',dict(kind='final_report',source_corpus='per-paper checkpoint receipts',
            benchmark_includes_background_checkpoint_uploads=True,final_report_export_outside_benchmark=True))
        (corpus/'README.txt').write_text('MANIFEST ONLY: source files are in the verified checkpoint corpus ZIPs.\n',encoding='utf-8')
        (report/'README.md').write_text('# Final session report\n\nThe paired corpus.zip is a manifest-only stub, not the source corpus.\nUse the checkpoint ledger in retry-state to locate verified source ZIPs.\n',encoding='utf-8')
        backup=backup_run(corpus,report,Path(self.plan['backup_root'])/'session-reports',run_id=manifest['run_id'],work_dir=stage/'zip')
        register_final_report(self.plan,backup)
        self._remove_stage(stage)
        print('Final session measurements saved on Drive; source recovery uses verified checkpoints.',flush=True)

    def _remove_stage(self, stage):
        stage=Path(stage).resolve()
        owner=(self.root/'.checkpoint-stage').resolve()
        if stage==owner or not stage.is_relative_to(owner) or stage.is_symlink():
            raise ValueError('Unexpected checkpoint staging path.')
        shutil.rmtree(stage)
