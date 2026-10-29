"""Transport prepared raw as one ZIP; parsing still validates local raw at run start.

One writer only: freeze the prepared source during packing. Archive SHA-256 checks
transport integrity; it does not replace validate_prepared_corpus before parsing.
"""
import hashlib
from pathlib import Path
import re
import shutil
from uuid import uuid4
import zipfile

from .milestone2 import _no_links, _safe_members, _write_json
from .validation import validate_prepared_corpus


def pack_prepared_corpus(corpus_root: Path, archive_path: Path) -> dict:
    """Optional step AFTER M1 preparation. Preserve its schema, bytes and empty dirs.

    Destination must be new and outside raw. Receipt is <archive>.receipt.json.
    No parser or crawl is invoked; partial-but-valid raw retains blocked versions.
    """
    root, archive = Path(corpus_root).absolute(), Path(archive_path).absolute()
    _no_links(root)
    _no_links(archive)
    root, archive = root.resolve(), archive.resolve()
    if archive.is_relative_to(root) or root.is_relative_to(archive):
        raise ValueError('Archive must be outside prepared raw')
    receipt_path = Path(str(archive) + '.receipt.json')
    if archive.exists() or receipt_path.exists():
        raise FileExistsError('Use a new archive path; existing bundles are not overwritten')
    check = validate_prepared_corpus(root)
    if not check['valid']:
        raise ValueError(f"Prepared raw is invalid: {check['issues']}")
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_name(archive.name + '.tmp-' + uuid4().hex)
    try:
        checked = set()
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as zipped:
            for path in sorted(root.rglob('*')):
                _no_links(path, checked)
                if not path.is_dir() and not path.is_file():
                    raise ValueError('Prepared raw contains a special file')
                zipped.write(path, path.relative_to(root).as_posix())
        with temporary.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        receipt = dict(kind='m2-prepared-transport-1.0', snapshot_id=check['snapshot_id'],
                       sha256=digest, bytes=temporary.stat().st_size,
                       paper_count=check['paper_count'], versions_expected=check['versions_expected'])
        temporary.rename(archive)
        _write_json(receipt_path, receipt)
        return receipt
    finally:
        temporary.unlink(missing_ok=True)


def stage_prepared_archive(archive_path: Path, destination: Path, *, expected_sha256: str) -> Path:
    """Copy one ZIP to local disk, verify hash, safely unpack into a NEW directory.

    Never merge into existing raw or outputs. No full-corpus validation here:
    inputs.load_publications owns that once per parser run. If runtime is reused,
    point RAW_CORPUS_ROOT to the existing copy and still run fresh validation.
    """
    archive, target = Path(archive_path).absolute(), Path(destination).absolute()
    _no_links(archive)
    _no_links(target)
    archive, target = archive.resolve(), target.resolve()
    if not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('A lowercase SHA-256 from the transport receipt is required')
    if target.exists():
        raise FileExistsError('Local destination already exists; reuse explicitly or choose a new path')
    if archive.is_relative_to(target):
        raise ValueError('Source archive must be outside destination')
    target.parent.mkdir(parents=True, exist_ok=True)
    work = target.with_name(target.name + '.stage-' + uuid4().hex)
    work.mkdir()
    try:
        copied, unpacked = work / 'transport.zip', work / 'raw'
        digest = hashlib.sha256()
        with archive.open('rb') as source, copied.open('xb') as output:
            while block := source.read(1024 * 1024):
                digest.update(block)
                output.write(block)
        if digest.hexdigest() != expected_sha256:
            raise ValueError('Transport SHA-256 mismatch')
        unpacked.mkdir()
        with zipfile.ZipFile(copied) as zipped:
            members = _safe_members(zipped)
            if not {'manifest.json', 'preparation.json', 'input_validation.json'} <= members.keys():
                raise ValueError('Not a prepared raw bundle')
            if sum(info.file_size for info in members.values()) > shutil.disk_usage(work).free:
                raise ValueError('Insufficient local disk for prepared raw')
            # _safe_members checks every path, including directory/link entries.
            for info in zipped.infolist():
                path = unpacked.joinpath(*Path(info.filename).parts)
                if info.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with zipped.open(info) as source, path.open('xb') as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
        unpacked.rename(target)
        return target
    finally:
        shutil.rmtree(work)
