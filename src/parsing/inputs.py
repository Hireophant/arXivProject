"""Module inputs.py — Khánh / KH1.

Adapter for prepared M1 corpus (schema m2-input-1.0).
Reads validation markers, inventory, and manifest to build typed
PublicationInput and VersionInput structures without network access or
modifying raw corpus files.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .contracts import Diagnostic, PublicationInput, VersionInput, SourceStatus
from src.preparation.validation import validate_prepared_corpus


def _load_manifest_and_inventory(corpus_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[tuple[str, int], dict[str, str]]]:
    manifest_path = corpus_root / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"manifest.json not found in corpus root: {corpus_root}")
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    summary_path = corpus_root / "preparation.json"
    if not summary_path.exists():
        raise ValueError(f"preparation.json not found in corpus root: {corpus_root}")
    with summary_path.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    inventory_path = corpus_root / "inventory.csv"
    if not inventory_path.exists():
        raise ValueError(f"inventory.csv not found in corpus root: {corpus_root}")
    inventory: dict[tuple[str, int], dict[str, str]] = {}
    with inventory_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            inventory[(row["arxiv_id"], int(row["version"]))] = row

    return manifest, summary, inventory


def _build_version_input(
    corpus_root: Path,
    arxiv_id: str,
    version: int,
    state: str,
    inv_row: dict[str, str] | None,
) -> VersionInput:
    status_map: dict[str, SourceStatus] = {
        "ready_tex": "tex",
        "empty_no_tex": "no_tex",
        "blocked_input": "blocked",
    }
    source_status = status_map.get(state)
    if not source_status:
        raise ValueError(f"Unknown input state '{state}' for {arxiv_id} v{version}")

    diagnostics: list[Diagnostic] = []
    source_dir: Path | None = None
    source_fingerprint: str | None = None

    if inv_row:
        source_fingerprint = inv_row.get("source_fingerprint") or None
        rel_dir = inv_row.get("source_dir")
        if rel_dir and source_status in {"tex", "no_tex"}:
            resolved = (corpus_root / rel_dir).resolve()
            corpus_root_resolved = corpus_root.resolve()
            if not resolved.is_relative_to(corpus_root_resolved):
                raise ValueError(f"Source dir {rel_dir} escapes corpus root {corpus_root}")
            source_dir = resolved

        if source_status == "blocked":
            reason = inv_row.get("reason") or "SOURCE_BLOCKED"
            m1_error = inv_row.get("m1_error") or ""
            msg = f"Version {version} is blocked. Reason: {reason}."
            if m1_error:
                msg += f" M1 error: {m1_error}"
            diagnostics.append(
                Diagnostic(
                    code=reason,
                    severity="error",
                    message=msg.strip(),
                    arxiv_id=arxiv_id,
                    version=version,
                    affected_versions=[version],
                )
            )
    else:
        if source_status == "blocked":
            diagnostics.append(
                Diagnostic(
                    code="SOURCE_BLOCKED",
                    severity="error",
                    message=f"Version {version} is blocked with no inventory record.",
                    arxiv_id=arxiv_id,
                    version=version,
                    affected_versions=[version],
                )
            )

    return VersionInput(
        arxiv_id=arxiv_id,
        version=version,
        source_dir=source_dir,
        source_status=source_status,
        source_fingerprint=source_fingerprint,
        diagnostics=diagnostics,
    )


def load_publications(corpus_root: Path) -> list[PublicationInput]:
    """API chính. Đọc raw m2-input-1.0 do notebook prepare tạo.

    1. Gọi preparation.validate_prepared_corpus, đòi valid=True; complete=False vẫn nạp nhưng giữ blocked.
    2. Đối chiếu preparation/input_validation/manifest cùng run và snapshot hiện tại.
    3. Duyệt manifest.papers theo arxiv_id, record.versions tăng dần.
    4. Trả về list[PublicationInput] với đầy đủ expected versions và diagnostics.
    """
    corpus_root = Path(corpus_root).resolve()
    validation = validate_prepared_corpus(corpus_root)
    if not validation.get("valid"):
        raise ValueError(f"Corpus validation failed for {corpus_root}: {validation.get('issues')}")

    run_id = validation.get("run_id")
    snapshot_id = validation.get("snapshot_id")
    if not run_id or not snapshot_id:
        raise ValueError(f"Missing run_id or snapshot_id in validation result: {validation}")

    manifest, _, inventory = _load_manifest_and_inventory(corpus_root)

    publications: list[PublicationInput] = []
    papers = manifest.get("papers", {})

    for arxiv_id, paper in sorted(papers.items()):
        record = paper.get("record", {})
        versions = record.get("versions", [])
        version_states = paper.get("version_states", {})

        version_inputs: list[VersionInput] = []
        for v in sorted(versions):
            state = version_states.get(str(v), "blocked_input")
            inv_row = inventory.get((arxiv_id, v))
            v_input = _build_version_input(corpus_root, arxiv_id, v, state, inv_row)
            version_inputs.append(v_input)

        publications.append(
            PublicationInput(
                arxiv_id=arxiv_id,
                versions=version_inputs,
                snapshot_id=snapshot_id,
                preparation_run_id=run_id,
                corpus_root=corpus_root,
            )
        )

    return publications


def load_version_input(corpus_root: Path, arxiv_id: str, version: int) -> VersionInput:
    """Đọc đúng version_states/inventory của một version đã kiểm."""
    corpus_root = Path(corpus_root).resolve()
    manifest, _, inventory = _load_manifest_and_inventory(corpus_root)
    papers = manifest.get("papers", {})
    if arxiv_id not in papers:
        raise ValueError(f"Publication {arxiv_id} not found in manifest")

    paper = papers[arxiv_id]
    record = paper.get("record", {})
    versions = record.get("versions", [])
    if version not in versions:
        raise ValueError(f"Version {version} not found in publication record for {arxiv_id}")

    version_states = paper.get("version_states", {})
    state = version_states.get(str(version), "blocked_input")
    inv_row = inventory.get((arxiv_id, version))

    return _build_version_input(corpus_root, arxiv_id, version, state, inv_row)
