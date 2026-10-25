"""Persist per-member retry work across Colab runtimes using verified backups.

Queue IDs are registered BEFORE collection and acknowledged AFTER a verified
backup. Interrupted runs therefore remain pending. Only one runtime per member
may run at a time; tickets reject stale completion, not concurrent writers.
Uses Python JSON/pathlib/UUID/zipfile/hashlib APIs, not an external queue service.
Design, limitations and full citations: KE_HOACH_MILESTONE_1.md sections 10/12.
"""
from __future__ import annotations

from copy import deepcopy
import csv
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from uuid import UUID, uuid4
import zipfile

from .backup import _sha256
from .failures import failure_rows, permanent_tasks, quarantined_ids

_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[A-Za-z][A-Za-z0-9.-]*/\d{7})\Z')


def scope_ids(scope: dict) -> list[str]:
    """Expand the existing scope contract, preserving numeric-ID width/order."""
    if scope.get('mode') == 'range':
        a, b = scope.get('start_id'), scope.get('end_id')
        if (not isinstance(a, str) or not isinstance(b, str)
                or not re.fullmatch(r'\d{4}\.\d{4,5}', a)
                or not re.fullmatch(r'\d{4}\.\d{4,5}', b)
                or a[:4] != b[:4] or len(a) != len(b) or a > b or scope.get('ids')):
            raise ValueError('Invalid retry range scope.')
        width = len(a) - 5
        result = [f'{a[:4]}.{n:0{width}d}' for n in range(int(a[5:]), int(b[5:]) + 1)]
    elif scope.get('mode') == 'ids' and scope.get('start_id') is None and scope.get('end_id') is None:
        result = scope.get('ids')
    else:
        raise ValueError('Invalid retry scope.')
    _validate_ids(result)
    return list(dict.fromkeys(result))


def _validate_ids(values):
    if not isinstance(values, list) or not values or any(
        not isinstance(i, str) or not _ID.fullmatch(i)
        or not 1 <= int((i.split('/')[-1] if '/' in i else i.split('.')[0])[2:4]) <= 12
        for i in values
    ):
        raise ValueError('Invalid retry arXiv IDs.')


def _read(path: Path, member: str) -> dict:
    if path.is_symlink():
        raise ValueError('Retry state must not be a symbolic link.')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        # exists() can suppress permission/I/O errors. Only an actual missing
        # file is a fresh queue; every other read error must stop collection.
        return dict(schema_version='1.0', member=member, pending_ids=[], sources={},
                    active_session=None, last_completed_session=None, backups=[], permanent_failures={})
    if (not isinstance(value, dict) or value.get('schema_version') != '1.0'
            or value.get('member') != member or not isinstance(value.get('pending_ids'), list)
            or not isinstance(value.get('sources'), dict) or not isinstance(value.get('backups'), list)
            or not all(isinstance(value.get(k), (str, type(None)))
                       for k in ('active_session', 'last_completed_session'))):
        raise ValueError('Invalid retry state or wrong member; keep the original file.')
    pending = value['pending_ids']
    if pending:
        _validate_ids(pending)
    if len(set(pending)) != len(pending) or not set(value['sources']).issubset(pending):
        raise ValueError('Inconsistent retry state.')
    if any(not isinstance(v, str) for v in value['sources'].values()):
        raise ValueError('Invalid retry backup source.')
    quarantine = value.setdefault('permanent_failures', {})
    if not isinstance(quarantine, dict):
        raise ValueError('Invalid permanent failure state.')
    if quarantine:
        _validate_ids(list(quarantine))
    if any(not isinstance(rows, list) or not rows or any(
            not isinstance(row, dict) or row.get('arxiv_id') != identifier
            or row.get('category') != 'permanent' for row in rows)
           for identifier, rows in quarantine.items()):
        raise ValueError('Invalid permanent failure evidence.')
    return value


