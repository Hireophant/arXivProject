"""Khang: bounded source downloads and byte-preserving text extraction.

Sequential callers only: do not write the same version directory concurrently.
No TeX compilation, discovery, metadata, or manifest writes occur here.
References: https://info.arxiv.org/help/mimetypes.html and
https://info.arxiv.org/help/api/tou.html (checked 2026-10-15).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import re
import shutil
import tarfile
import tempfile
import time
import zipfile
from xml.etree import ElementTree
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from . import DownloadResult, HttpPolicy, SourceReceipt


# Deliberately finite; larger submissions fail explicitly rather than truncate.
_MAX_ARCHIVE_BYTES = 256 * 1024**2
_MAX_EXPANDED_BYTES = 512 * 1024**2
_MAX_FILE_BYTES = 64 * 1024**2
_MAX_MEMBERS = 10_000
_MAX_METADATA_BYTES = 1024**2
_CHUNK = 64 * 1024
_URL = "https://export.arxiv.org/src/"
_TEX = re.compile(rb"\\(?:documentclass|documentstyle|begin|input|include|section|def|bye)\b")
_KINDS = {"tex", "tar", "pdf", "docx", "gzip-tex", "gzip-tar", "gzip-pdf", "gzip-docx"}


class _SourceError(Exception):
    """Only fixed, non-sensitive diagnostics may be placed in this exception."""


def _validate(arxiv_id: str, version: int, version_dir: Path) -> Path:
    if not isinstance(arxiv_id, str) or not re.fullmatch(
        r"(?:[0-9]{4}\.[0-9]{4,5}|[a-zA-Z][a-zA-Z0-9.-]*/[0-9]{7})", arxiv_id
    ):
        raise ValueError("Expected a base arXiv ID without a version suffix.")
    if type(version) is not int or version < 1:
        raise ValueError("version must be an integer >= 1.")
    try:
        path = Path(version_dir).absolute()
    except (TypeError, ValueError):
        raise ValueError("Invalid version directory.") from None
    if path == Path(path.anchor):
        raise ValueError("The filesystem root is not a version directory.")
    # Reject links/junctions in the whole destination path, including ancestors.
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Destination may not traverse a symlink or junction.")
        if part.exists() and not part.is_dir():
            raise ValueError("Destination and its parents must be directories.")
    return path.resolve()


def _result(arxiv_id: str, version: int) -> DownloadResult:
    return dict(arxiv_id=arxiv_id, version=version, status="failed",
                source_bytes_before=None, source_bytes_after=None,
                archive_bytes=None, file_count=None, elapsed_seconds=0.0,
                attempts=0, used_cache=False, error=None)


def _safe_name(name: str) -> str:
    # A portable subset also prevents NTFS alternate streams and device names.
    if not name or name.startswith("/") or "\\" in name:
        raise _SourceError("Unsafe archive path.")
    parts = [p for p in name.split("/") if p not in ("", ".")]
    for p in parts:
        if (p == ".." or p.endswith((".", " ")) or len(p) > 240
                or any(ord(c) < 32 or c in ':<>"|?*' for c in p)
                or re.fullmatch(r"(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])", p.split(".")[0])):
            raise _SourceError("Unsafe archive path.")
    if len(parts) > 32 or len("/".join(parts)) > 2048:
        raise _SourceError("Archive path exceeds limits.")
    return "/".join(parts)


def _is_text(data: bytes) -> bool:
    if data.startswith((b"%PDF-", b"\x89PNG", b"\xff\xd8\xff", b"GIF87a", b"GIF89a",
                        b"II*\0", b"MM\0*", b"PK\x03\x04", b"\x1f\x8b", b"\x7fELF",
                        b"\xd0\xcf\x11\xe0", b"RIFF", b"BM")):
        return False
    # UTF-8 and legacy 8-bit TeX are kept as bytes, never decoded/re-encoded.
    return not any(c < 32 and c not in (9, 10, 12, 13) for c in data) and b"\x7f" not in data


def _is_tex(data: bytes) -> bool:
    # Ignore comment-only TeX commands when deciding whether this is a source.
    return _is_text(data) and bool(_TEX.search(re.sub(rb"(?m)(?<!\\)%[^\r\n]*", b"", data)))


def _bounded_copy(source, target, limit: int) -> int:
    total = 0
    while chunk := source.read(min(_CHUNK, limit - total + 1)):
        total += len(chunk)
        if total > limit:
            raise _SourceError("Source exceeds the configured byte limit.")
        target.write(chunk)
    return total


def _tar_preflight(path: Path) -> bool:
    """Check raw headers before tarfile can allocate PAX/longname metadata.

    Strict end markers reject truncated archives and concatenated payloads.
    Tar padding/headers are excluded from the source byte measurements.
    """
    size = path.stat().st_size
    with path.open("rb") as stream:
        first = stream.read(512)
        try:
            tarfile.TarInfo.frombuf(first, "utf-8", "surrogateescape")
        except tarfile.HeaderError:
            if first != bytes(512):
                return False
        stream.seek(0)
        count = 0
        while True:
            block = stream.read(512)
            if block == bytes(512):
                if stream.read(512) != bytes(512):
                    raise _SourceError("Truncated tar end markers.")
                while tail := stream.read(_CHUNK):
                    if any(tail):
                        raise _SourceError("Unexpected data after tar end markers.")
                return True
            if len(block) != 512:
                raise _SourceError("Truncated tar header.")
            try:
                info = tarfile.TarInfo.frombuf(block, "utf-8", "surrogateescape")
            except tarfile.HeaderError:
                raise _SourceError("Invalid tar header checksum.") from None
            count += 1
            if count > _MAX_MEMBERS or info.size < 0:
                raise _SourceError("Tar member count or size exceeds limits.")
            metadata = info.type in (tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME,
                                     tarfile.GNUTYPE_LONGLINK)
            if info.size > (_MAX_METADATA_BYTES if metadata else _MAX_FILE_BYTES):
                raise _SourceError("Tar member exceeds the configured byte limit.")
            end = stream.tell() + ((info.size + 511) // 512) * 512
            if end > size:
                raise _SourceError("Truncated tar member.")
            stream.seek(end)


def _extract_tar(path: Path, output: Path) -> tuple[int, bool]:
    before, has_tex, count = 0, False, 0
    seen: dict[str, str] = {}
    files: set[str] = set()
    with tarfile.open(path, mode="r:") as archive:
        for member in archive:
            count += 1
            if count > _MAX_MEMBERS or member.issparse():
                raise _SourceError("Too many members or unsupported sparse tar.")
            if not (member.isfile() or member.isdir()):
                raise _SourceError("Archive links and special files are forbidden.")
            name = _safe_name(member.name)
            if not name:
                if member.isdir():
                    continue
                raise _SourceError("Empty archive filename.")
            parts = name.split("/")
            for i in range(1, len(parts) + 1):
                prefix = "/".join(parts[:i])
                key = prefix.casefold()
                if key in seen and seen[key] != prefix:
                    raise _SourceError("Case-colliding archive paths.")
                seen[key] = prefix
            if name in files or any("/".join(parts[:i]) in files for i in range(1, len(parts))):
                raise _SourceError("Duplicate or conflicting archive paths.")
            target = output.joinpath(*parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if target.is_dir():
                raise _SourceError("Conflicting file and directory paths.")
            files.add(name)
            if member.size < 0 or member.size > _MAX_FILE_BYTES:
                raise _SourceError("Tar member exceeds the configured byte limit.")
            before += member.size
            if before > _MAX_EXPANDED_BYTES:
                raise _SourceError("Expanded source exceeds the configured byte limit.")
            with archive.extractfile(member) as stream:
                data = stream.read(member.size + 1)
            if len(data) != member.size:
                raise _SourceError("Truncated tar member.")
            if _is_text(data):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                has_tex = has_tex or _is_tex(data)
    if not files:
        raise _SourceError("Empty source archive.")
    return before, has_tex


def _verified_pdf(data: bytes) -> bool:
    # Structural identification only, not a full PDF parser or renderer.
    return (bool(re.match(rb"%PDF-[12]\.[0-9]", data))
            and bool(re.search(rb"\d+\s+\d+\s+obj\b", data))
            and bool(re.search(rb"startxref\s+\d+\s+%%EOF\s*$", data)))


def _docx_size(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = {m.filename for m in members}
        if not {"[Content_Types].xml", "word/document.xml"} <= names:
            raise _SourceError("Unsupported ZIP source (not verified Word-only).")
        if len(members) > _MAX_MEMBERS or len(names) != len(members):
            raise _SourceError("Invalid or oversized Word archive.")
        total = 0
        for member in members:
            _safe_name(member.filename)
            total += member.file_size
            if member.file_size > _MAX_FILE_BYTES or total > _MAX_EXPANDED_BYTES:
                raise _SourceError("Word archive exceeds the configured byte limit.")
            # Reading verifies the CRC; none of the ZIP paths are extracted.
            with archive.open(member) as stream:
                data = stream.read(_MAX_FILE_BYTES + 1)
            if len(data) != member.file_size:
                raise _SourceError("Invalid Word archive member.")
            if _is_tex(data):
                raise _SourceError("ZIP contains TeX; unsupported mixed ZIP source.")
        document = archive.read("word/document.xml")
        if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
            raise _SourceError("Unsupported declarations in Word document XML.")
        try:
            root = ElementTree.fromstring(document)
        except ElementTree.ParseError:
            raise _SourceError("Invalid Word document XML.") from None
        if root.tag not in {
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document",
            "{http://purl.oclc.org/ooxml/wordprocessingml/main}document",
        }:
            raise _SourceError("Invalid Word document XML.")
        return total


def _prepare(source: Path, output: Path, work: Path) -> tuple[str, int, bool]:
    path, prefix = source, ""
    with source.open("rb") as stream:
        magic = stream.read(8)
    if magic.startswith(b"\x1f\x8b"):
        path, prefix = work / "expanded", "gzip-"
        with gzip.open(source, "rb") as stream, path.open("wb") as dest:
            _bounded_copy(stream, dest, _MAX_EXPANDED_BYTES)
    if path.stat().st_size > _MAX_EXPANDED_BYTES:
        raise _SourceError("Expanded source exceeds the configured byte limit.")
    if _tar_preflight(path):
        before, has_tex = _extract_tar(path, output)
        return prefix + "tar", before, has_tex
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise _SourceError("Single source exceeds the configured byte limit.")
    data = path.read_bytes()
    if data.startswith(b"PK\x03\x04"):
        return prefix + "docx", _docx_size(path), False
    if _verified_pdf(data):
        return prefix + "pdf", len(data), False
    if _is_tex(data) and not re.match(rb"\s*(?:<!doctype\s+html|<html)", data, re.I):
        # Single-file transport has no trustworthy member name; use main.tex.
        (output / "main.tex").write_bytes(data)
        return prefix + "tex", len(data), True
    raise _SourceError("Unrecognized or damaged source; absence of TeX is not verified.")


def _inventory(directory: Path) -> tuple[dict[str, str], int, bool]:
    hashes, size, has_tex = {}, 0, False
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise _SourceError("Source tree contains a link.")
        if path.is_dir():
            continue
        if not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
            raise _SourceError("Invalid source tree file.")
        size += path.stat().st_size
        if size > _MAX_EXPANDED_BYTES or len(hashes) >= _MAX_MEMBERS:
            raise _SourceError("Source tree exceeds limits.")
        data = path.read_bytes()
        hashes[path.relative_to(directory).as_posix()] = hashlib.sha256(data).hexdigest()
        has_tex = has_tex or _is_tex(data)
    return hashes, size, has_tex


def _publish(output: Path, target: Path, work: Path, version: int,
             receipt: SourceReceipt | None = None) -> None:
    """Stage both items first, replace source then receipt, rollback on errors.

    Directory replacement needs two renames on Windows/POSIX. A process kill
    between them can leave .khang-* backup files; a missing receipt forces a
    fresh download. This is not a concurrent-writer transaction.
    """
    receipt_path = target.parent / f".v{version}.receipt.json"
    staged_receipt = work / "receipt.json"
    if receipt is not None:
        with staged_receipt.open("w", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
    old, old_receipt = work / "previous", work / "previous-receipt"
    installed = False
    try:
        if receipt_path.is_symlink() or (receipt_path.exists() and not receipt_path.is_file()):
            raise _SourceError("Invalid source receipt path.")
        if receipt_path.exists():
            os.replace(receipt_path, old_receipt)
        if target.exists():
            os.replace(target, old)
        os.replace(output, target)
        installed = True
        if receipt is not None:
            os.replace(staged_receipt, receipt_path)
    except BaseException:
        if installed:
            shutil.rmtree(target)
        if old.exists():
            os.replace(old, target)
        if old_receipt.exists():
            os.replace(old_receipt, receipt_path)
        raise


def prepare_source(
    source_path: Path, version_dir: Path, *, arxiv_id: str, version: int,
) -> DownloadResult:
    """Process a local TeX/gzip/tar/PDF/DOCX payload without network access.

    Attempts=0, used_cache=False. Byte counts exclude archive framing, dirs
    and receipts. no_tex commits an empty version directory; failures preserve
    prior output. Successful local writes invalidate any old network receipt.
    Invalid arguments raise ValueError; operational failures return failed.
    """
    target = _validate(arxiv_id, version, version_dir)
    try:
        source = Path(source_path)
        valid = source.is_file()
    except (TypeError, ValueError, OSError):
        valid = False
    if not valid:
        raise ValueError("source_path must be an existing regular file.")
    started, result = time.monotonic(), _result(arxiv_id, version)
    try:
        result["archive_bytes"] = source.stat().st_size
        if result["archive_bytes"] > _MAX_ARCHIVE_BYTES:
            raise _SourceError("Input exceeds the configured download byte limit.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".khang-", dir=target.parent) as temp:
            work = Path(temp)
            output = work / "output"
            output.mkdir()
            kind, before, has_tex = _prepare(source, output, work)
            if not has_tex:
                shutil.rmtree(output)
                output.mkdir()
            hashes, after, _ = _inventory(output)
            _publish(output, target, work, version)
            result.update(status="success" if has_tex else "no_tex",
                          source_bytes_before=before, source_bytes_after=after,
                          file_count=len(hashes),
                          error=None if has_tex else f"Verified {kind} source without TeX.")
    except (_SourceError, OSError, EOFError, tarfile.TarError, zipfile.BadZipFile,
            RuntimeError, UnicodeError) as exc:
        result["error"] = str(exc) if isinstance(exc, _SourceError) else f"Source processing failed ({type(exc).__name__})."
    result["elapsed_seconds"] = time.monotonic() - started
    return result


def _cached(arxiv_id: str, version: int, target: Path) -> DownloadResult | None:
    receipt_path = target.parent / f".v{version}.receipt.json"
    try:
        if (not target.is_dir() or receipt_path.is_symlink()
                or receipt_path.stat().st_size > 4 * _MAX_METADATA_BYTES):
            return None
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        result = receipt["result"]
        if (receipt["schema_version"] != "1.0" or receipt["arxiv_id"] != arxiv_id
                or type(receipt["version"]) is not int or receipt["version"] != version
                or receipt["source_url"] != f"{_URL}{arxiv_id}v{version}"
                or receipt["source_kind"] not in _KINDS
                or set(result) != set(_result(arxiv_id, version))
                or result["arxiv_id"] != arxiv_id or type(result["version"]) is not int
                or result["version"] != version or result["status"] not in {"success", "no_tex"}
                or result["used_cache"] is not False):
            return None
        for key in ("source_bytes_before", "source_bytes_after", "archive_bytes", "file_count", "attempts"):
            if type(result[key]) is not int or result[key] < 0:
                return None
        elapsed = result["elapsed_seconds"]
        if (type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0
                or result["attempts"] < 1
                or result["source_bytes_before"] < result["source_bytes_after"]
                or result["source_bytes_before"] > _MAX_EXPANDED_BYTES
                or not 0 < result["archive_bytes"] <= _MAX_ARCHIVE_BYTES):
            return None
        hashes, size, has_tex = _inventory(target)
        if (hashes != receipt["files_sha256"] or len(hashes) != result["file_count"]
                or size != result["source_bytes_after"]):
            return None
        if result["status"] == "success":
            if not has_tex or result["error"] is not None or receipt["source_kind"].endswith(("pdf", "docx")):
                return None
        elif (hashes or any(target.iterdir()) or receipt["source_kind"].endswith("tex")
              or result["error"] != f"Verified {receipt['source_kind']} source without TeX."):
            return None
        return dict(result, used_cache=True, attempts=0)
    except (OSError, ValueError, KeyError, TypeError, _SourceError, UnicodeError):
        return None


def _validate_policy(policy: HttpPolicy) -> None:
    try:
        for key in ("timeout_seconds", "arxiv_delay_seconds", "s2_delay_seconds", "backoff_cap_seconds"):
            value = policy[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError
        if (policy["timeout_seconds"] == 0 or type(policy["max_attempts"]) is not int
                or policy["max_attempts"] < 1 or not isinstance(policy["user_agent"], str)
                or not policy["user_agent"].strip() or any(ord(c) < 32 for c in policy["user_agent"])):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid HttpPolicy.") from None


def _retry_delay(header: str | None, attempt: int, policy: HttpPolicy) -> float:
    delay = min(2.0 ** min(attempt - 1, 30), policy["backoff_cap_seconds"])
    if header:
        try:
            value = float(header)
        except ValueError:
            try:
                date = parsedate_to_datetime(header)
                value = (date - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                value = -1
        if math.isfinite(value) and value >= 0:
            delay = value  # Retry-After takes precedence over the backoff cap.
    return max(3.0, policy["arxiv_delay_seconds"], delay)


def download_version(
    arxiv_id: str, version: int, version_dir: Path, *, policy: HttpPolicy,
    use_cache: bool = True,
) -> DownloadResult:
    """Download the exact version from export.arxiv.org and commit a receipt.

    The HTTP body is read without automatic Content-Encoding decompression so
    archive_bytes measures downloaded payload bytes. Retries cover transient
    HTTP/transport errors. Redirects are rejected to avoid unversioned sources
    or an unpaced request to another host. No good output is replaced on error.
    """
    target = _validate(arxiv_id, version, version_dir)
    _validate_policy(policy)
    if type(use_cache) is not bool:
        raise ValueError("use_cache must be bool.")
    started, result = time.monotonic(), _result(arxiv_id, version)
    if use_cache and (cached := _cached(arxiv_id, version, target)) is not None:
        cached["elapsed_seconds"] = time.monotonic() - started
        return cached
    url = f"{_URL}{arxiv_id}v{version}"
    wait = max(3.0, policy["arxiv_delay_seconds"])
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".khang-", dir=target.parent) as temp:
            work = Path(temp)
            payload = work / "payload"
            for attempt in range(1, policy["max_attempts"] + 1):
                time.sleep(wait)
                result["attempts"] = attempt
                retry_after = None
                try:
                    with requests.get(url, headers={"User-Agent": policy["user_agent"],
                                                   "Accept-Encoding": "identity"},
                                      stream=True, allow_redirects=False,
                                      timeout=policy["timeout_seconds"]) as response:
                        status = response.status_code
                        if status != 200:
                            result["error"] = f"Source HTTP {status}."
                            if status not in {408, 429, 500, 502, 503, 504}:
                                break
                            retry_after = response.headers.get("Retry-After")
                        else:
                            length = response.headers.get("Content-Length")
                            if length is not None and (not length.isdigit() or int(length) > _MAX_ARCHIVE_BYTES):
                                raise _SourceError("Invalid or oversized HTTP Content-Length.")
                            with payload.open("wb") as stream:
                                response.raw.decode_content = False
                                received = _bounded_copy(response.raw, stream, _MAX_ARCHIVE_BYTES)
                            if length is not None and received != int(length):
                                raise _SourceError("Truncated HTTP payload.")
                            result["archive_bytes"] = received
                            prepared = prepare_source(payload, work / "prepared", arxiv_id=arxiv_id, version=version)
                            result.update({k: v for k, v in prepared.items()
                                           if k not in {"attempts", "elapsed_seconds"}})
                            if result["status"] != "failed":
                                # Derive kind from the validated payload, without repeating extraction.
                                with payload.open("rb") as stream:
                                    compressed = stream.read(2) == b"\x1f\x8b"
                                opener = gzip.open if compressed else open
                                with opener(payload, "rb") as stream:
                                    head = stream.read(512)
                                try:
                                    tarfile.TarInfo.frombuf(head, "utf-8", "surrogateescape")
                                    kind = "tar"
                                except tarfile.HeaderError:
                                    kind = "pdf" if head.startswith(b"%PDF-") else "docx" if head.startswith(b"PK\x03\x04") else "tex"
                                kind = ("gzip-" if compressed else "") + kind
                                hashes, _, _ = _inventory(work / "prepared")
                                result["elapsed_seconds"] = time.monotonic() - started
                                receipt: SourceReceipt = dict(schema_version="1.0", arxiv_id=arxiv_id,
                                    version=version, source_url=url, source_kind=kind,
                                    result=dict(result), files_sha256=hashes)
                                _publish(work / "prepared", target, work, version, receipt)
                            break
                except requests.RequestException:
                    result["error"] = "Source transport request failed."
                # urllib3 raw reads raise errors outside requests' exception hierarchy.
                except requests.packages.urllib3.exceptions.HTTPError:
                    result["error"] = "Source transport stream failed."
                if attempt < policy["max_attempts"]:
                    wait = _retry_delay(retry_after, attempt, policy)
    except (_SourceError, OSError, EOFError, tarfile.TarError, UnicodeError) as exc:
        result.update(status="failed", source_bytes_before=None, source_bytes_after=None,
                      file_count=None, error=str(exc) if isinstance(exc, _SourceError)
                      else f"Source download failed ({type(exc).__name__}).")
    result["elapsed_seconds"] = time.monotonic() - started
    return result
