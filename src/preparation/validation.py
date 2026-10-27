"""Read back the saved raw corpus before handing it to an M2 parser."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath

from .milestone2 import SCHEMA, _json_bytes, _load_json, _no_links, _paper_key, _safe_name, _source_receipt, _valid_local


def validate_prepared_corpus(root):
    """Return integrity, completeness and a reproducible content snapshot ID.

    This is read-only and rehashes source bytes. A partial corpus can be valid:
    known blocked versions remain in coverage, never promoted to parseable.
    Snapshot identity excludes absolute locations, run IDs and timestamps.
    """
    root = Path(root).absolute()
    issues, snapshots, expected = [], [], {}
    checked_paths = set()  # Scoped to one read-back pass; never reused across runs.
    result = dict(valid=False, complete=False, run_id=None, snapshot_id=None, issues=issues)

    def issue(code, detail, identifier=None, version=None):
        issues.append(dict(code=code, detail=str(detail), arxiv_id=identifier, version=version))

    def read(relative):
        parts = _safe_name(relative).parts
        target = root.joinpath(*parts)
        _no_links(target, checked_paths)
        if not target.is_relative_to(root):
            raise ValueError("Artifact path escapes prepared corpus")
        with target.open("rb") as stream:
            return _load_json(stream)

    try:
        _no_links(root, checked_paths)
        root = root.resolve()
        summary, manifest = read("preparation.json"), read("manifest.json")
        if (summary.get("schema_version") != SCHEMA or manifest.get("schema_version") != SCHEMA
                or not summary.get("run_id") or summary["run_id"] != manifest.get("run_id")):
            issue("RUN_ID_MISMATCH", "Schema/run_id must match the completion marker")
            return result
        result["run_id"] = summary["run_id"]
        if summary.get("status") not in {"ready", "partial"}:
            issue("INCOMPLETE_RUN", "Preparation must finish before parser handoff")
            return result
        papers = manifest["papers"]
        if not isinstance(papers, dict) or not papers:
            raise ValueError("Prepared manifest has no publications")
        inventory_path = root / "inventory.csv"
        _no_links(inventory_path, checked_paths)
        with inventory_path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        inventory = {}
        for row in rows:
            key = (row["arxiv_id"], int(row["version"]))
            if key in inventory or row["version"] != str(key[1]):
                issue("INVENTORY_MISMATCH", "Duplicate/noncanonical inventory version")
            inventory[key] = row

        for identifier, paper in sorted(papers.items()):
            try:
                key = _paper_key(identifier)
                record, states = paper["record"], paper["version_states"]
                versions = record["versions"]
                if (record.get("arxiv_id") != identifier or not isinstance(versions, list) or not versions
                        or any(type(v) is not int or v < 1 for v in versions)
                        or versions != list(range(1, max(versions) + 1))
                        or set(states) != {str(v) for v in versions}):
                    raise ValueError("Invalid expected publication/version states")
                snapshot = dict(arxiv_id=identifier, record=record, versions=[], references=None)
                try:
                    if paper["metadata_path"] != key + "/metadata.json" or read(paper["metadata_path"]) != record["metadata"]:
                        raise ValueError("Saved metadata differs from publication record")
                except (OSError, ValueError, KeyError, TypeError) as error:
                    issue("METADATA_INTEGRITY", error, identifier)
                references = paper.get("references")
                if references is not None:
                    try:
                        if references["path"] != key + "/reference_result.json":
                            raise ValueError("Unexpected reference result path")
                        reference_result = read(references["path"])
                        kept, all_refs = read(key + "/references.json"), read(key + "/references_all.json")
                        if (kept != reference_result.get("references", {})
                                or all_refs != reference_result.get("all_references", [])
                                or references.get("status") != reference_result.get("status")
                                or reference_result.get("arxiv_id") != identifier):
                            raise ValueError("Reference artifacts disagree with selected M1 result")
                        snapshot["references"] = reference_result
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        issue("REFERENCE_INTEGRITY", error, identifier)
                for version in versions:
                    state = states[str(version)]
                    if state not in {"ready_tex", "empty_no_tex", "blocked_input"}:
                        raise ValueError("Unknown input state")
                    expected[(identifier, version)] = state
                    row = inventory.get((identifier, version), {})
                    if row.get("status") != state:
                        issue("INVENTORY_MISMATCH", "Inventory/state disagree", identifier, version)
                    node = dict(version=version, state=state)
                    if state == "blocked_input":
                        if row.get("source_dir") or not row.get("reason"):
                            issue("INVENTORY_MISMATCH", "Blocked version must retain reason and no usable path", identifier, version)
                        node["reason"] = row.get("reason")
                    else:
                        try:
                            source_dir = f"{key}/sources/v{version}"
                            if row.get("source_dir") != source_dir:
                                raise ValueError("Unexpected source directory")
                            receipt = read(f"{key}/sources/.v{version}.receipt.json")
                            download, _, fingerprint = _source_receipt(receipt, identifier, version)
                            target = root.joinpath(*PurePosixPath(source_dir).parts)
                            _no_links(target, checked_paths)
                            if (not _valid_local(target, receipt, checked_paths) or fingerprint != row.get("source_fingerprint")
                                    or (download["status"] == "success") != (state == "ready_tex")
                                    or paper["downloads"][str(version)] != download):
                                raise ValueError("Saved source/receipt/fingerprint/state do not agree")
                            node["fingerprint"] = fingerprint
                        except (OSError, ValueError, KeyError, TypeError) as error:
                            issue("SOURCE_INTEGRITY", error, identifier, version)
                    snapshot["versions"].append(node)
                # Store only a digest of a publication's references, not a second
                # in-memory copy of the entire group's reference metadata.
                snapshot["references"] = hashlib.sha256(_json_bytes(snapshot["references"])).hexdigest()
                snapshots.append(snapshot)
            except (OSError, ValueError, KeyError, TypeError) as error:
                issue("PUBLICATION_CONTRACT", error, identifier)
        if set(inventory) != set(expected):
            issue("INVENTORY_MISMATCH", "Inventory must cover exactly every expected publication/version")
        counts = Counter(expected.values())
        for field, count in (("paper_count", len(papers)), ("versions_expected", len(expected)),
                             ("versions_ready_tex", counts["ready_tex"]),
                             ("versions_empty_no_tex", counts["empty_no_tex"]),
                             ("versions_blocked", counts["blocked_input"])):
            if summary.get(field) != count:
                issue("SUMMARY_MISMATCH", field)
        audit_path = root / "backup_audit.jsonl"
        provenance_path = root / "provenance.jsonl"
        _no_links(audit_path, checked_paths)
        _no_links(provenance_path, checked_paths)
        with audit_path.open(encoding="utf-8") as stream:
            audit_errors = sum(json.loads(line).get("status") == "error" for line in stream if line.strip())
        if summary.get("backup_errors") != audit_errors:
            issue("AUDIT_INTEGRITY", "Inconsistent backup error counts")
        try:
            source_evidence, download_evidence = set(), set()
            with provenance_path.open(encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("Provenance entries must be objects")
                    identifier, version = event.get("arxiv_id"), event.get("version")
                    backup, decision = event.get("backup"), event.get("decision")
                    if (type(version) is not int or (identifier, version) not in expected
                            or not isinstance(backup, str) or not backup):
                        raise ValueError("Provenance identity/backup is invalid")
                    if decision in {"selected", "identical", "SOURCE_CONFLICT"}:
                        fingerprint = event.get("fingerprint")
                        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
                            raise ValueError("Provenance fingerprint is invalid")
                        if decision != "SOURCE_CONFLICT":
                            source_evidence.add((identifier, version, backup, fingerprint))
                    elif decision == "m1_download_record":
                        download = event.get("result")
                        if not isinstance(download, dict):
                            raise ValueError("Provenance download evidence is invalid")
                        download_evidence.add((identifier, version, backup, hashlib.sha256(_json_bytes(download)).hexdigest()))
                    else:
                        raise ValueError("Unknown provenance decision")
            for pair, state in expected.items():
                if state == "blocked_input":
                    continue
                row = inventory[pair]
                if (*pair, row["backup"], row["source_fingerprint"]) not in source_evidence:
                    raise ValueError("Usable version lacks matching selected-source provenance")
            for identifier, paper in papers.items():
                for version, evidence in paper.get("download_evidence", {}).items():
                    h = hashlib.sha256(_json_bytes(evidence["result"])).hexdigest()
                    if (identifier, int(version), evidence["backup"], h) not in download_evidence:
                        raise ValueError("Selected M1 failure/download evidence is missing from provenance")
        except (OSError, ValueError, KeyError, TypeError) as error:
            issue("AUDIT_INTEGRITY", error)
        if summary["status"] == "ready" and (counts["blocked_input"] or audit_errors):
            issue("SUMMARY_MISMATCH", "A ready corpus cannot contain blocked versions or backup errors")
        snapshot_id = hashlib.sha256(_json_bytes(snapshots)).hexdigest()
        if summary.get("snapshot_id") is not None and summary["snapshot_id"] != snapshot_id:
            issue("SNAPSHOT_MISMATCH", "Saved content changed after the preparation snapshot was signed")
        if not issues:
            result.update(valid=True, complete=summary["status"] == "ready",
                          snapshot_id=snapshot_id,
                          paper_count=len(papers), versions_expected=len(expected),
                          versions_ready_tex=counts["ready_tex"], versions_empty_no_tex=counts["empty_no_tex"],
                          versions_blocked=counts["blocked_input"])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        issue("INPUT_CONTRACT", error)
    return result
