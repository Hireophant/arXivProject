"""Unit tests for src/parsing/inputs.py — Khánh / KH1.

Covers:
- Loading prepared corpus (schema m2-input-1.0) via load_publications
- Handling mixed statuses (ready_tex, empty_no_tex, blocked_input) per S8
- Preserving all expected versions, diagnostics for blocked inputs
- Preservation of legacy slash arXiv IDs
- Standalone load_version_input calls and error handling on invalid corpus
"""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4

from src.parsing.contracts import PublicationInput, VersionInput, Diagnostic
from src.parsing.inputs import load_publications, load_version_input
from src.preparation.milestone2 import prepare_corpus
from tests.test_m2_preparation import backup, TEX


class TestInputsAdapter(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m2_inputs_test_"))
        self.source_dir = self.test_dir / "Milestone1"
        self.source_dir.mkdir(parents=True)
        self.output_dir = self.test_dir / "preparationM2" / "raw_m1" / "Dataset1"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_publications_valid_corpus(self):
        # 1 paper, 2 versions, both with TeX
        paper_id = "2606.20274"
        backup(self.source_dir, "backup1", versions=(1, 2), sources={1: TEX, 2: TEX}, identifier=paper_id)
        prepare_corpus(self.source_dir, self.output_dir)

        publications = load_publications(self.output_dir)
        self.assertEqual(len(publications), 1)
        pub = publications[0]
        self.assertEqual(pub.arxiv_id, paper_id)
        self.assertEqual(len(pub.versions), 2)
        self.assertTrue(pub.snapshot_id)
        self.assertTrue(pub.preparation_run_id)
        self.assertEqual(pub.corpus_root, self.output_dir)

        v1 = pub.versions[0]
        self.assertEqual(v1.version, 1)
        self.assertEqual(v1.source_status, "tex")
        self.assertIsNotNone(v1.source_dir)
        self.assertTrue(v1.source_dir.exists())
        self.assertTrue((v1.source_dir / "main.tex").exists())
        self.assertTrue(v1.source_fingerprint)
        self.assertEqual(len(v1.diagnostics), 0)

        v2 = pub.versions[1]
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.source_status, "tex")

    def test_s8_mixed_versions_blocked_and_empty(self):
        # S8 test case: v1 has TeX, v2 is verified no_tex, v3 is missing/blocked
        paper_id = "2606.20274"
        backup(self.source_dir, "backup_s8", versions=(1, 2, 3), sources={1: TEX, 2: None}, identifier=paper_id)
        prepare_corpus(self.source_dir, self.output_dir)

        publications = load_publications(self.output_dir)
        self.assertEqual(len(publications), 1)
        pub = publications[0]
        self.assertEqual(len(pub.versions), 3)

        # v1: tex
        v1 = pub.versions[0]
        self.assertEqual(v1.version, 1)
        self.assertEqual(v1.source_status, "tex")
        self.assertIsNotNone(v1.source_dir)

        # v2: empty_no_tex -> source_status "no_tex"
        v2 = pub.versions[1]
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.source_status, "no_tex")

        # v3: missing/blocked -> source_status "blocked"
        v3 = pub.versions[2]
        self.assertEqual(v3.version, 3)
        self.assertEqual(v3.source_status, "blocked")
        self.assertIsNone(v3.source_dir)
        self.assertTrue(len(v3.diagnostics) > 0)
        self.assertEqual(v3.diagnostics[0].severity, "error")
        self.assertEqual(v3.diagnostics[0].arxiv_id, paper_id)
        self.assertEqual(v3.diagnostics[0].version, 3)

    def test_legacy_slash_arxiv_id(self):
        # Legacy arXiv ID containing slash
        paper_id = "math/0102003"
        backup(self.source_dir, "backup_slash", versions=(1,), sources={1: TEX}, identifier=paper_id)
        prepare_corpus(self.source_dir, self.output_dir)

        publications = load_publications(self.output_dir)
        self.assertEqual(len(publications), 1)
        pub = publications[0]
        self.assertEqual(pub.arxiv_id, paper_id)
        v1 = pub.versions[0]
        self.assertEqual(v1.arxiv_id, paper_id)
        self.assertEqual(v1.source_status, "tex")
        self.assertTrue(v1.source_dir.exists())

    def test_load_version_input_standalone(self):
        paper_id = "2606.20274"
        backup(self.source_dir, "backup_single", versions=(1, 2), sources={1: TEX, 2: None}, identifier=paper_id)
        prepare_corpus(self.source_dir, self.output_dir)

        v1 = load_version_input(self.output_dir, paper_id, 1)
        self.assertEqual(v1.version, 1)
        self.assertEqual(v1.source_status, "tex")

        v2 = load_version_input(self.output_dir, paper_id, 2)
        self.assertEqual(v2.version, 2)
        self.assertEqual(v2.source_status, "no_tex")

        # Requesting a version not in record raises ValueError
        with self.assertRaises(ValueError):
            load_version_input(self.output_dir, paper_id, 99)

        # Requesting unknown paper raises ValueError
        with self.assertRaises(ValueError):
            load_version_input(self.output_dir, "non.existent.id", 1)

    def test_invalid_corpus_raises(self):
        # Empty non-corpus directory
        empty_dir = self.test_dir / "empty_corpus"
        empty_dir.mkdir()
        with self.assertRaises(ValueError):
            load_publications(empty_dir)


if __name__ == "__main__":
    unittest.main()
