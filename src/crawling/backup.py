"""Create verified, independent corpus/report backups after a run finishes.

This helper only uses filesystem APIs. The notebook mounts Google Drive and
passes a destination directory; local sources are never deleted. ZIP CRC and
SHA-256 verify transport integrity, not semantic corpus completeness.
References: Python zipfile/hashlib/shutil documentation; full citations and the
backup policy are in docs/milestone1/KE_HOACH_MILESTONE_1.md, sections 10-11.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from uuid import UUID, uuid4
import zipfile


def _sha256(path: Path) -> str:
    """Hash bounded chunks so large corpus ZIPs do not fill notebook RAM."""
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _source_directory(path: Path) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Backup input must be an existing ordinary directory.')
    return path.resolve()


def _inventory(root: Path) -> list[Path]:
    """Fail on scan errors; retain directories so empty no_tex versions survive.

    shutil.make_archive/os.walk without onerror can silently omit an unreadable
    subtree. Build a strict inventory, then archive exactly those entries.
    """
    def fail(exc):
        raise exc
    entries = []
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=fail):
        for name in sorted(dirs + files):
            item = Path(directory) / name
            mode = item.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError('Backup input contains a link or special file.')
            entries.append(item)
    return entries


def _check_run(path: Path, run_id: str) -> None:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or value.get('run_id') != run_id:
        raise ValueError('Corpus/report run IDs must match the selected run.')


def backup_run(
    corpus_root: Path, report_dir: Path, backup_root: Path, *,
    run_id: str, work_dir: Path,
) -> dict:
    """Archive one stable run, copy it, verify bytes and publish a receipt last.

    Inputs must belong to the same completed pipeline invocation (including a
    partial/failed collection with a report). Stop collection before calling.
    Each attempt creates a new folder; a failed attempt has no completion
    receipt and leaves local archives/sources and earlier backups untouched.
    """
    if not isinstance(run_id, str) or str(UUID(run_id)) != run_id:
        raise ValueError('Backup run_id must be a canonical UUID.')
    corpus = _source_directory(corpus_root)
    report = _source_directory(report_dir)
    destination = Path(backup_root).resolve()
    work = Path(work_dir).resolve()
    for output in (destination, work):
        if any(output.is_relative_to(source) for source in (corpus, report)):
            raise ValueError('Backup output must be outside corpus and report inputs.')
    _check_run(corpus / 'manifest.json', run_id)
    _check_run(report / 'manifest.json', run_id)
    _check_run(report / 'run_summary.json', run_id)
    inventories = {'corpus': _inventory(corpus), 'report': _inventory(report)}

    created = datetime.now(timezone.utc)
    attempt = created.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    local_dir = work / run_id / attempt
    local_dir.mkdir(parents=True, exist_ok=False)
    entries = {}
    # Compress on runtime-local disk before writing a few large files to Drive.
    for name, source in (('corpus', corpus), ('report', report)):
        archive = local_dir / (name + '.zip')
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
            for item in inventories[name]:
                zipped.write(item, arcname=item.relative_to(source).as_posix())
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip() is not None:
                raise OSError('Local backup archive failed its CRC check.')
        entries[name] = dict(filename=archive.name, bytes=archive.stat().st_size,
                             sha256=_sha256(archive))

    remote_dir = destination / run_id / attempt
    remote_dir.mkdir(parents=True, exist_ok=False)
    for name, entry in entries.items():
        local = local_dir / entry['filename']
        pending = remote_dir / (entry['filename'] + '.part')
        shutil.copy2(local, pending)
        if pending.stat().st_size != entry['bytes'] or _sha256(pending) != entry['sha256']:
            raise OSError('Copied backup differs from its verified local archive.')
        os.replace(pending, remote_dir / entry['filename'])

    # A receipt is the completion marker: ZIP presence alone is not success.
    receipt = dict(schema_version='1.0', run_id=run_id,
                   created_at_utc=created.isoformat(), archives=entries)
    body = json.dumps(receipt, ensure_ascii=False, indent=2).encode('utf-8')
    pending_receipt = remote_dir / 'backup_receipt.json.part'
    pending_receipt.write_bytes(body)
    if pending_receipt.read_bytes() != body:
        raise OSError('Backup completion receipt could not be verified.')
    receipt_path = remote_dir / 'backup_receipt.json'
    os.replace(pending_receipt, receipt_path)
    return dict(run_id=run_id, directory=str(remote_dir),
                local_directory=str(local_dir), receipt_path=str(receipt_path),
                archives=entries)
