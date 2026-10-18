"""Persist per-member retry work across Colab runtimes using verified backups.

Queue IDs are registered BEFORE collection and acknowledged AFTER a verified
backup. Interrupted runs therefore remain pending. Only one runtime per member
may run at a time; tickets reject stale completion, not concurrent writers.
Uses Python JSON/pathlib/UUID/zipfile/hashlib APIs, not an external queue service.
Design, limitations and full citations: KE_HOACH_MILESTONE_1.md sections 10/12.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from uuid import uuid4
import zipfile

from .backup import _sha256

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
                    active_session=None, last_completed_session=None, backups=[])
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
    before = state['pending_ids']
    combined = list(dict.fromkeys([*before, *requested])) if extend else requested
    actual_scope = (dict(mode='ids', ids=combined, start_id=None, end_id=None)
                    if extend and before else deepcopy(scope))
    plan = dict(ticket=str(uuid4()), member=member, state_path=str(path.resolve()),
                backup_root=str(path.resolve().parent.parent), input_scope=deepcopy(scope),
                scope=actual_scope, requested_ids=combined,
                retry_ids=[i for i in combined if i in before],
                new_ids=[i for i in requested if i not in before],
                deferred_ids=[i for i in before if i not in combined],
                sources={i: state['sources'][i] for i in combined if i in state['sources']})
    state['pending_ids'] = list(dict.fromkeys([*before, *requested]))
    state['active_session'] = plan['ticket']
    _write(path, state)
    return plan


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
    for receipt_path, identifiers in grouped.items():
        receipt = _receipt(Path(receipt_path), Path(plan['backup_root']))
        archive = Path(receipt_path).resolve().parent / 'corpus.zip'
        expected = receipt['archives']['corpus']
        if archive.stat().st_size != expected['bytes'] or _sha256(archive) != expected['sha256']:
            raise OSError('Retry corpus ZIP does not match its backup receipt.')
        folders = {i.replace('.', '-').replace('/', '-') for i in identifiers}
        with zipfile.ZipFile(archive) as zipped:
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
    return copied


def finish_session(state_path: Path, plan: dict, manifest: dict, backup: dict, *, invalid_ids=()) -> dict:
    """Acknowledge only complete, audited IDs in a verified archived run.

    Missing/failed discovery, source, references, or failed integrity audit all
    remain pending, including confirmed not_found IDs for explicit visibility.
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
    if manifest['scope'] != plan['scope'] or backup['run_id'] != manifest['run_id']:
        raise ValueError('Retry completion belongs to a different run/scope.')
    receipt_path = Path(backup['receipt_path']).resolve()
    receipt = _receipt(receipt_path, Path(plan['backup_root']))
    if receipt.get('run_id') != manifest['run_id'] or receipt['archives'] != backup['archives']:
        raise ValueError('Retry backup receipt belongs to a different run.')
    if any(not (receipt_path.parent/e['filename']).is_file() for e in receipt['archives'].values()):
        raise OSError('Retry backup archive is missing.')
    invalid = set(invalid_ids)
    invalid.update(i['arxiv_id'] for i in (manifest.get('discovery') or {}).get('issues', []))
    done = set()
    for identifier in plan['requested_ids']:
        paper = manifest['papers'].get(identifier)
        if not paper or identifier in invalid:
            continue
        versions = paper['record']['versions']
        if (versions and all((paper['downloads'].get(str(v)) or {}).get('status') in ('success', 'no_tex')
                             for v in versions)
                and (paper.get('references') or {}).get('status') == 'success'):
            done.add(identifier)
    state['pending_ids'] = [i for i in state['pending_ids'] if i not in done]
    state['sources'] = {i: source for i, source in state['sources'].items() if i not in done}
    for identifier in plan['requested_ids']:
        if identifier in state['pending_ids']:
            state['sources'][identifier] = str(receipt_path)
    state['backups'].append(dict(run_id=manifest['run_id'], receipt_path=str(receipt_path),
                                 requested_ids=plan['requested_ids'], completed_ids=sorted(done)))
    state['last_completed_session'] = plan['ticket']
    state['active_session'] = None
    _write(path, state)
    return state
