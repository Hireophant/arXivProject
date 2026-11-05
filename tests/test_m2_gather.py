r"""Unit tests for src/parsing/gather.py — Khánh / KH2.

Covers:
- Safe file reading with UTF-8-SIG / Latin-1 strict fallback and SHA256 integrity
- Root discovery with comment filtering (% vs escaped \%), directory traversal safety, ambiguity detection
- Recursive include traversal (S1: 3-level include, commented include, unused file exclusion)
- Repeated includes with separate flat source spans
- Cycle detection without global visited-set (allowing sequential repetitions)
- Missing include handling with diagnostic and partial status
- Bibliography declaration extraction (\\bibliography, \\addbibresource)
- gather_version integration across tex, no_tex, blocked, and failed roots (S8, S9)
"""
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from src.parsing.contracts import VersionInput, Diagnostic
from src.parsing.gather import find_root, read_source, expand_includes, gather_version


class TestGather(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="m2_gather_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _make_version(self, status="tex", source_dir=None, version=1, arxiv_id="2606.20274"):
        return VersionInput(
            arxiv_id=arxiv_id,
            version=version,
            source_dir=source_dir if source_dir is not None else self.test_dir,
            source_status=status,
            source_fingerprint="synth_fp",
        )

    # -------------------------------------------------------------------------
    # 1. read_source
    # -------------------------------------------------------------------------
    def test_read_source_utf8_sig_and_latin1(self):
        # UTF-8 with BOM
        utf8_bom = b"\xef\xbb\xbfHello UTF-8 BOM"
        (self.test_dir / "bom.tex").write_bytes(utf8_bom)
        text, sf = read_source(self.test_dir, "bom.tex")
        self.assertEqual(text, "Hello UTF-8 BOM")
        self.assertEqual(sf.encoding, "utf-8-sig")
        self.assertEqual(sf.sha256, hashlib.sha256(utf8_bom).hexdigest())

        # Latin-1 strict
        latin1_bytes = "Café au lait".encode("latin-1")
        (self.test_dir / "latin1.tex").write_bytes(latin1_bytes)
        text_l, sf_l = read_source(self.test_dir, "latin1.tex")
        self.assertEqual(text_l, "Café au lait")
        self.assertEqual(sf_l.encoding, "latin-1")

    def test_read_source_path_escape_raises(self):
        with self.assertRaises(ValueError):
            read_source(self.test_dir, "../outside.tex")

    # -------------------------------------------------------------------------
    # 2. find_root
    # -------------------------------------------------------------------------
    def test_find_root_simple_and_comments(self):
        # Single active root
        (self.test_dir / "main.tex").write_text(
            "% \\documentclass{draft}\n\\documentclass{article}\n\\begin{document}Hello\\end{document}\n",
            encoding="utf-8"
        )
        root = find_root(self.test_dir)
        self.assertEqual(root, "main.tex")

    def test_find_root_escaped_percent(self):
        # Escaped percent makes \\documentclass active
        (self.test_dir / "escaped.tex").write_text(
            "\\%\\documentclass{article}\n\\begin{document}Escaped\\end{document}\n",
            encoding="utf-8"
        )
        root = find_root(self.test_dir)
        self.assertEqual(root, "escaped.tex")

    def test_find_root_in_subfolder(self):
        sub = self.test_dir / "src"
        sub.mkdir()
        (sub / "root.tex").write_text(
            "\\documentclass{report}\n\\begin{document}Sub\\end{document}\n",
            encoding="utf-8"
        )
        root = find_root(self.test_dir)
        self.assertEqual(root, "src/root.tex")

    def test_find_root_no_root_raises(self):
        (self.test_dir / "chunk.tex").write_text("Just a chunk without documentclass", encoding="utf-8")
        with self.assertRaises(ValueError):
            find_root(self.test_dir)

    def test_find_root_multiple_candidates_raises(self):
        (self.test_dir / "root1.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
        (self.test_dir / "root2.tex").write_text("\\documentclass{book}\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            find_root(self.test_dir)

    def test_documentclass_in_included_preamble_selects_unique_document_owner(self):
        (self.test_dir/'sections').mkdir()
        (self.test_dir/'sections/packages.tex').write_text(r'\documentclass{article}\usepackage{amsmath}',encoding='utf-8')
        (self.test_dir/'paper.tex').write_text(r'\input{sections/packages}\begin{document}Actual body.\end{document}',encoding='utf-8')
        self.assertEqual(find_root(self.test_dir),'paper.tex')
        gathered=gather_version(self._make_version())
        self.assertIn('Actual body.',gathered.latex)
        self.assertIn(r'\documentclass{article}',gathered.latex)

    def test_two_documents_sharing_a_preamble_remain_ambiguous(self):
        (self.test_dir/'packages.tex').write_text(r'\documentclass{article}',encoding='utf-8')
        for name in ('paper.tex','supplement.tex'):
            (self.test_dir/name).write_text(r'\input{packages}\begin{document}Body.\end{document}',encoding='utf-8')
        with self.assertRaises(ValueError):find_root(self.test_dir)

    def test_literal_documentclass_example_does_not_create_a_second_root(self):
        (self.test_dir/'paper.tex').write_text(r'\documentclass{article}\begin{document}Body.\end{document}',encoding='utf-8')
        (self.test_dir/'example.tex').write_text(r'\verb|\documentclass{fake}|',encoding='utf-8')
        self.assertEqual(find_root(self.test_dir),'paper.tex')

    def test_documentclass_options_and_comment_before_class_name(self):
        for command in ('\\documentclass[12pt]{article}',
                        '\\documentclass[a4paper,twocolumn]% note\n{article}'):
            with self.subTest(command=command):
                (self.test_dir/'paper.tex').write_text(command+r'\begin{document}Body.\end{document}',encoding='utf-8')
                self.assertEqual(find_root(self.test_dir),'paper.tex')

    # -------------------------------------------------------------------------
    # 3. expand_includes (S1, repeated, cycle, missing)
    # -------------------------------------------------------------------------
    def test_s1_multifile_and_unused_files(self):
        # 3 levels: main.tex -> ch1.tex -> sec1.tex
        (self.test_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n\\input{ch1}\n% \\input{commented}\n\\end{document}\n",
            encoding="utf-8"
        )
        (self.test_dir / "ch1.tex").write_text(
            "Chapter 1:\n\\input{sec1.tex}\n",
            encoding="utf-8"
        )
        (self.test_dir / "sec1.tex").write_text(
            "Section 1.1 content.",
            encoding="utf-8"
        )
        # Unused file and commented file
        (self.test_dir / "commented.tex").write_text("Should not be parsed", encoding="utf-8")
        (self.test_dir / "unused.tex").write_text("Unused file", encoding="utf-8")

        v = self._make_version()
        res = expand_includes(v, "main.tex")

        self.assertEqual(res.status, "ready")
        self.assertIn("Chapter 1:", res.latex)
        self.assertIn("Section 1.1 content.", res.latex)
        self.assertNotIn("Should not be parsed", res.latex)
        self.assertNotIn("Unused file", res.latex)

        # Check source_files: main.tex, ch1.tex, sec1.tex
        file_paths = {sf.path for sf in res.source_files}
        self.assertEqual(file_paths, {"main.tex", "ch1.tex", "sec1.tex"})

        # Check source spans
        self.assertTrue(len(res.source_map) >= 3)
        # Verify that sec1 content in flattened latex corresponds to a SourceSpan with path="sec1.tex"
        sec1_spans = [s for s in res.source_map if s.path == "sec1.tex"]
        self.assertTrue(len(sec1_spans) > 0)
        span = sec1_spans[0]
        self.assertEqual(res.latex[span.flat_start:span.flat_end], "Section 1.1 content.")

    def test_repeated_include_distinct_spans(self):
        (self.test_dir / "main.tex").write_bytes(
            b"\\documentclass{article}\n\\begin{document}\n\\input{part}\nMiddle text\n\\input{part}\n\\end{document}\n"
        )
        (self.test_dir / "part.tex").write_bytes(b"Repeated content\n")

        v = self._make_version()
        res = expand_includes(v, "main.tex")

        self.assertEqual(res.status, "ready")
        part_spans = [s for s in res.source_map if s.path == "part.tex"]
        self.assertEqual(len(part_spans), 2)
        # Both spans refer to the same part.tex range
        self.assertEqual(part_spans[0].start, part_spans[1].start)
        self.assertEqual(part_spans[0].end, part_spans[1].end)
        # But have different flat ranges
        self.assertNotEqual(part_spans[0].flat_start, part_spans[1].flat_start)
        self.assertEqual(res.latex[part_spans[0].flat_start:part_spans[0].flat_end], "Repeated content\n")
        self.assertEqual(res.latex[part_spans[1].flat_start:part_spans[1].flat_end], "Repeated content\n")

    def test_include_cycle_detected(self):
        (self.test_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\n\\input{a}\n\\end{document}\n",
            encoding="utf-8"
        )
        (self.test_dir / "a.tex").write_text("In A\n\\input{b}\n", encoding="utf-8")
        (self.test_dir / "b.tex").write_text("In B\n\\input{a}\n", encoding="utf-8")

        v = self._make_version()
        res = expand_includes(v, "main.tex")

        self.assertEqual(res.status, "partial")
        cycle_diags = [d for d in res.diagnostics if d.code == "INCLUDE_CYCLE"]
        self.assertEqual(len(cycle_diags), 1)
        self.assertIn("cycle", cycle_diags[0].message.lower())

    def test_missing_include_handled(self):
        (self.test_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nBody text\n\\input{missing}\n\\end{document}\n",
            encoding="utf-8"
        )
        v = self._make_version()
        res = expand_includes(v, "main.tex")

        self.assertEqual(res.status, "partial")
        missing_diags = [d for d in res.diagnostics if d.code == "INCLUDE_MISSING"]
        self.assertEqual(len(missing_diags), 1)

    def test_bibliography_locations(self):
        (self.test_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\nText\n"
            "\\bibliography{refs,other}\n"
            "\\addbibresource{extra.bib}\n"
            "\\end{document}\n",
            encoding="utf-8"
        )
        (self.test_dir / "refs.bib").write_text("@article{a, title={T}}\n", encoding="utf-8")
        # other.bib is missing; extra.bib exists
        (self.test_dir / "extra.bib").write_text("@book{b, title={E}}\n", encoding="utf-8")

        v = self._make_version()
        res = expand_includes(v, "main.tex")

        self.assertEqual(len(res.bib_paths), 3)
        bib_dict = {b.path: b for b in res.bib_paths}
        self.assertIn("refs.bib", bib_dict)
        self.assertTrue(bib_dict["refs.bib"].exists)
        self.assertEqual(bib_dict["refs.bib"].kind, "bib")

        self.assertIn("other.bib", bib_dict)
        self.assertFalse(bib_dict["other.bib"].exists)

        self.assertIn("extra.bib", bib_dict)
        self.assertTrue(bib_dict["extra.bib"].exists)

    # -------------------------------------------------------------------------
    # 4. gather_version
    # -------------------------------------------------------------------------
    def test_gather_version_tex_success(self):
        (self.test_dir / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}Working\\end{document}\n",
            encoding="utf-8"
        )
        v = self._make_version(status="tex")
        res = gather_version(v)
        self.assertEqual(res.status, "ready")
        self.assertEqual(res.root_path, "main.tex")
        self.assertIn("Working", res.latex)

    def test_gather_version_no_tex(self):
        v = self._make_version(status="no_tex", source_dir=None)
        res = gather_version(v)
        self.assertEqual(res.status, "empty_no_tex")
        self.assertIsNone(res.root_path)
        self.assertEqual(res.latex, "")
        self.assertEqual(len(res.source_map), 0)

    def test_gather_version_blocked(self):
        v = self._make_version(status="blocked", source_dir=None)
        v.diagnostics.append(Diagnostic(code="SOURCE_BLOCKED", severity="error", message="Blocked", arxiv_id=v.arxiv_id))
        res = gather_version(v)
        self.assertEqual(res.status, "blocked_input")
        self.assertIsNone(res.root_path)
        self.assertEqual(len(res.diagnostics), 1)

    def test_gather_version_failed_root(self):
        # Empty dir, no root
        v = self._make_version(status="tex")
        res = gather_version(v)
        self.assertEqual(res.status, "failed")
        self.assertIsNone(res.root_path)
        self.assertTrue(any(d.code == "ROOT_UNRESOLVED" for d in res.diagnostics))


if __name__ == "__main__":
    unittest.main()
