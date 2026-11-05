"""Sequential local parsing, verified checkpoints and immutable batches (Danh / DA3).

Only composes public owner APIs; no gathering/hierarchy/bibliography/metrics duplication.
All versions of one publication remain together; outputs are finalized and read back
before checkpoints. Source/config/code/review signatures and artifact hashes gate resume.
Prepare M1 separately. Backup batches are verified after copy before a receipt is published.
Owner exceptions remain visible; unit orchestration tests are separate from raw integration evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import time
import uuid
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import BinaryIO
from .contracts import ParseConfig, ParsedPublication, ParseRunResult, PublicationInput
from . import contracts as c
from .serialization import (_canonical, _hydrate, _loads, _owned_destination, _write_json,
                            read_publication, read_review_decisions, write_publication, _retry_sharing_violation)
from .validation import finalize_publication

_REVIEW: ContextVar[tuple | None] = ContextVar('m2_review',default=None)
_BACKUP: ContextVar[_BackgroundBackup | None] = ContextVar('m2_backup',default=None)
_PROFILE: ContextVar[list | None] = ContextVar('m2_profile',default=None)
_CODE: ContextVar[str | None] = ContextVar('m2_code_hash',default=None)


def _code_hash() -> str:
    digest = hashlib.sha256()
    source_root = Path(__file__).resolve().parent.parent
    for package in ('parsing','preparation'):
        for path in sorted((source_root/package).glob('*.py')):
            digest.update(path.relative_to(source_root).as_posix().encode('utf-8'))
            digest.update(b'\0'); digest.update(path.read_bytes()); digest.update(b'\0')
    return digest.hexdigest()


def _acquire_writer(output_root: Path) -> BinaryIO:
    # An OS lock is released on process exit. Never infer ownership from a stale
    # marker or unlink an active inode (which could admit a second POSIX writer).
    stream = (output_root/'.m2-writer.lock').open('a+b')
    try:
        stream.seek(0,os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'\0');stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    return stream


def _release_writer(stream: BinaryIO) -> None:
    try:
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_UN)
    finally: stream.close()


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    staging = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        _write_json(staging,value)
        _retry_sharing_violation(lambda: os.replace(staging,path))
    finally:
        if staging.exists(): staging.unlink()


def _relative_file(root: Path, relative: str) -> Path:
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Invalid artifact path')
    path = root/relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Artifact escapes run root')
    if any(p.is_symlink() for p in (path,*path.parents)): raise ValueError('Symlink artifact')
    return path


def _paper_key(arxiv_id: str) -> str:
    # No lossy dot/slash replacement at the filesystem boundary.
    return hashlib.sha256(arxiv_id.encode('utf-8')).hexdigest()


def _review_hash(config: ParseConfig) -> str | None:
    cached = _REVIEW.get()
    if cached is not None and cached[0] == config.reference_review_path: return cached[1]
    return _hash(config.reference_review_path) if config.reference_review_path is not None else None


def _stage(name: str, action: object) -> object:
    started = time.perf_counter()
    try: return action()
    finally:
        profile = _PROFILE.get()
        if profile is not None: profile.append({'stage':name,'wall_seconds':time.perf_counter()-started})


def _merge_metrics(total: c.MetricsSummary, current: c.MetricsSummary) -> c.MetricsSummary:
    statuses = {status:total.status_counts[status]+current.status_counts[status] for status in c.VERSION_STATUSES}
    counts = {}
    for row in total.dedup+current.dedup:
        before,after = counts.get(row.kind,(0,0))
        counts[row.kind] = (before+row.before,after+row.after)
    attempted = statuses['parsed']+statuses['partial']+statuses['failed']
    expected = sum(statuses.values())
    def rate(n: int, d: int) -> float | None: return n/d if d else None
    total.versions.extend(current.versions)
    return c.MetricsSummary(versions=total.versions,status_counts=statuses,
        publication_count=total.publication_count+current.publication_count,
        export_ready_publication_count=total.export_ready_publication_count+current.export_ready_publication_count,
        parse_success_rate=rate(statuses['parsed'],attempted),
        resolved_version_coverage=rate(statuses['parsed']+statuses['empty_no_tex'],expected),
        attempt_coverage=rate(attempted,expected-statuses['empty_no_tex']),
        dedup=[c.DedupCount(kind=kind,before=b,after=a) for kind,(b,a) in sorted(counts.items())])


def _empty_metrics() -> c.MetricsSummary:
    return c.MetricsSummary(versions=[],status_counts={s:0 for s in c.VERSION_STATUSES},publication_count=0,
        export_ready_publication_count=0,parse_success_rate=None,resolved_version_coverage=None,attempt_coverage=None,dedup=[])


def _assert_run_inputs(root: Path, config: ParseConfig, review_sha: str | None, code_sha: str) -> None:
    current_review = _hash(config.reference_review_path) if config.reference_review_path is not None else None
    if current_review != review_sha or _code_hash() != code_sha:
        _atomic_json(root/'cache-invalid.json',{'reason':'Code/review changed during run; do not resume these checkpoints'})
        raise ValueError('Code/review changed during run; checkpoints quarantined')


def _failed_publication(publication: PublicationInput, diagnostic: c.Diagnostic) -> ParsedPublication:
    diagnostics = [deepcopy(d) for version in publication.versions for d in version.diagnostics]+[diagnostic]
    return finalize_publication(c.ParsedPublication(arxiv_id=publication.arxiv_id,elements=[],hierarchy=[],bibtex=[],
        version_states={v.version:('empty_no_tex' if v.source_status=='no_tex' else 'blocked_input' if v.source_status=='blocked' else 'failed') for v in publication.versions},
        occurrences=[],root_ids={v.version:None for v in publication.versions},key_map={},bib_occurrences=[],
        identity_decisions=[],conflicts=[],diagnostics=diagnostics,counts_before_after=[]))


def _cache_candidates(output_root: Path) -> dict[tuple[str,str], list[tuple[Path,c.CheckpointRecord]]]:
    result = {}
    for path in sorted(output_root.glob('*/checkpoints/*.json'),reverse=True):
        try:
            if path.is_symlink(): continue
            checkpoint = _hydrate(c.CheckpointRecord,_loads(path.read_text('utf-8')))
            if checkpoint.contract_version != c.CONTRACT_VERSION or checkpoint.schema_version != c.OUTPUT_SCHEMA_VERSION: continue
            root = path.parent.parent
            if (root/'cache-invalid.json').exists(): continue
            manifest = _hydrate(c.RunManifest,_loads((root/'manifest.json').read_text('utf-8')))
            if manifest.run_id != checkpoint.run_id: continue
            result.setdefault((checkpoint.arxiv_id,checkpoint.signature),[]).append((root,checkpoint))
        except (OSError,ValueError,TypeError): continue
    return result


def _cached_publication(candidates: list, publication: PublicationInput) -> ParsedPublication | None:
    for root,checkpoint in candidates:
        try:
            if not checkpoint.output_sha256: continue
            if any(_hash(_relative_file(root,path)) != digest for path,digest in checkpoint.output_sha256.items()): continue
            destination = _relative_file(root,checkpoint.artifact_path)
            artifacts = {p.relative_to(root).as_posix() for p in destination.iterdir() if p.is_file()}
            if not artifacts.issubset(checkpoint.output_sha256): continue
            parsed = read_publication(destination)
            if parsed.arxiv_id != publication.arxiv_id or set(parsed.version_states) != {v.version for v in publication.versions}: continue
            return parsed
        except (OSError,ValueError,TypeError): continue
    return None


def process_publication(publication: PublicationInput, config: ParseConfig) -> ParsedPublication:
    """Nối một publication đủ versions; import owner APIs bên trong hàm sau khi đã triển khai.
    Gather từng version -> tree -> BibliographyExtraction; unify_entries nhận LIST extractions toàn bài.
    Đọc review file khớp publication.snapshot_id; normalize từng tree -> assemble -> finalize.
    Không bỏ empty/blocked/failed khỏi trees hay extractions. Chặn NotImplementedError rõ, không catch thành success.
    Không đọc lại corpus bằng mỗi owner; không chia versions một bài sang các worker/shard.
    Test integration thực sau merge, không mock tất cả owner API rồi tuyên bố pipeline đạt.
    """
    from .gather import gather_version
    from .hierarchy import parse_version
    from .bibliography import extract_entries
    from .reference_dedup import unify_entries
    from .normalize import normalize_tree
    from .content_dedup import assemble_publication
    from .khang_macros import declarations
    if not publication.versions or len({v.version for v in publication.versions}) != len(publication.versions):
        raise ValueError('Expected versions must be nonempty and unique')
    if any(v.arxiv_id != publication.arxiv_id for v in publication.versions): raise ValueError('Mixed publication versions')
    cached_review = _REVIEW.get()
    if cached_review is not None and cached_review[0] == config.reference_review_path and cached_review[3] == publication.snapshot_id:
        decisions = cached_review[2].get(publication.arxiv_id,[])
    else:
        decisions = [d for d in read_review_decisions(config.reference_review_path,snapshot_id=publication.snapshot_id) if d.arxiv_id == publication.arxiv_id]
    trees, extractions, macro_contexts = [], [], {}
    for version in sorted(publication.versions,key=lambda v:v.version):
        try:
            gathered = _stage('gather',lambda:gather_version(version))
            macro_context = declarations(gathered.latex)
            tree = _stage('tree',lambda:parse_version(gathered,macro_context=macro_context))
            macro_contexts[version.version] = macro_context
            if tree.arxiv_id != publication.arxiv_id or tree.version != version.version: raise ValueError('Owner returned wrong version identity')
        except NotImplementedError: raise
        except Exception as exc:
            diagnostic = c.Diagnostic(arxiv_id=publication.arxiv_id,version=version.version,code='PARSE_FATAL',severity='error',message=f'{type(exc).__name__}: {exc}')
            tree = c.VersionTree(arxiv_id=publication.arxiv_id,version=version.version,root_local_id=None,nodes=[],bibliography_blocks=[],
                status='empty_no_tex' if version.source_status == 'no_tex' else 'blocked_input' if version.source_status == 'blocked' else 'failed',
                source_fingerprint=version.source_fingerprint,diagnostics=deepcopy(version.diagnostics)+[diagnostic])
            extraction = c.BibliographyExtraction(arxiv_id=publication.arxiv_id,version=version.version,occurrences=[],diagnostics=[diagnostic])
        else:
            try:
                extraction = _stage('bibliography',lambda:extract_entries(gathered,tree))
                if extraction.arxiv_id != publication.arxiv_id or extraction.version != version.version: raise ValueError('Bibliography returned wrong version identity')
            except NotImplementedError: raise
            except Exception as exc:
                diagnostic = c.Diagnostic(arxiv_id=publication.arxiv_id,version=version.version,code='BIB_ENTRY_UNPARSED',severity='error',message=f'{type(exc).__name__}: {exc}')
                tree = replace(tree,diagnostics=tree.diagnostics+[diagnostic])
                extraction = c.BibliographyExtraction(arxiv_id=publication.arxiv_id,version=version.version,occurrences=[],diagnostics=[diagnostic])
        trees.append(tree); extractions.append(extraction)
    bibliography = _stage('unify',lambda:unify_entries(publication.arxiv_id,extractions,review_decisions=decisions))
    normalized = _stage('normalize',lambda:[normalize_tree(tree,bibliography,config,
        macro_context=macro_contexts.get(tree.version)) for tree in trees])
    return _stage('assemble_finalize',lambda:finalize_publication(assemble_publication(normalized,bibliography)))


def checkpoint_signature(publication: PublicationInput, config: ParseConfig) -> str:
    """SHA256 canonical JSON contract/output schema + input snapshot + mọi source fingerprints +
    config.normalization_version/strict + code_revision + hash bytes review file (None có marker riêng).
    Không dùng absolute paths/mtime/Python hash; code_revision unrecorded phải bị từ chối ở run thật.
    Source/config/code/review thay đổi -> cache invalid, input chưa đạt không được lấy output tốt cũ che lỗi.
    Giữ raw review bytes hash và verified decisions provenance để tái lập.
    """
    if not config.code_revision.strip() or config.code_revision == 'unrecorded': raise ValueError('Record actual code revision')
    payload = {'contract':c.CONTRACT_VERSION,'schema':c.OUTPUT_SCHEMA_VERSION,'arxiv_id':publication.arxiv_id,
        'snapshot_id':publication.snapshot_id,'preparation_run_id':publication.preparation_run_id,
        'sources':[{'version':v.version,'status':v.source_status,'fingerprint':v.source_fingerprint,
                    'diagnostics':[asdict(d) for d in v.diagnostics]} for v in sorted(publication.versions,key=lambda v:v.version)],
        'normalization_version':config.normalization_version,'strict':config.strict,
        'sample_interval_seconds':config.ram_sample_interval_seconds,
        'code_revision':config.code_revision,'code_sha256':_CODE.get() or _code_hash(),'review_sha256':_review_hash(config)}
    return hashlib.sha256(_canonical(payload).encode('utf-8')).hexdigest()


def run(corpus_root: Path, output_root: Path, config: ParseConfig, *, resume: bool = False,
        max_publications: int | None = None, progress_root: Path | None = None) -> ParseRunResult:
    """API notebook. Timer bắt đầu TRƯỚC inputs.load_publications (bao gồm xác minh raw), kết thúc sau output/checkpoint.
    Đòi input/output tách biệt, không ghi đè raw; một writer một run. Ghi run_id/snapshot/config/code environment.
    Mỗi bài all versions -> process_publication; working/audit giữ lỗi; strict=True chỉ publish export_ready.
    strict=False lưu working partial hợp lệ nhưng không quảng cáo export_ready; schema hỏng chỉ audit, không tables hỏng.
    Lỗi bài độc lập vẫn tiếp tục, lỗi đọc input toàn run/không ghi audit thì fatal. NotImplementedError từ owner phải propagate.
    Resume kiểm signature + read_publication + validator, không tin marker cũ; output/audit xong mới checkpoint.
    Gộp metrics từ TỪNG working publication, kể cả blocked/error, không giữ tables toàn corpus; chỉ success khi mọi expected bài export_ready và ghi thành công.
    RunManifest đúng fields/docstrings trong contracts.py. Run mới giữ run namespace riêng để không dùng output cũ tăng coverage.
    PublicationMeasurement/samples được benchmark ghi theo run; không cộng retry/cache vào fresh benchmark.
    Kiểm cuối S10/S13, full corpus union không trùng trước khi Book/Moodle.

    Layout OUTPUT_ROOT/<run_id>/: manifest.json (RunManifest), working/<paper_key>/,
    published/<paper_key>/ (hoặc manifest trỏ working để khỏi copy), audit/<paper_key>.jsonl,
    checkpoints/<paper_key>.json (CheckpointRecord), metrics/, benchmark/.
    working/published/audit/checkpoint artifact paths trong manifest đều relative run root.
    Nhận modules owner đã xong, không tự triển khai lại logic họ; unit test từng stage bằng fixtures,
    rồi integration thật sau merge. Scratch ngoài Git data/milestone2-dev/<owner>/.
    Khi ghép: rà callers bằng rg rồi dọn nháp/helper duplicate do nhóm tạo có replacement rõ;
    bỏ placeholder skipped test chỉ khi có assertions thật bao acceptance. Không xóa raw/test fail/shared
    fixtures/evidence, không git clean/reset --hard hay hook tự xóa khi merge. Ghi cleanup list trong
    phản hồi bàn giao; kiểm conflicts thủ công nếu ai sửa ngoài ownership, không hứa zero conflict.
    Người thật cuối cùng so xuyên raw->tree->normalize->tables/bib/cites, reviewer từng phần xác nhận.

    max_publications selects a visit from verified progress_root backups: pending
    before unseen, all versions together; four failed durable attempts defer a
    publication. queue.json describes full input scope separately from this visit's
    RunManifest. Omit the limit for the existing full-corpus/benchmark behavior.
    """
    from .inputs import load_publications
    from .metrics import summarize,write_metrics
    if max_publications is not None and (type(max_publications) is not int or max_publications < 1):
        raise ValueError('max_publications must be a positive integer')
    if max_publications is not None and progress_root is None:
        raise ValueError('Bounded visits require a verified backup progress_root')
    started = time.perf_counter()
    corpus_root,output_root = Path(corpus_root).resolve(),_owned_destination(output_root).resolve()
    if corpus_root.is_relative_to(output_root) or output_root.is_relative_to(corpus_root): raise ValueError('Input/output trees must be disjoint')
    if config.code_revision == 'unrecorded' or not config.code_revision.strip(): raise ValueError('Record actual code revision')
    output_root.mkdir(parents=True,exist_ok=True)
    writer = _acquire_writer(output_root)
    run_id = 'm2-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:12]
    root = output_root/run_id
    try:
        root.mkdir()
    except BaseException:
        _release_writer(writer)
        raise
    manifest = c.RunManifest(run_id=run_id,snapshot_id='',preparation_run_id='',code_revision=config.code_revision,
        normalization_version=config.normalization_version,strict=config.strict,review_sha256=None,status='in_progress',publications=[])
    manifest_path,metrics_path = root/'manifest.json',root/'metrics/run_summary.json'
    diagnostics, summary, seen, io_failed = [],_empty_metrics(),set(),False
    review_token,code_token = None,None
    backup = _BACKUP.get()
    def runtime_issue(code: str, message: str, arxiv_id: str = '') -> None:
        issue=c.Diagnostic(arxiv_id=arxiv_id,code=code,severity='error',message=message)
        diagnostics.append(issue)
        with (root/'run_errors.jsonl').open('a',encoding='utf-8',newline='\n') as stream:
            stream.write(_canonical(asdict(issue))+'\n');stream.flush();os.fsync(stream.fileno())
    def backup_step(action, arxiv_id: str = '') -> None:
        nonlocal io_failed
        try: action()
        except (OSError, ValueError) as exc:
            io_failed = True
            runtime_issue('OUTPUT_BACKUP_FAILED',str(exc),arxiv_id)
    try:
        _atomic_json(manifest_path,asdict(manifest))
        publications = _stage('validation_inputs',lambda:load_publications(corpus_root))
        if not publications: raise ValueError('No expected publications')
        contexts = {(p.snapshot_id,p.preparation_run_id) for p in publications}
        if len(contexts) != 1: raise ValueError('Mixed input snapshots/preparation runs')
        manifest.snapshot_id,manifest.preparation_run_id = contexts.pop()
        review_sha = _review_hash(config)
        decisions = read_review_decisions(config.reference_review_path,snapshot_id=manifest.snapshot_id)
        if (config.reference_review_path is not None and _hash(config.reference_review_path) != review_sha):
            raise ValueError('Review changed while being read')
        manifest.review_sha256 = review_sha
        review_index = {}
        for decision in decisions: review_index.setdefault(decision.arxiv_id,[]).append(decision)
        review_token = _REVIEW.set((config.reference_review_path,review_sha,review_index,manifest.snapshot_id))
        code_sha = _code_hash()
        code_token = _CODE.set(code_sha)
        if len({p.arxiv_id for p in publications}) != len(publications):
            raise ValueError('Duplicate publication in input')
        queue = None
        if max_publications is not None:
            from .continuation import read_history,build_queue,write_queue,MAX_ATTEMPTS
            signatures = {p.arxiv_id:checkpoint_signature(p,config) for p in publications}
            publications,queue = build_queue(publications,signatures,
                read_history(progress_root,manifest.snapshot_id),max_publications)
            queue.update(run_id=run_id,snapshot_id=manifest.snapshot_id)
            write_queue(root,queue)
        queue_rows = {r['arxiv_id']:r for r in queue['publications']} if queue is not None else {}
        cache_index = _cache_candidates(output_root) if resume else {}
        _atomic_json(root/'environment.json',{'python':platform.python_version(),'platform':platform.platform(),
            'raw_corpus_root':str(corpus_root),'code_revision':config.code_revision,'code_sha256':code_sha,'config':{
                'strict':config.strict,'normalization_version':config.normalization_version,
                'ram_sample_interval_seconds':config.ram_sample_interval_seconds}})
        _atomic_json(root/'profile/run.json',{'stage':'validation_inputs','wall_seconds':time.perf_counter()-started,
            'note':'Run startup through full input validation/review/cache index; not a fresh-network prepare measurement'})
        for publication in publications:
            if publication.arxiv_id in seen: raise ValueError('Duplicate publication in input')
            seen.add(publication.arxiv_id)
            signature = checkpoint_signature(publication,config)
            paper_started,profile = time.perf_counter(),[]
            key = _paper_key(publication.arxiv_id)
            record = c.RunPublicationRecord(arxiv_id=publication.arxiv_id,expected_versions=[v.version for v in publication.versions],
                checkpoint_signature=signature,export_ready=False,working_path=None,published_path=None,
                audit_path='audit/'+key+'.jsonl',wall_seconds=None,used_cache=False,output_sha256={})
            profile_token = _PROFILE.set(profile)
            parsed = None
            try:
                parsed = _cached_publication(cache_index.get((publication.arxiv_id,signature),[]),publication) if resume else None
                if queue is not None and parsed is not None and not parsed.export_ready:
                    parsed = None  # A retry must execute owners, not replay a cached failure.
                record.used_cache = parsed is not None
                if parsed is None: parsed = process_publication(publication,config)
                if parsed.arxiv_id != publication.arxiv_id or set(parsed.version_states) != {v.version for v in publication.versions}:
                    raise ValueError('Processor lost expected publication/version coverage')
                parsed = finalize_publication(parsed)
            except NotImplementedError:
                raise
            except Exception as exc:
                parsed = _failed_publication(publication,c.Diagnostic(arxiv_id=publication.arxiv_id,code='PARSE_FATAL',severity='error',message=f'{type(exc).__name__}: {exc}'))
            finally:
                _PROFILE.reset(profile_token)
            _assert_run_inputs(root,config,review_sha,code_sha)
            export_started = time.perf_counter()
            try:
                files = _stage('export_readback',lambda:write_publication(parsed,root/'working'/key))
                record.working_path = 'working/'+key
                record.export_ready = parsed.export_ready
                if parsed.export_ready or not config.strict: record.published_path = record.working_path
                record.output_sha256 = {p.relative_to(root).as_posix():_hash(p) for p in files}
            except (OSError,ValueError,TypeError) as exc:
                io_failed = True
                record.working_path,record.published_path,record.export_ready,record.output_sha256 = None,None,False,{}
                parsed.diagnostics.append(c.Diagnostic(arxiv_id=publication.arxiv_id,code='OUTPUT_WRITE_FAILED',severity='error',message=str(exc)))
                parsed = finalize_publication(parsed)
            profile.append({'stage':'export_readback','wall_seconds':time.perf_counter()-export_started})
            # Audit is a fatal boundary if it cannot be persisted.
            audit = root/record.audit_path
            audit.parent.mkdir(parents=True,exist_ok=True)
            with audit.open('w',encoding='utf-8',newline='\n') as stream:
                for diagnostic in parsed.diagnostics: stream.write(_canonical(asdict(diagnostic))+'\n')
                stream.flush(); os.fsync(stream.fileno())
            if record.working_path is not None:
                record.output_sha256[record.audit_path] = _hash(audit)
                checkpoint = c.CheckpointRecord(arxiv_id=publication.arxiv_id,run_id=run_id,signature=signature,
                    artifact_path=record.working_path,output_sha256=record.output_sha256)
                try:
                    _atomic_json(root/'checkpoints'/(key+'.json'),asdict(checkpoint))
                except OSError as exc:
                    io_failed = True
                    parsed.diagnostics.append(c.Diagnostic(arxiv_id=publication.arxiv_id,code='OUTPUT_WRITE_FAILED',severity='error',
                        message=f'Checkpoint failed after verified local artifact {record.working_path}: {exc}'))
                    parsed = finalize_publication(parsed)
                    record.working_path,record.published_path,record.export_ready,record.output_sha256 = None,None,False,{}
                    with audit.open('w',encoding='utf-8',newline='\n') as stream:
                        for diagnostic in parsed.diagnostics: stream.write(_canonical(asdict(diagnostic))+'\n')
                        stream.flush();os.fsync(stream.fileno())
            diagnostics.extend(parsed.diagnostics)
            current = summarize([parsed])
            summary = _merge_metrics(summary,current)
            record.wall_seconds = time.perf_counter()-paper_started
            _atomic_json(root/'profile'/(key+'.json'),{'arxiv_id':publication.arxiv_id,'run_id':run_id,
                'used_cache':record.used_cache,'stages':profile})
            manifest.publications.append(record)
            _atomic_json(manifest_path,asdict(manifest))
            if queue is not None:
                row = queue_rows[publication.arxiv_id]
                row['attempts'] += 1
                row['status'] = 'done' if record.export_ready and record.working_path else ('deferred' if row['attempts'] >= MAX_ATTEMPTS else 'pending')
                row.setdefault('evidence',[]).append({'run_id':run_id,'audit_path':record.audit_path,
                    'audit_sha256':_hash(audit),'export_ready':record.export_ready})
                write_queue(root,queue)
            if backup is not None and backup.add(publication.arxiv_id):
                backup_step(backup.wait)
                backup_step(lambda: backup.submit(root), publication.arxiv_id)
            del parsed,current,profile
        write_metrics(summary,root/'metrics',run_id=run_id,snapshot_id=manifest.snapshot_id)
        if backup is not None:
            backup_step(backup.wait)
        _assert_run_inputs(root,config,review_sha,code_sha)
        manifest.status = 'success' if all(r.export_ready and r.working_path for r in manifest.publications) and not io_failed else 'partial'
        _atomic_json(manifest_path,asdict(manifest))
        _atomic_json(root/'timing.json',{'wall_seconds':time.perf_counter()-started,'boundary':'before input validation through output/readback/checkpoints/metrics'})
        if backup is not None:
            try: backup.finish(root)
            except (OSError,ValueError) as exc:
                manifest.status = 'partial'
                runtime_issue('OUTPUT_BACKUP_FAILED',str(exc))
                _atomic_json(manifest_path,asdict(manifest))
        return ParseRunResult(run_id=run_id,snapshot_id=manifest.snapshot_id,status=manifest.status,manifest_path=manifest_path,
            metrics_path=metrics_path,processed_publications=len(manifest.publications),diagnostics=diagnostics)
    except BaseException as exc:
        manifest.status = 'failed'
        # Preserve the original exception even when local/Drive persistence fails.
        actions = [lambda: runtime_issue('RUN_FATAL',f'{type(exc).__name__}: {exc}'),
                   lambda: _atomic_json(manifest_path,asdict(manifest))]
        if backup is not None:
            actions.extend((lambda: backup_step(backup.wait), lambda: backup.finish(root)))
        for action in actions:
            try: action()
            except BaseException: pass
        raise
    finally:
        if review_token is not None: _REVIEW.reset(review_token)
        if code_token is not None: _CODE.reset(code_token)
        _release_writer(writer)


@dataclass(frozen=True)
class _BackupSnapshot:
    manifest: str
    immutable_metadata: tuple[str, ...]
    mutable_metadata: dict[str, bytes]


def _snapshot_backup(run_root: Path) -> _BackupSnapshot:
    # Committed audit/profile files are immutable. Capture their names before the
    # parser writes the next publication, and freeze metadata that it may rewrite.
    immutable = tuple(p.relative_to(run_root).as_posix()
                      for folder in ('metrics','benchmark','audit','profile')
                      for p in (run_root/folder).rglob('*') if p.is_file())
    mutable = {name: _relative_file(run_root,name).read_bytes()
               for name in ('environment.json','timing.json','run_errors.jsonl',
                            'queue.json','review_later.csv') if (run_root/name).is_file()}
    return _BackupSnapshot((run_root/'manifest.json').read_text('utf-8'), immutable, mutable)


def backup_run_batch(run_root: Path, backup_root: Path, *, arxiv_ids: list[str] | None = None,
                     _snapshot: _BackupSnapshot | None = None) -> Path | None:
    """Copy a new immutable ZIP batch, verify destination bytes, then publish its receipt.

    Only completed, hash-verified checkpoints are eligible. A receipt is the durable marker;
    unreceipted archives are never trusted. Already verified papers are not zipped again.
    Returns None when no newly completed publication remains. Drive time is separate from parse.
    """
    run_root,backup_root = Path(run_root).resolve(),_owned_destination(backup_root).resolve()
    if (run_root/'cache-invalid.json').exists(): raise ValueError('Run checkpoints were invalidated')
    if backup_root.is_relative_to(run_root) or run_root.is_relative_to(backup_root): raise ValueError('Backup must be separate from local run')
    snapshot = _snapshot if _snapshot is not None else _snapshot_backup(run_root)
    manifest = _hydrate(c.RunManifest,_loads(snapshot.manifest))
    target = backup_root/manifest.run_id
    target.mkdir(parents=True,exist_ok=True)
    completed, backed_files = set(), {}
    latest_backup, latest_metadata, batch_number = (-1,-1), None, 0
    for receipt_path in target.glob('batch-*.zip.receipt.json'):
        receipt = _loads(receipt_path.read_text('utf-8'))
        archive = target/receipt['archive']
        if receipt.get('run_id') == manifest.run_id and receipt.get('snapshot_id') == manifest.snapshot_id and archive.is_file() and _hash(archive) == receipt['sha256']:
            completed.update(receipt['arxiv_ids'])
            number=receipt.get('batch_number',0)
            if type(number) is not int or number < 0: raise ValueError('Invalid backup batch number')
            batch_number=max(batch_number,number)
            order=(number,receipt_path.stat().st_mtime_ns)
            if order>latest_backup:
                latest_backup,latest_metadata=order,receipt.get('metadata_sha256')
            for relative,digest in receipt.get('files',{}).items():
                backed_files.setdefault(relative,set()).add(digest)
    selected = [r for r in manifest.publications if r.working_path and r.arxiv_id not in completed and (arxiv_ids is None or r.arxiv_id in arxiv_ids)]
    # Preserve evidence for every attempted publication, including ones without
    # valid working tables. Checkpoint manifests remain batch-local for restore;
    # run_manifest.json separately preserves the full run and its actual status.
    metadata_hashes = {path: _hash(_relative_file(run_root,path)) for path in snapshot.immutable_metadata}
    metadata_hashes.update({path: hashlib.sha256(content).hexdigest()
                            for path, content in snapshot.mutable_metadata.items()})
    run_manifest = (_canonical(asdict(manifest))+'\n').encode('utf-8')
    metadata_hashes['run_manifest.json'] = hashlib.sha256(run_manifest).hexdigest()
    metadata_sha = hashlib.sha256(_canonical(metadata_hashes).encode('utf-8')).hexdigest()
    if not selected and metadata_sha == latest_metadata: return None
    files = {}
    # Keep all batches: unchanged metadata already has a verified durable copy.
    # Full run context stays in every new batch, while large audits/profiles are deltas.
    files.update({path:digest for path,digest in metadata_hashes.items()
                  if path=='run_manifest.json' or digest not in backed_files.get(path,set())})
    for record in selected:
        checkpoint_path = 'checkpoints/'+_paper_key(record.arxiv_id)+'.json'
        checkpoint_file = _relative_file(run_root,checkpoint_path)
        checkpoint = _hydrate(c.CheckpointRecord,_loads(checkpoint_file.read_text('utf-8')))
        if checkpoint.signature != record.checkpoint_signature or checkpoint.output_sha256 != record.output_sha256:
            raise ValueError('Checkpoint/manifest mismatch before backup')
        folder = _relative_file(run_root,record.working_path)
        actual_files = {p.relative_to(run_root).as_posix() for p in folder.iterdir() if p.is_file()}
        if not actual_files or not actual_files.issubset(record.output_sha256): raise ValueError('Incomplete publication hash inventory')
        for path,digest in record.output_sha256.items():
            if _hash(_relative_file(run_root,path)) != digest: raise ValueError('Output changed before backup')
            files[path] = digest
        files[checkpoint_path] = _hash(checkpoint_file)
        read_publication(_relative_file(run_root,record.working_path))
    batch_id = 'batch-'+uuid.uuid4().hex
    staging = run_root/('.'+batch_id+'.zip')
    archive = target/(batch_id+'.zip')
    transfer = target/('.'+batch_id+'.part')
    try:
        with zipfile.ZipFile(staging,'x',compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr('manifest.json',_canonical(asdict(replace(manifest,publications=selected,status='partial'))))
            for relative in sorted(files):
                if relative == 'run_manifest.json': bundle.writestr(relative,run_manifest)
                elif relative in snapshot.mutable_metadata: bundle.writestr(relative,snapshot.mutable_metadata[relative])
                else: bundle.write(_relative_file(run_root,relative),relative)
        digest = _hash(staging)
        shutil.copyfile(staging,transfer)
        with transfer.open('r+b') as stream: os.fsync(stream.fileno())
        if _hash(transfer) != digest: raise ValueError('Backup destination checksum mismatch')
        transfer.rename(archive)
        if _hash(archive) != digest: raise ValueError('Final backup archive checksum mismatch')
        if (run_root/'cache-invalid.json').exists(): raise ValueError('Run checkpoints were invalidated')
        receipt = {'kind':'m2-parsed-batch-1.0','run_id':manifest.run_id,'snapshot_id':manifest.snapshot_id,
            'batch_number':batch_number+1,'metadata_files':metadata_hashes,
            'code_revision':manifest.code_revision,'archive':archive.name,'sha256':digest,
            'arxiv_ids':[r.arxiv_id for r in selected],'files':files,
            'metadata_sha256':metadata_sha,
            'signatures':{r.arxiv_id:r.checkpoint_signature for r in selected}}
        _atomic_json(Path(str(archive)+'.receipt.json'),receipt)
    finally:
        staging.unlink(missing_ok=True); transfer.unlink(missing_ok=True)
    return archive


def restore_run_batch(archive: Path, destination: Path, *, expected_sha256: str) -> Path:
    """Restore a verified batch into a new local run folder. Revalidate cache on resume.

    Multiple batches may be restored to separate children of OUTPUT_ROOT; resume indexes
    checkpoints in each child. Their manifest run_id is preserved; no old coverage is assumed.
    """
    archive,destination = Path(archive),_owned_destination(destination)
    receipt = _loads(Path(str(archive)+'.receipt.json').read_text('utf-8'))
    if receipt.get('kind') != 'm2-parsed-batch-1.0' or receipt.get('sha256') != expected_sha256 or _hash(archive) != expected_sha256:
        raise ValueError('Invalid batch receipt/checksum')
    if destination.exists(): raise FileExistsError('Restore requires a new destination')
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging = destination.with_name('.'+destination.name+'.restore-'+uuid.uuid4().hex)
    staging.mkdir()
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = set()
            for member in bundle.infolist():
                if member.filename in names or member.is_dir() or (member.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Duplicate/directory/symlink ZIP entry')
                names.add(member.filename)
                path = _relative_file(staging,member.filename)
                path.parent.mkdir(parents=True,exist_ok=True)
                with bundle.open(member) as source,path.open('xb') as output: shutil.copyfileobj(source,output)
        if names != set(receipt['files']) | {'manifest.json'}: raise ValueError('Batch inventory mismatch')
        for relative,digest in receipt['files'].items():
            if _hash(_relative_file(staging,relative)) != digest: raise ValueError('Restored file checksum mismatch')
        manifest = _hydrate(c.RunManifest,_loads((staging/'manifest.json').read_text('utf-8')))
        if manifest.run_id != receipt['run_id'] or manifest.snapshot_id != receipt['snapshot_id']: raise ValueError('Batch identity mismatch')
        for record in manifest.publications:
            if receipt['signatures'].get(record.arxiv_id) != record.checkpoint_signature: raise ValueError('Batch signature mismatch')
            read_publication(_relative_file(staging,record.working_path))
        staging.rename(destination)
    finally:
        if staging.exists(): shutil.rmtree(staging)
    return destination


class _BackgroundBackup:
    def __init__(self, pool: ThreadPoolExecutor, root: Path, batch_size: int):
        self.pool, self.root, self.batch_size = pool, root, batch_size
        self.pending: list[str] = []
        self.retry: list[str] = []
        self.active_ids: list[str] = []
        self.future: Future | None = None

    def add(self, arxiv_id: str) -> bool:
        self.pending.append(arxiv_id)
        return len(self.pending) >= self.batch_size

    def submit(self, run_root: Path) -> None:
        snapshot = _snapshot_backup(run_root)
        self.active_ids = self.pending[:self.batch_size]
        self.future = self.pool.submit(backup_run_batch,run_root,self.root,
                                       arxiv_ids=self.active_ids,_snapshot=snapshot)
        del self.pending[:self.batch_size]

    def wait(self) -> None:
        if self.future is None: return
        try:
            self.future.result()
        except (OSError, ValueError):
            self.retry.extend(self.active_ids)
            self.future = None
            raise
        self.future = None

    def finish(self, run_root: Path) -> None:
        remaining = self.retry + self.pending
        # Keep recovery ZIPs bounded even after multiple failed background uploads.
        for start in range(0,len(remaining),self.batch_size):
            backup_run_batch(run_root,self.root,arxiv_ids=remaining[start:start+self.batch_size])
        if not remaining:
            backup_run_batch(run_root,self.root,arxiv_ids=[])


def run_with_backup(corpus_root: Path, output_root: Path, config: ParseConfig, backup_root: Path, *, resume: bool = False,
                    batch_size: int = 50, max_publications: int | None = None) -> ParseRunResult:
    """Parse sequentially while one worker uploads completed, bounded batches.

    A lost runtime can lose work since the most recent verified receipt. Backup failures keep
    local good output and make the run partial. Use benchmark_run separately for fresh timings.
    """
    if type(batch_size) is not int or batch_size < 1: raise ValueError('batch_size must be positive')
    raw,backup = Path(corpus_root).resolve(),_owned_destination(backup_root).resolve()
    if backup.is_relative_to(raw) or raw.is_relative_to(backup): raise ValueError('Backup and raw input must be disjoint')
    with ThreadPoolExecutor(max_workers=1,thread_name_prefix='m2-drive-backup') as pool:
        token = _BACKUP.set(_BackgroundBackup(pool,backup,batch_size))
        try: return run(corpus_root,output_root,config,resume=resume,
                        max_publications=max_publications,progress_root=backup_root if max_publications is not None else None)
        finally: _BACKUP.reset(token)

