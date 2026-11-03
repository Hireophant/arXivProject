"""Unit tests for src/parsing/metrics.py — Khánh / KH3.

Covers:
- Calculation of status counts across all 5 statuses (parsed, empty_no_tex, partial, failed, blocked_input)
- Verification of parse_success_rate, resolved_version_coverage, attempt_coverage
- Zero denominator handling (returning None)
- Duplicate publication detection (raises ValueError)
- Dedup count aggregation across multiple publications
- Atomic writing and schema verification for versions.csv, dedup.csv, and run_summary.json
"""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src.parsing.contracts import (
    CONTRACT_VERSION,
    OUTPUT_SCHEMA_VERSION,
    DedupCount,
    Diagnostic,
    MetricsSummary,
    ParsedPublication,
)
from src.parsing.metrics import summarize, write_metrics


def _make_parsed_pub(
    arxiv_id: str,
    version_states: dict[int, str],
    *,
    export_ready: bool = False,
    diagnostics: list[Diagnostic] | None = None,
    dedup_counts: list[DedupCount] | None = None,
) -> ParsedPublication:
    return ParsedPublication(
        arxiv_id=arxiv_id,
        elements=[],
        hierarchy=[],
        bibtex=[],
        version_states=version_states,
        occurrences=[],
        root_ids={v: f"r{v}" for v in version_states},
        key_map={},
        bib_occurrences=[],
        identity_decisions=[],
        conflicts=[],
        diagnostics=diagnostics or [],
        counts_before_after=dedup_counts or [],
        export_ready=export_ready,
    )


