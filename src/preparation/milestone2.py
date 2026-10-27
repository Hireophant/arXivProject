"""Restore M1 backup folders/Drive download ZIPs without crawling or parsing.

Archive and source receipt schemas follow crawling/backup.py and download.py.
This module deliberately uses only stdlib; it does not import the crawler or
require requests/psutil. ZIP/path/hash APIs: docs.python.org/3/library/{zipfile,
pathlib,hashlib}.html. Only one writer may prepare a destination at a time.
"""
from collections import Counter
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
from uuid import uuid4
import zipfile


SCHEMA = "m2-input-1.0"
_CHUNK = 1024 * 1024
_MAX_JSON = 256 * 1024**2
_MAX_FILE = 64 * 1024**2
_MAX_VERSION = 512 * 1024**2
_ID = re.compile(r"(?:[0-9]{4}\.[0-9]{4,5}|[a-zA-Z][a-zA-Z0-9.-]*/[0-9]{7})\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")


def _replace(source, target):
    """Bounded retry for Windows file scanners/sharing locks during publication."""
    for attempt, delay in enumerate((0, .1, .2, .4, .8)):
        if delay:
            time.sleep(delay)
        try:
            os.replace(source, target)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 4:
                raise


def _atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + "." + uuid4().hex + ".part")
    try:
        with pending.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def _write_json(path, value):
    _atomic_bytes(path, _json_bytes(value))


def _load_json(stream, limit=_MAX_JSON):
    # A single read(limit + 1) reserves the whole limit on buffered disk files,
    # even for a 300-byte metadata file. Read bounded chunks instead.
    chunks, size = [], 0
    while chunk := stream.read(min(64 * 1024, limit - size + 1)):
        size += len(chunk)
        if size > limit:
            raise ValueError("JSON exceeds preparation size limit")
        chunks.append(chunk)
    return json.loads(b"".join(chunks))


def _safe_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or ":" in name or any(ord(c) < 32 for c in name)):
        raise ValueError("Unsafe archive path")
    return path


def _safe_members(zipped):
    members, folded = {}, set()
    for info in zipped.infolist():
        _safe_name(info.filename)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError("Archive contains a link or special file")
        if info.is_dir():
            continue
        key = info.filename.casefold()
        if key in folded:
            raise ValueError("Archive contains duplicate/case-colliding paths")
        members[info.filename] = info
        folded.add(key)
    return members


def _no_links(path, checked=None):
    for part in (path, *path.parents):
        if checked is not None and part in checked:
            break  # This ancestor and its parents were checked in this pass.
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Paths through links/junctions are not supported")
        if checked is not None:
            checked.add(part)


class _Store:
    """Uniform read access; nested archives are spooled, never unpacked wholesale."""

    def __init__(self, source):
        original = Path(source).absolute()
        _no_links(original)
        self.source = original.resolve()
        self.outer = None
        if self.source.is_dir():
            names, checked = [], set()
            for p in self.source.rglob("*"):
                _no_links(p, checked)
                if p.is_file() and p.name in {"backup_receipt.json", "corpus.zip"}:
                    names.append(p.relative_to(self.source).as_posix())
            self.names = sorted(names)
        elif self.source.is_file() and zipfile.is_zipfile(self.source):
            self.outer = zipfile.ZipFile(self.source)
            try:
                self.names = sorted(_safe_members(self.outer))
            except BaseException:
                self.outer.close()
                raise
        else:
            raise ValueError("SOURCE_PATH must be a backup folder or a Drive download ZIP")

    def close(self):
        if self.outer:
            self.outer.close()

    def open(self, name):
        _safe_name(name)
        if self.outer:
            return self.outer.open(name)
        path = self.source.joinpath(*PurePosixPath(name).parts)
        _no_links(path)
        if not path.resolve().is_relative_to(self.source):
            raise ValueError("Backup path escapes source")
        return path.open("rb")

    def read_json(self, name):
        with self.open(name) as stream:
            return _load_json(stream)

    @contextmanager
    def corpus(self, name, expected, work):
        if (expected.get("filename") != "corpus.zip"
                or type(expected.get("bytes")) is not int or expected["bytes"] < 0
                or not isinstance(expected.get("sha256"), str)
                or not _HASH.fullmatch(expected["sha256"])):
            raise ValueError("Invalid corpus archive receipt")
        # Streaming to local seekable storage avoids random reads of a Drive ZIP.
        with tempfile.SpooledTemporaryFile(max_size=16 * 1024**2, dir=work) as spool:
            h, size = hashlib.sha256(), 0
            with self.open(name) as stream:
                while chunk := stream.read(_CHUNK):
                    size += len(chunk)
                    if size > expected["bytes"]:
                        raise ValueError("Corpus archive size differs from receipt")
                    h.update(chunk)
                    spool.write(chunk)
            if size != expected["bytes"] or h.hexdigest() != expected["sha256"]:
                raise ValueError("Corpus archive SHA-256/size differs from receipt")
            spool.seek(0)
            with zipfile.ZipFile(spool) as zipped:
                yield zipped, _safe_members(zipped)