def _write(path: Path, value: dict) -> None:
    """Publish complete JSON and verify the written bytes; never reset on error."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    pending = path.with_name(path.name + '.' + uuid4().hex + '.part')
    pending.write_bytes(body)
    if pending.read_bytes() != body:
        raise OSError('Retry state copy could not be verified.')
    os.replace(pending, path)
    if path.read_bytes() != body:
        raise OSError('Published retry state could not be verified.')


def completed_sources(state: dict) -> dict[str, str]:
    """Replay the append-only receipt ledger; later failures never erase success.

    Also migrates old v1 queues without inventing completion for unbacked IDs.
    Each ID has one chosen verified source, even across checkpoints and retries.
    """
    result = {}
    for item in state['backups']:
        for identifier in item['completed_ids']:
            result[identifier] = item['receipt_path']
    return result


def migrate_permanent_failures(state_path: Path, *, member: str) -> int:
    """Classify old pending evidence once, using hash-verified report archives.

    Does not contact upstream services, reset queues, or acknowledge completion.
    Missing/corrupt evidence stops migration instead of silently dropping IDs.
    """
    path = Path(state_path)
    state = _read(path, member)
    scanned = set(state.get('quarantine_scanned_receipts', []))
    grouped = {}
    for identifier, source in state['sources'].items():
        if source not in scanned and identifier in state['pending_ids']:
            grouped.setdefault(source, set()).add(identifier)
    added = 0
    for source, identifiers in grouped.items():
        receipt_file = locate_receipt(source, path.resolve().parent.parent)
        receipt = _receipt(receipt_file, path.resolve().parent.parent)
        archive = receipt_file.parent / 'report.zip'
        expected = receipt['archives']['report']
        if archive.stat().st_size != expected['bytes'] or _sha256(archive) != expected['sha256']:
            raise OSError('Quarantine migration report failed its backup hash.')
        with zipfile.ZipFile(archive) as zipped:
            manifest = json.loads(zipped.read('manifest.json'))
            invalid = set()
            if 'integrity_audit.csv' in zipped.namelist():
                invalid = {r['arxiv_id'] for r in csv.DictReader(io.StringIO(
                    zipped.read('integrity_audit.csv').decode('utf-8')))
                    if r['valid'].lower() not in ('true', '1')}
        terminal = quarantined_ids(manifest, invalid) & identifiers
        rows = failure_rows(manifest)
        for identifier in terminal:
            state['permanent_failures'][identifier] = [dict(r, receipt_path=source)
                for r in rows if r['arxiv_id'] == identifier and r['category'] == 'permanent']
        added += len(terminal)
        scanned.add(source)
    if grouped:
        blocked = set(state['permanent_failures']) - completed_sources(state).keys()
        state['pending_ids'] = [i for i in state['pending_ids'] if i not in blocked]
        state['sources'] = {i: s for i, s in state['sources'].items() if i in state['pending_ids']}
        state['quarantine_scanned_receipts'] = sorted(scanned)
        _write(path, state)
    return added


def progress(state_path: Path, *, member: str, assignment_scope: dict,
             previous_assignment_scope: dict | None = None) -> dict:
    """Read progress for the current segment without dropping older queue work.

    An explicit previous scope permits splitting an existing assignment. Its
    receipts and pending IDs remain in the same queue; only the current segment
    contributes to the overview and automatic work selection.
    """
    assigned = scope_ids(assignment_scope)
    allowed = scope_ids(previous_assignment_scope) if previous_assignment_scope is not None else assigned
    assigned_set = set(assigned)
    if not assigned_set.issubset(allowed):
        raise ValueError('Current assignment must belong to the previous member range.')
    state = _read(Path(state_path), member)
    if state.get('assignment_ids', assigned) not in (assigned, allowed):
        raise ValueError('Full assignment changed; keep the saved member range.')
    quarantine = set(state['permanent_failures']) - completed_sources(state).keys()
    seen = set(state['pending_ids']) | quarantine
    for entry in state['backups']:
        seen.update(entry['requested_ids'])
        seen.update(entry['completed_ids'])
    if not seen.issubset(allowed):
        raise ValueError('Saved work contains IDs outside this member assignment.')
    completed = completed_sources(state)
    pending = [i for i in state['pending_ids'] if i in assigned_set and i not in completed and i not in quarantine]
    unseen = [i for i in assigned if i not in seen]
    return dict(member=member, total=len(assigned), completed=len(set(assigned) & completed.keys()),
                pending=len(pending), unseen=len(unseen), quarantined=len(assigned_set & quarantine),
                next_new_id=unseen[0] if unseen else None,
                pending_ids=pending, unseen_ids=unseen,
                last_saved_id=next((i for b in reversed(state['backups'])
                                    for i in reversed(b['completed_ids']) if i in assigned_set), None))


def plan_session(state_path: Path, *, member: str, assignment_scope: dict,
                 new_limit: int, retry_limit: int = 40, retry_only: bool = False,
                 previous_assignment_scope: dict | None = None) -> dict:
    """Select N unseen IDs plus bounded retry work; never reschedule saved success."""
    if (type(new_limit) is not int or new_limit < 1 or type(retry_limit) is not int
            or retry_limit < 0 or type(retry_only) is not bool):
        raise ValueError('New limit must be positive and retry limit nonnegative.')
    migrate_permanent_failures(state_path, member=member)
    info = progress(state_path, member=member, assignment_scope=assignment_scope,
                    previous_assignment_scope=previous_assignment_scope)
    retries = info['pending_ids'][:retry_limit]
    new = [] if retry_only else info['unseen_ids'][:new_limit]
    selected = list(dict.fromkeys([*retries, *new]))
    if not selected:
        return dict(ticket=None, member=member, scope=None, requested_ids=[], new_ids=[],
                    retry_ids=[], deferred_ids=info['pending_ids'], sources={}, progress_before=info)
    path = Path(state_path)
    state = _read(path, member)
    # Preserve the original range and all out-of-segment pending/history. Old
    # v1 ledgers had no assignment_ids; pin their explicitly supplied old scope.
    state.setdefault('assignment_ids', scope_ids(previous_assignment_scope)
                     if previous_assignment_scope is not None else scope_ids(assignment_scope))
    _write(path, state)
    plan = prepare_session(path, member=member,
                           scope=dict(mode='ids', ids=selected, start_id=None, end_id=None), extend=False)
    plan['assignment_scope'] = deepcopy(assignment_scope)
    plan['progress_before'] = {k:v for k,v in info.items() if k not in ('pending_ids','unseen_ids')}
    state = _read(path, member)
    state.setdefault('plans', []).append({k:deepcopy(plan[k]) for k in ('ticket','new_ids','retry_ids','requested_ids')})
    _write(path, state)
    return plan


def prepare_session(state_path: Path, *, member: str, scope: dict, extend: bool = True) -> dict:
    """Register work durably; cold sessions prepend pending IDs to the new scope.

    Resume passes extend=False to preserve its manifest scope exactly; pending
    IDs outside that root are deferred, never dropped. A broken queue stops the
    run rather than being replaced with an empty one.
    """
    if not isinstance(member, str) or not member.strip() or type(extend) is not bool:
        raise ValueError('Invalid retry member/options.')
    path = Path(state_path)
    requested = scope_ids(scope)
    state = _read(path, member)
    # Explicit resume retains the exact manifest scope; automatic cold visits
    # omit terminal failures even if a legacy queue still lists them as pending.
    blocked = set(state['permanent_failures']) | completed_sources(state).keys()
    before = [i for i in state['pending_ids'] if i not in blocked]
    if extend:
        requested = [i for i in requested if i not in blocked]
        if not requested and not before:
            return dict(ticket=None, member=member, scope=None, requested_ids=[], new_ids=[],
                        retry_ids=[], deferred_ids=[], sources={})
    known = set(before)
    for entry in state['backups']:
        known.update(entry['requested_ids'])
    combined = list(dict.fromkeys([*before, *requested])) if extend else requested
    actual_scope = (dict(mode='ids', ids=combined, start_id=None, end_id=None)
                    if extend else deepcopy(scope))
    plan = dict(ticket=str(uuid4()), member=member, state_path=str(path.resolve()),
                backup_root=str(path.resolve().parent.parent), input_scope=deepcopy(scope),
                scope=actual_scope, requested_ids=combined,
                retry_ids=[i for i in combined if i in known],
                new_ids=[i for i in requested if i not in known],
                deferred_ids=[i for i in before if i not in combined],
                sources={i: state['sources'][i] for i in combined if i in state['sources']})
    state['pending_ids'] = list(dict.fromkeys([*before, *requested]))
    state['sources'] = {i: source for i, source in state['sources'].items() if i in state['pending_ids']}
    state['active_session'] = plan['ticket']
    _write(path, state)
    return plan


def locate_receipt(value: str, allowed_root: Path) -> Path:
    """Resolve a copied member tree without following old machine/Drive paths.

    Only the known run UUID/attempt/receipt layout may be rebased. Keep each
    member's backup tree intact when collecting four personal Drives for Book.
    """
    root = Path(allowed_root).resolve()
    path = Path(value).resolve()
    if path.is_relative_to(root):
        return path
    parts = value.replace('\\','/').split('/')
    if len(parts)<3 or parts[-1]!='backup_receipt.json':
        raise ValueError('Unrecognized portable backup receipt path.')
    if str(UUID(parts[-3])) != parts[-3]:
        raise ValueError('Portable backup run ID is invalid.')
    if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{8}',parts[-2]):
        raise ValueError('Portable backup attempt name is invalid.')
    tail = parts[-4:] if len(parts)>=4 and parts[-4] in ('checkpoints','session-reports') else parts[-3:]
    path = root.joinpath(*tail).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Portable backup path escapes its member folder.')
    return path


def _receipt(path: Path, allowed_root: Path) -> dict:
    path = path.resolve()
    if path.name != 'backup_receipt.json' or not path.is_relative_to(allowed_root.resolve()):
        raise ValueError('Retry source is outside this Drive backup root.')
    receipt = json.loads(path.read_text(encoding='utf-8'))
    if receipt.get('schema_version') != '1.0' or set(receipt.get('archives', {})) != {'corpus', 'report'}:
        raise ValueError('Invalid backup receipt.')
    for name, entry in receipt['archives'].items():
        if (entry.get('filename') != name + '.zip' or type(entry.get('bytes')) is not int
                or entry['bytes'] < 0 or not re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', ''))):
            raise ValueError('Invalid backup archive identity.')
    return receipt


def seed_pending(plan: dict, root: Path) -> int:
    """Restore pending papers' source/hidden receipts/cache into a NEW local root.

    Full ZIP hash is checked before selective extraction. Do not copy the old
    manifest or metrics: the next run gets its own scope, run_id and benchmark.
    Source/reference cache validators still decide whether a restored task can
    be reused. ZIP paths/links/special files are rejected before writing entries.
    """
    root = Path(root)
    if root.is_symlink() or (root.exists() and any(root.iterdir())):
        raise ValueError('Retry restoration requires a new empty local root.')
    grouped = {}
    for identifier, receipt_path in plan['sources'].items():
        grouped.setdefault(receipt_path, []).append(identifier)
    copied = 0
    restored_tasks = {}
    for receipt_path, identifiers in grouped.items():
        receipt_file = locate_receipt(receipt_path,Path(plan['backup_root']))
        receipt = _receipt(receipt_file, Path(plan['backup_root']))
        archive = receipt_file.parent / 'corpus.zip'
        expected = receipt['archives']['corpus']
        if archive.stat().st_size != expected['bytes'] or _sha256(archive) != expected['sha256']:
            raise OSError('Retry corpus ZIP does not match its backup receipt.')
        folders = {i.replace('.', '-').replace('/', '-') for i in identifiers}
        with zipfile.ZipFile(archive) as zipped:
            previous = json.loads(zipped.read('manifest.json'))
            restored_tasks.update({i: p for i, p in permanent_tasks(previous).items() if i in identifiers})
            members = []
            for item in zipped.infolist():
                path = PurePosixPath(item.filename)
                mode = item.external_attr >> 16
                if (path.is_absolute() or '..' in path.parts or '\\' in item.filename
                        or ':' in item.filename or not path.parts
                        or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFDIR, stat.S_IFREG))):
                    raise ValueError('Unsafe retry archive entry.')
                if path.parts[0] in folders or path.parts[0] == 'metadata_cache':
                    members.append((item, root.joinpath(*path.parts)))
            for item, target in members:
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(item) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    copied += 1
    if restored_tasks:
        _write(root / 'permanent_tasks.json', restored_tasks)
        copied += 1
    return copied


def successful_ids(manifest: dict, invalid_ids=()) -> set[str]:
    """Operational completion, excluding known discovery/artifact audit failures."""
    invalid = set(invalid_ids)
    invalid.update(i['arxiv_id'] for i in (manifest.get('discovery') or {}).get('issues', []))
    done = set()
    for identifier in scope_ids(manifest['scope']):
        paper = manifest['papers'].get(identifier)
        if not paper or identifier in invalid:
            continue
        versions = paper['record']['versions']
        if (versions and all((paper['downloads'].get(str(v)) or {}).get('status') in ('success', 'no_tex')
                             for v in versions)
                and (paper.get('references') or {}).get('status') == 'success'):
            done.add(identifier)
    return done


def finish_session(state_path: Path, plan: dict, manifest: dict, backup: dict, *, invalid_ids=(), final=True) -> dict:
    """Acknowledge only complete, audited IDs in a verified archived run.

    Unresolved recoverable tasks and integrity failures remain pending. Terminal
    upstream failures are retained separately, never counted as complete.
    A backup error never reaches this function, so unarchived work stays queued.
    """
    path = Path(state_path)
    if path.resolve() != Path(plan['state_path']).resolve():
        raise ValueError('Retry state path changed.')
    state = _read(path, plan['member'])
    if state['last_completed_session'] == plan['ticket']:
        return state
    if state['active_session'] != plan['ticket']:
        raise ValueError('A newer session owns this member queue; old completion rejected.')
    covered = scope_ids(manifest['scope'])
    if ((final and manifest['scope'] != plan['scope'])
            or not set(covered).issubset(plan['requested_ids']) or backup['run_id'] != manifest['run_id']):
        raise ValueError('Retry completion belongs to a different run/scope.')
    receipt_path = Path(backup['receipt_path']).resolve()
    receipt = _receipt(receipt_path, Path(plan['backup_root']))
    if receipt.get('run_id') != manifest['run_id'] or receipt['archives'] != backup['archives']:
        raise ValueError('Retry backup receipt belongs to a different run.')
    if any(not (receipt_path.parent/e['filename']).is_file() for e in receipt['archives'].values()):
        raise OSError('Retry backup archive is missing.')
    if any(b['receipt_path'] == str(receipt_path) for b in state['backups']):
        return state
    done = successful_ids(manifest, invalid_ids)
    terminal = quarantined_ids(manifest, invalid_ids)
    rows = failure_rows(manifest)
    for identifier in terminal:
        state['permanent_failures'][identifier] = [dict(r, receipt_path=str(receipt_path))
            for r in rows if r['arxiv_id'] == identifier and r['category'] == 'permanent']
    for identifier in done | (set(covered) - terminal):
        state['permanent_failures'].pop(identifier, None)
    still_pending = set(state['pending_ids']) - done - terminal
    # Failed retries rotate to the tail, so permanently missing upstream data
    # cannot starve deferred IDs when a per-session retry limit is configured.
    state['pending_ids'] = ([i for i in state['pending_ids'] if i in still_pending and i not in covered]
                            + [i for i in covered if i in still_pending])
    state['sources'] = {i: source for i, source in state['sources'].items() if i in still_pending}
    for identifier in covered:
        if identifier in state['pending_ids']:
            state['sources'][identifier] = str(receipt_path)
    state['backups'].append(dict(run_id=manifest['run_id'], receipt_path=str(receipt_path),
                                 requested_ids=covered, completed_ids=sorted(done),
                                 quarantined_ids=sorted(terminal),
                                 kind='final' if final else 'checkpoint'))
    if final:
        state['last_completed_session'] = plan['ticket']
        state['active_session'] = None
    _write(path, state)
    return state


def register_final_report(plan: dict, backup: dict) -> None:
    """Record a small final report without pointing corpus recovery at its stub.

    Each paper's recoverable bytes were already committed by a checkpoint.
    This report-only bundle contains a manifest stub in corpus.zip, so it MUST
    NOT acknowledge papers or replace their source-archive pointers.
    """
    path = Path(plan['state_path'])
    state = _read(path, plan['member'])
    if state['active_session'] != plan['ticket']:
        raise ValueError('A newer session owns the queue.')
    receipt = _receipt(Path(backup['receipt_path']), Path(plan['backup_root']))
    if receipt['run_id'] != backup['run_id'] or receipt['archives'] != backup['archives']:
        raise ValueError('Final report receipt mismatch.')
    if not any(b['receipt_path'] == backup['receipt_path'] for b in state['backups']):
        state['backups'].append(dict(run_id=backup['run_id'], receipt_path=backup['receipt_path'],
                                     requested_ids=plan['requested_ids'], completed_ids=[], kind='final_report'))
        _write(path, state)