class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m2_metrics_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_summarize_mixed_statuses(self):
        # Pub 1: 2 versions, both parsed, export_ready=True
        p1 = _make_parsed_pub("2606.00001", {1: "parsed", 2: "parsed"}, export_ready=True)

        # Pub 2: 1 version, empty_no_tex, export_ready=True
        p2 = _make_parsed_pub("2606.00002", {1: "empty_no_tex"}, export_ready=True)

        # Pub 3: 3 versions: v1 partial, v2 failed, v3 blocked_input, export_ready=False
        d1 = Diagnostic(code="CITATION_UNRESOLVED", severity="error", message="Unresolved cite", arxiv_id="2606.00003", version=1)
        d2 = Diagnostic(code="ROOT_UNRESOLVED", severity="error", message="No root", arxiv_id="2606.00003", version=2)
        d3 = Diagnostic(code="SOURCE_BLOCKED", severity="error", message="Blocked", arxiv_id="2606.00003", version=3)
        p3 = _make_parsed_pub(
            "2606.00003",
            {1: "partial", 2: "failed", 3: "blocked_input"},
            export_ready=False,
            diagnostics=[d1, d2, d3],
        )

        summary = summarize([p1, p2, p3])

        self.assertEqual(summary.publication_count, 3)
        self.assertEqual(summary.export_ready_publication_count, 2)
        self.assertEqual(len(summary.versions), 6)

        # Counts: parsed=2, empty_no_tex=1, partial=1, failed=1, blocked_input=1
        self.assertEqual(summary.status_counts["parsed"], 2)
        self.assertEqual(summary.status_counts["empty_no_tex"], 1)
        self.assertEqual(summary.status_counts["partial"], 1)
        self.assertEqual(summary.status_counts["failed"], 1)
        self.assertEqual(summary.status_counts["blocked_input"], 1)

        # Rates:
        # parse_success = 2 / (2 + 1 + 1) = 2/4 = 0.5
        self.assertAlmostEqual(summary.parse_success_rate, 0.5)
        # resolved_coverage = (2 + 1) / 6 = 3/6 = 0.5
        self.assertAlmostEqual(summary.resolved_version_coverage, 0.5)
        # attempt_coverage = (2 + 1 + 1) / (6 - 1) = 4/5 = 0.8
        self.assertAlmostEqual(summary.attempt_coverage, 0.8)

        # Check version metrics
        vm_dict = {(vm.arxiv_id, vm.version): vm for vm in summary.versions}
        self.assertEqual(vm_dict[("2606.00001", 1)].status, "parsed")
        self.assertEqual(vm_dict[("2606.00001", 1)].export_ready, True)
        self.assertEqual(vm_dict[("2606.00003", 1)].error_codes, ["CITATION_UNRESOLVED"])
        self.assertEqual(vm_dict[("2606.00003", 2)].error_codes, ["ROOT_UNRESOLVED"])

    def test_zero_denominators(self):
        # 1 version empty_no_tex: attempt and parse_success have 0 denominator
        p = _make_parsed_pub("2606.00001", {1: "empty_no_tex"})
        summary = summarize([p])

        self.assertIsNone(summary.parse_success_rate)
        self.assertIsNone(summary.attempt_coverage)
        self.assertEqual(summary.resolved_version_coverage, 1.0)

        # Empty publications
        empty_summary = summarize([])
        self.assertEqual(empty_summary.publication_count, 0)
        self.assertEqual(len(empty_summary.versions), 0)
        self.assertIsNone(empty_summary.parse_success_rate)
        self.assertIsNone(empty_summary.resolved_version_coverage)
        self.assertIsNone(empty_summary.attempt_coverage)

    def test_duplicate_publication_id_raises(self):
        p1 = _make_parsed_pub("2606.00001", {1: "parsed"})
        p2 = _make_parsed_pub("2606.00001", {1: "parsed"})
        with self.assertRaises(ValueError):
            summarize([p1, p2])

    def test_dedup_aggregation(self):
        p1 = _make_parsed_pub(
            "2606.00001",
            {1: "parsed"},
            dedup_counts=[
                DedupCount(kind="sentence", before=10, after=7),
                DedupCount(kind="figure", before=2, after=2),
            ],
        )
        p2 = _make_parsed_pub(
            "2606.00002",
            {1: "parsed"},
            dedup_counts=[
                DedupCount(kind="sentence", before=20, after=13),
                DedupCount(kind="bibtex", before=5, after=3),
            ],
        )

        summary = summarize([p1, p2])
        dedup_map = {d.kind: d for d in summary.dedup}

        self.assertIn("sentence", dedup_map)
        self.assertEqual(dedup_map["sentence"].before, 30)
        self.assertEqual(dedup_map["sentence"].after, 20)

        self.assertIn("figure", dedup_map)
        self.assertEqual(dedup_map["figure"].before, 2)
        self.assertEqual(dedup_map["figure"].after, 2)

        self.assertIn("bibtex", dedup_map)
        self.assertEqual(dedup_map["bibtex"].before, 5)
        self.assertEqual(dedup_map["bibtex"].after, 3)

    def test_write_metrics_files_and_roundtrip(self):
        p = _make_parsed_pub(
            "2606.00001",
            {1: "parsed", 2: "partial"},
            export_ready=False,
            diagnostics=[Diagnostic(code="CITATION_UNRESOLVED", severity="error", message="err", arxiv_id="2606.00001", version=2)],
            dedup_counts=[DedupCount(kind="sentence", before=10, after=8)],
        )
        summary = summarize([p])
        out_files = write_metrics(summary, self.test_dir, run_id="run_123", snapshot_id="snap_456")

        self.assertEqual(len(out_files), 3)
        v_file = self.test_dir / "versions.csv"
        d_file = self.test_dir / "dedup.csv"
        s_file = self.test_dir / "run_summary.json"

        self.assertTrue(v_file.is_file())
        self.assertTrue(d_file.is_file())
        self.assertTrue(s_file.is_file())

        # Check versions.csv
        with v_file.open("r", encoding="utf-8", newline="") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 2)
            row1 = reader[0]
            self.assertEqual(row1["run_id"], "run_123")
            self.assertEqual(row1["snapshot_id"], "snap_456")
            self.assertEqual(row1["arxiv_id"], "2606.00001")
            self.assertEqual(row1["version"], "1")
            self.assertEqual(row1["status"], "parsed")
            self.assertEqual(row1["export_ready"], "false")

            row2 = reader[1]
            self.assertEqual(row2["version"], "2")
            self.assertEqual(row2["status"], "partial")
            self.assertEqual(json.loads(row2["error_codes"]), ["CITATION_UNRESOLVED"])

        # Check dedup.csv
        with d_file.open("r", encoding="utf-8", newline="") as f:
            reader = list(csv.DictReader(f))
            self.assertEqual(len(reader), 1)
            row = reader[0]
            self.assertEqual(row["kind"], "sentence")
            self.assertEqual(row["before"], "10")
            self.assertEqual(row["after"], "8")
            self.assertAlmostEqual(float(row["reduction"]), 0.2)

        # Check run_summary.json
        data = json.loads(s_file.read_text(encoding="utf-8"))
        self.assertEqual(data["run_id"], "run_123")
        self.assertEqual(data["snapshot_id"], "snap_456")
        self.assertEqual(data["schema_version"], OUTPUT_SCHEMA_VERSION)
        self.assertEqual(data["contract_version"], CONTRACT_VERSION)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["publication_count"], 1)


if __name__ == "__main__":
    unittest.main()