def _preview(store):
    receipts = [n for n in store.names if PurePosixPath(n).name == "backup_receipt.json"]
    paired = {str(PurePosixPath(n).parent / "corpus.zip") for n in receipts}
    orphans = [n for n in store.names if PurePosixPath(n).name == "corpus.zip" and n not in paired]
    members = []
    # Queue names are hints for display, not authority for source completeness.
    if store.outer:
        queue_names = [n for n in store.names if "/retry-state/" in "/" + n and n.endswith(".json")]
    else:
        queue_names = [p.relative_to(store.source).as_posix()
                       for p in store.source.rglob("member-*.json") if p.parent.name == "retry-state"]
    for name in queue_names:
        try:
            queue = store.read_json(name)
            members.append(dict(queue=name, member=queue.get("member"),
                                assignment_count=len(queue.get("assignment_ids", [])),
                                pending_count=len(queue.get("pending_ids", []))))
        except (OSError, ValueError, KeyError):
            members.append(dict(queue=name, error="Unreadable retry queue"))
    return dict(source=str(store.source), source_kind="zip" if store.outer else "folder",
                backup_count=len(receipts), receipts=receipts, orphan_corpus_archives=orphans,
                queues=members, verified=False)


def inspect_backups(source):
    """Cheap inventory only. No SHA checks, restoration, network or output writes."""
    store = _Store(source)
    try:
        return _preview(store)
    finally:
        store.close()


def _paper_key(identifier):
    if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
        raise ValueError("Invalid base arXiv ID in manifest")
    digits = identifier.split("/")[-1] if "/" in identifier else identifier.split(".")[0]
    if not 1 <= int(digits[2:4]) <= 12:
        raise ValueError("Invalid arXiv month")
    return identifier.replace(".", "-").replace("/", "-")


