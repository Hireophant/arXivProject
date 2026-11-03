"""Module metrics.py — Khánh / KH3.

Computes coverage, status counts, success rates, and deduplication reductions
from finalized ParsedPublication records and writes canonical metrics CSV/JSON reports.
"""
from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path

from .contracts import (
    CONTRACT_VERSION,
    OUTPUT_SCHEMA_VERSION,
    DedupCount,
    MetricsSummary,
    ParsedPublication,
    VersionMetric,
)


def summarize(publications: list[ParsedPublication]) -> MetricsSummary:
    """API thuần, nhận kết quả sau finalize, không gọi pipeline hay validator.

    - Chặn trùng lặp arxiv_id (raise ValueError).
    - status_counts đủ 5 statuses kể cả zero.
    - parse_success_rate = parsed / (parsed + partial + failed)
    - resolved_version_coverage = (parsed + empty_no_tex) / expected_versions
    - attempt_coverage = (parsed + partial + failed) / (expected_versions - empty_no_tex)
    - Mẫu số 0 -> None.
    - Dedup theo kind được cộng dồn before/after.
    """
    seen_ids: set[str] = set()
    for pub in publications:
        if pub.arxiv_id in seen_ids:
            raise ValueError(f"Duplicate publication ID detected in metrics: {pub.arxiv_id}")
        seen_ids.add(pub.arxiv_id)

    versions: list[VersionMetric] = []
    for pub in sorted(publications, key=lambda p: p.arxiv_id):
        for v in sorted(pub.version_states.keys()):
            status = pub.version_states[v]
            # Thu thập error_codes liên quan tới version này
            codes = sorted({
                d.code for d in pub.diagnostics
                if (d.version == v or v in d.affected_versions or (d.version is None and not d.affected_versions))
            })
            versions.append(
                VersionMetric(
                    arxiv_id=pub.arxiv_id,
                    version=v,
                    status=status,
                    error_codes=codes,
                    export_ready=pub.export_ready,
                )
            )

    status_counts: dict[str, int] = {
        "parsed": 0,
        "empty_no_tex": 0,
        "partial": 0,
        "failed": 0,
        "blocked_input": 0,
    }
    for vm in versions:
        if vm.status in status_counts:
            status_counts[vm.status] += 1
        else:
            status_counts[vm.status] = 1

    total_versions = len(versions)
    parsed = status_counts["parsed"]
    partial = status_counts["partial"]
    failed = status_counts["failed"]
    empty_no_tex = status_counts["empty_no_tex"]

    denom_attempted = parsed + partial + failed
    parse_success_rate = (parsed / denom_attempted) if denom_attempted > 0 else None

    resolved_version_coverage = ((parsed + empty_no_tex) / total_versions) if total_versions > 0 else None

    denom_non_empty = total_versions - empty_no_tex
    attempt_coverage = (denom_attempted / denom_non_empty) if denom_non_empty > 0 else None

    kind_before: dict[str, int] = {}
    kind_after: dict[str, int] = {}
    for pub in publications:
        for dc in pub.counts_before_after:
            kind_before[dc.kind] = kind_before.get(dc.kind, 0) + dc.before
            kind_after[dc.kind] = kind_after.get(dc.kind, 0) + dc.after

    dedup = [
        DedupCount(kind=k, before=kind_before[k], after=kind_after[k])
        for k in sorted(kind_before.keys())
    ]

    return MetricsSummary(
        versions=versions,
        status_counts=status_counts,
        publication_count=len(publications),
        export_ready_publication_count=sum(1 for p in publications if p.export_ready),
        parse_success_rate=parse_success_rate,
        resolved_version_coverage=resolved_version_coverage,
        attempt_coverage=attempt_coverage,
        dedup=dedup,
    )


def write_metrics(
    summary: MetricsSummary,
    output_dir: Path,
    *,
    run_id: str,
    snapshot_id: str,
) -> list[Path]:
    """Ghi versions.csv, dedup.csv, run_summary.json nguyên tử vào output_dir."""
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    versions_path = out / "versions.csv"
    dedup_path = out / "dedup.csv"
    summary_path = out / "run_summary.json"

    # 1. Ghi versions.csv
    tmp_v = out / ".versions.csv.tmp"
    with tmp_v.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "snapshot_id",
            "arxiv_id",
            "version",
            "status",
            "error_codes",
            "export_ready",
        ])
        for vm in summary.versions:
            writer.writerow([
                run_id,
                snapshot_id,
                vm.arxiv_id,
                vm.version,
                vm.status,
                json.dumps(vm.error_codes, ensure_ascii=False),
                "true" if vm.export_ready else "false",
            ])
    tmp_v.replace(versions_path)

    # 2. Ghi dedup.csv
    tmp_d = out / ".dedup.csv.tmp"
    with tmp_d.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id",
            "snapshot_id",
            "kind",
            "before",
            "after",
            "reduction",
        ])
        for dc in summary.dedup:
            if dc.before > 0:
                reduction_str = f"{(dc.before - dc.after) / dc.before:.6g}"
            else:
                reduction_str = ""
            writer.writerow([
                run_id,
                snapshot_id,
                dc.kind,
                dc.before,
                dc.after,
                reduction_str,
            ])
    tmp_d.replace(dedup_path)

    # 3. Ghi run_summary.json
    tmp_s = out / ".run_summary.json.tmp"
    summary_dict = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "snapshot_id": snapshot_id,
        "summary": asdict(summary),
    }
    with tmp_s.open("w", encoding="utf-8") as f:
        json.dump(summary_dict, f, ensure_ascii=False, indent=2)
    tmp_s.replace(summary_path)

    return [versions_path, dedup_path, summary_path]