def _source_receipt(receipt, identifier, version):
    if (receipt.get("schema_version") != "3.0" or receipt.get("arxiv_id") != identifier
            or type(receipt.get("version")) is not int or receipt["version"] != version
            or receipt.get("source_url") != f"https://export.arxiv.org/src/{identifier}v{version}"):
        raise ValueError("Invalid M1 source receipt identity/schema")
    result, hashes = receipt.get("result", {}), receipt.get("files_sha256")
    if (result.get("arxiv_id") != identifier or type(result.get("version")) is not int
            or result["version"] != version or result.get("status") not in {"success", "no_tex"}
            or not isinstance(hashes, dict) or len(hashes) > 10000):
        raise ValueError("Invalid M1 source receipt payload")
    for name, value in hashes.items():
        path = _safe_name(name)
        if (path.suffix.lower() not in {".tex", ".bib"} or not isinstance(value, str)
                or not _HASH.fullmatch(value)):
            raise ValueError("Invalid source file inventory")
    if result.get("status") == "no_tex":
        if hashes or result.get("source_bytes_after") != 0 or result.get("file_count") != 0:
            raise ValueError("no_tex receipt contains nonempty source")
        if (receipt.get("source_kind") not in {"pdf", "docx", "tar", "gzip-pdf", "gzip-docx", "gzip-tar"}
                or result.get("error") != f"Verified {receipt['source_kind']} source without TeX."):
            raise ValueError("no_tex receipt lacks verified non-TeX evidence")
    elif (not any(PurePosixPath(n).suffix.lower() == ".tex" for n in hashes)
          or result.get("error") is not None
          or receipt.get("source_kind") not in {"tex", "tar", "gzip-tex", "gzip-tar"}):
        raise ValueError("Successful source receipt lacks TeX")
    if (type(result.get("source_bytes_after")) is not int
            or not 0 <= result["source_bytes_after"] <= _MAX_VERSION
            or type(result.get("file_count")) is not int or result["file_count"] != len(hashes)):
        raise ValueError("Invalid source byte/file counts")
    fingerprint = hashlib.sha256(_json_bytes(dict(status=result["status"], files=hashes))).hexdigest()
    return result, hashes, fingerprint


def _valid_local(directory, receipt, checked=None):
    """Rehash current output on every resume; completion markers alone are insufficient."""
    try:
        checked = set() if checked is None else checked
        _no_links(directory, checked)
        if not directory.is_dir():
            return False
        if receipt["result"]["status"] == "no_tex" and any(directory.iterdir()):
            return False
        expected = receipt["files_sha256"]
        actual, size = {}, 0
        for p in directory.rglob("*"):
            _no_links(p, checked)
            if p.is_file():
                if p.stat().st_size > _MAX_FILE:
                    return False
                h = hashlib.sha256()
                with p.open("rb") as stream:
                    while chunk := stream.read(_CHUNK):
                        h.update(chunk)
                        size += len(chunk)
                actual[p.relative_to(directory).as_posix()] = h.hexdigest()
        return actual == expected and size == receipt["result"]["source_bytes_after"]
    except (OSError, ValueError):
        return False


def _copy_source(zipped, info, target=None):
    if info.file_size > _MAX_FILE:
        raise ValueError("Source file exceeds size limit")
    h, size = hashlib.sha256(), 0
    with zipped.open(info) as source, (target.open("wb") if target else nullcontext()) as output:
        while chunk := source.read(_CHUNK):
            size += len(chunk)
            if size > _MAX_FILE:
                raise ValueError("Source file exceeds size limit")
            h.update(chunk)
            if output is not None:
                output.write(chunk)
    return h.hexdigest()


def _restore_version(zipped, members, prefix, target, receipt, work):
    result, hashes, _ = _source_receipt(receipt, receipt["arxiv_id"], receipt["version"])
    present = {n[len(prefix):] for n in members if n.startswith(prefix)}
    if present != set(hashes):
        raise ValueError("Source ZIP members differ from per-version receipt")
    if _valid_local(target, receipt):
        # Backup transport hashes do not prove agreement with source receipts.
        # Verify every candidate even if an identical output copy already exists.
        for name, expected_hash in hashes.items():
            if _copy_source(zipped, members[prefix + name]) != expected_hash:
                raise ValueError("Source file SHA-256 differs from source receipt")
        _write_json(target.parent / f".v{receipt['version']}.receipt.json", receipt)
        return False
    stage = work / ("version-" + uuid4().hex)
    stage.mkdir()
    prepared = stage / "prepared"
    prepared.mkdir()
    old = stage / "previous"
    try:
        for name, expected_hash in hashes.items():
            info = members[prefix + name]
            path = prepared.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            if _copy_source(zipped, info, path) != expected_hash:
                raise ValueError("Source file SHA-256 differs from source receipt")
        if not _valid_local(prepared, receipt):
            raise ValueError("Restored version does not match its source receipt")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            _replace(target, old)
        try:
            _replace(prepared, target)
            _write_json(target.parent / f".v{receipt['version']}.receipt.json", receipt)
        except BaseException:
            if target.exists():
                shutil.rmtree(target)
            if old.exists():
                _replace(old, target)
            raise
        return True
    finally:
        # Only remove the exact owned stage path, never a computed input directory.
        shutil.rmtree(stage)


def _write_csv(path, fields, rows):
    pending = path.with_name(path.name + ".part")
    with pending.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    _replace(pending, path)


def prepare_corpus(source, output, *, progress=None):
    """Restore all discoverable publications/versions; return a truthful summary.

    The completion file is preparation.json. Consumers must check its status,
    matching manifest run_id, and each version_state. This is raw input, not M2
    parser output. Rerunning rechecks archives and repaired/local source bytes.
    """
    source, output = Path(source).absolute(), Path(output).absolute()
    _no_links(output)
    output = output.resolve()
    source_resolved = source.resolve()
    if (output == source_resolved or source_resolved.is_relative_to(output)
            or (source.is_dir() and output.is_relative_to(source_resolved))):
        raise ValueError("M1 source and M2 output must be separate, non-overlapping paths")
    store = _Store(source)
    work = None
    try:
        preview = _preview(store)
        if not preview["backup_count"]:
            raise ValueError("No backup_receipt.json found; choose the full M1 backup folder")
        owner = output / ".prepare-owner.json"
        if output.exists() and any(output.iterdir()):
            if not owner.is_file() or json.loads(owner.read_text(encoding="utf-8")).get("schema_version") != SCHEMA:
                raise ValueError("Destination is nonempty and not owned by this preparer; choose a new dataset folder")
            checked = set()
            for p in output.rglob("*"):
                _no_links(p, checked)
        output.mkdir(parents=True, exist_ok=True)
        _write_json(owner, dict(schema_version=SCHEMA))
        run_id = uuid4().hex
        _write_json(output / "preparation.json", dict(status="in_progress", run_id=run_id, schema_version=SCHEMA))
        work = output / (".prepare-work-" + uuid4().hex)
        work.mkdir()
        papers, selected, conflicts, audit, provenance = {}, {}, set(), [], []
        restored = 0
        for orphan in preview["orphan_corpus_archives"]:
            audit.append(dict(backup=orphan, status="error", code="MISSING_BACKUP_RECEIPT"))
        for number, label in enumerate(preview["receipts"], 1):
            if progress:
                progress(f"[{number}/{preview['backup_count']}] {label}")
            try:
                receipt = store.read_json(label)
                if receipt.get("schema_version") != "1.0":
                    raise ValueError("Unsupported backup receipt schema")
                when = datetime.fromisoformat(receipt["created_at_utc"].replace("Z", "+00:00"))
                if when.tzinfo is None:
                    raise ValueError("Backup timestamp must include timezone")
                stamp = when.astimezone(timezone.utc).isoformat()
                corpus_name = str(PurePosixPath(label).parent / "corpus.zip")
                with store.corpus(corpus_name, receipt["archives"]["corpus"], work) as (zipped, members):
                    with zipped.open("manifest.json") as stream:
                        manifest = _load_json(stream)
                    if manifest.get("schema_version") != "3.0" or manifest.get("run_id") != receipt.get("run_id"):
                        raise ValueError("M1 manifest identity/schema differs from backup receipt")
                    if not isinstance(manifest.get("papers"), dict):
                        raise ValueError("Missing M1 publication records")
                    source_receipts = {n for n in members if re.search(r"/sources/\.v[0-9]+\.receipt\.json$", n)}
                    for identifier, entry in sorted(manifest["papers"].items()):
                        key = _paper_key(identifier)
                        record = entry["record"]
                        versions = record["versions"]
                        if (record.get("arxiv_id") != identifier or not isinstance(versions, list)
                                or not versions or any(type(v) is not int or v < 1 for v in versions)
                                or versions != list(range(1, max(versions) + 1))
                                or record.get("metadata", {}).get("arxiv_id") != identifier):
                            raise ValueError("Invalid publication/version record")
                        paper = papers.setdefault(identifier, dict(record=record, metadata_path=key + "/metadata.json",
                                                    downloads={}, version_states={}, versions=set(), references=None,
                                                    download_evidence={}, download_ranks={},
                                                    metadata_rank=(-1, "", ""), reference_rank=(-1, "", "")))
                        paper["versions"].update(versions)
                        rank = (max(versions), stamp, label)
                        if rank > paper["metadata_rank"]:
                            paper["record"] = record
                            paper["metadata_rank"] = rank
                            _write_json(output / key / "metadata.json", record["metadata"])
                        references = entry.get("references")
                        if isinstance(references, dict):
                            ref_rank = ({"success": 4, "partial": 3, "not_found": 2, "failed": 1}.get(references.get("status"), 0), stamp, label)
                            if ref_rank > paper["reference_rank"]:
                                paper["reference_rank"] = ref_rank
                                paper["references"] = dict(status=references.get("status"), path=key + "/reference_result.json",
                                                           backup=label, pagination_complete=references.get("pagination_complete"))
                                _write_json(output / key / "reference_result.json", references)
                                _write_json(output / key / "references.json", references.get("references", {}))
                                _write_json(output / key / "references_all.json", references.get("all_references", []))
                        for version in versions:
                            version_key = (identifier, version)
                            original = entry.get("downloads", {}).get(str(version))
                            if isinstance(original, dict):
                                download_rank = ({"success": 4, "no_tex": 3, "failed": 2}.get(original.get("status"), 0), stamp, label)
                                if download_rank > paper["download_ranks"].get(str(version), (-1, "", "")):
                                    paper["download_ranks"][str(version)] = download_rank
                                    paper["download_evidence"][str(version)] = dict(result=original, backup=label)
                                provenance.append(dict(arxiv_id=identifier, version=version, backup=label,
                                                       decision="m1_download_record", result=original))
                            rname = f"{key}/sources/.v{version}.receipt.json"
                            if rname not in source_receipts:
                                continue
                            try:
                                with zipped.open(rname) as stream:
                                    source_receipt = _load_json(stream, 8 * 1024**2)
                                result, hashes, fingerprint = _source_receipt(source_receipt, identifier, version)
                                target = output / key / "sources" / f"v{version}"
                                previous = selected.get(version_key)
                                if previous and previous["fingerprint"] != fingerprint:
                                    # Check the conflicting candidate before calling it a real conflict.
                                    conflict_target = work / ("conflict-" + uuid4().hex) / f"v{version}"
                                    _restore_version(zipped, members, f"{key}/sources/v{version}/", conflict_target, source_receipt, work)
                                    conflicts.add(version_key)
                                    provenance.append(dict(arxiv_id=identifier, version=version, backup=label,
                                                           fingerprint=fingerprint, decision="SOURCE_CONFLICT"))
                                    continue
                                copied = _restore_version(zipped, members, f"{key}/sources/v{version}/",
                                                          target, source_receipt, work)
                                restored += int(copied)
                                # _restore_version publishes this candidate's receipt,
                                # including its download timing/attempt evidence.
                                # Identical bytes can still have different receipts.
                                selected[version_key] = dict(fingerprint=fingerprint, backup=label, result=result)
                                provenance.append(dict(arxiv_id=identifier, version=version, backup=label,
                                                       fingerprint=fingerprint, decision="selected" if previous is None else "identical"))
                            except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
                                audit.append(dict(backup=label, arxiv_id=identifier, version=version, status="error",
                                                  code="SOURCE_INVALID", detail=str(error)))
                    audit.append(dict(backup=label, status="verified", code="CORPUS_VERIFIED",
                                      corpus_sha256=receipt["archives"]["corpus"]["sha256"],
                                      kind="source_backup" if source_receipts else "manifest_only",
                                      publications=len(manifest["papers"])))
            except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
                audit.append(dict(backup=label, status="error", code="BACKUP_INVALID", detail=str(error)))

        inventory = []
        for identifier, paper in sorted(papers.items()):
            key = _paper_key(identifier)
            paper["record"]["versions"] = sorted(paper.pop("versions"))
            paper.pop("metadata_rank")
            paper.pop("reference_rank")
            paper.pop("download_ranks")
            for version in paper["record"]["versions"]:
                chosen = selected.get((identifier, version))
                conflict = (identifier, version) in conflicts
                state = ("blocked_input" if conflict or chosen is None else
                         "empty_no_tex" if chosen["result"]["status"] == "no_tex" else "ready_tex")
                reason = "SOURCE_CONFLICT" if conflict else "SOURCE_MISSING_OR_INVALID" if chosen is None else ""
                paper["version_states"][str(version)] = state
                evidence = paper["download_evidence"].get(str(version), {})
                paper["downloads"][str(version)] = chosen["result"] if chosen else evidence.get("result")
                inventory.append(dict(arxiv_id=identifier, version=version, status=state, reason=reason,
                                      source_dir=f"{key}/sources/v{version}" if state != "blocked_input" else "",
                                      backup=chosen["backup"] if chosen else "",
                                      m1_source_status=evidence.get("result", {}).get("status", ""),
                                      m1_error=evidence.get("result", {}).get("error") or "",
                                      source_fingerprint=chosen["fingerprint"] if chosen else ""))
        counts = Counter(row["status"] for row in inventory)
        errors = sum(row["status"] == "error" for row in audit)
        status = "failed" if not papers else "partial" if errors or counts["blocked_input"] else "ready"
        summary = dict(schema_version=SCHEMA, run_id=run_id, status=status, source=str(store.source),
                       output=str(output), paper_count=len(papers), versions_expected=len(inventory),
                       versions_ready_tex=counts["ready_tex"], versions_empty_no_tex=counts["empty_no_tex"],
                       versions_blocked=counts["blocked_input"], backup_count=preview["backup_count"],
                       backup_errors=errors, restored_versions=restored, queues=preview["queues"],
                       completed_at_utc=datetime.now(timezone.utc).isoformat())
        _write_json(output / "manifest.json", dict(schema_version=SCHEMA, run_id=run_id, papers=papers,
                                                  source=str(store.source), preparation_file="preparation.json"))
        fields = ["arxiv_id", "version", "status", "reason", "source_dir", "backup", "source_fingerprint",
                  "m1_source_status", "m1_error"]
        _write_csv(output / "inventory.csv", fields, inventory)
        _write_csv(output / "blocked_versions.csv", fields, [r for r in inventory if r["status"] == "blocked_input"])
        _atomic_bytes(output / "backup_audit.jsonl", b"".join(_json_bytes(r) + b"\n" for r in audit))
        _atomic_bytes(output / "provenance.jsonl", b"".join(_json_bytes(r) + b"\n" for r in provenance))
        # Publish data, then independently read it back from the destination.
        # Consumers check a matching input_validation run_id before handoff.
        _write_json(output / "preparation.json", summary)
        from .validation import validate_prepared_corpus
        if progress:
            progress("Read-back validation: checking saved sources, metadata and provenance...")
        validation = validate_prepared_corpus(output)
        _write_json(output / "input_validation.json", validation)
        summary["input_valid"] = validation["valid"]
        summary["snapshot_id"] = validation["snapshot_id"]
        if not validation["valid"]:
            summary["status"] = "failed"
        _write_json(output / "preparation.json", summary)
        return summary
    finally:
        store.close()
        if work is not None:
            shutil.rmtree(work)
