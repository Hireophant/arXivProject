import tempfile
import unittest
from pathlib import Path

from src.parsing.bibliography import extract_entries, parse_bibitems, parse_bibtex
from src.parsing.contracts import BibliographyBlock, SourceSpan
from tests.m2_support.fixtures import PAPER, make_gathered, make_raw_tree


class BibliographyTests(unittest.TestCase):
    def test_nested_braces_macros_and_missing_fields(self):
        text = '@string{prefix = "Deep"}\n@article{a, title={A {Nested} Title}, author={{Research and Development Lab} and An Nguyen}, year={2020}, doi={10.1/x}}\n@book{b, title=prefix # " Study"}'
        result = parse_bibtex(text, arxiv_id=PAPER, version=1, path="refs.bib", source_fingerprint="f")
        self.assertEqual(len(result.occurrences), 2)
        first, second = (o.entry for o in result.occurrences)
        self.assertEqual(first.title, "A {Nested} Title")
        self.assertEqual(first.authors, ["Research and Development Lab", "An Nguyen"])
        self.assertEqual(first.year, 2020)
        self.assertEqual(second.title, "Deep Study")
        self.assertIsNone(second.year)
        self.assertEqual(second.authors, [])
        self.assertTrue(result.occurrences[0].occurrence_id.startswith("2606-20274#bib-v1-"))

    def test_bibitem_optional_label_and_bad_entry(self):
        result = parse_bibitems(r'\bibitem[1]{old} An Nguyen and Binh Tran. "A title". 2021. doi:10.2/x'
                                '\n' r'\bibitem[broken] no key',
                                arxiv_id=PAPER, version=1,
                                source_spans=[SourceSpan(path="main.tex", start=50, end=140)],
                                source_fingerprint="f")
        self.assertEqual(result.occurrences[0].original_key, "old")
        self.assertEqual(result.occurrences[0].entry.year, 2021)
        self.assertEqual(result.occurrences[0].entry.authors, ["An Nguyen", "Binh Tran"])
        self.assertEqual(result.occurrences[0].entry.doi, "10.2/x")
        self.assertIsNone(result.occurrences[1].entry)
        self.assertEqual(result.diagnostics[0].code, "BIB_ENTRY_UNPARSED")

    def test_crossref_and_literal_hash(self):
        text = '@proceedings{parent, author={An Nguyen}, year={2020}}\n' \
               '@inproceedings{child, title={C# and {Nesting}}, crossref={parent}}'
        result = parse_bibtex(text, arxiv_id=PAPER, version=1, path="refs.bib", source_fingerprint="f")
        child = result.occurrences[1]
        self.assertEqual(child.entry.title, "C# and {Nesting}")
        self.assertEqual(child.entry.authors, [])
        self.assertEqual(child.entry.year, 2020)
        self.assertFalse(child.authors_complete)

    def test_parenthesized_entry_with_parenthesis_in_title(self):
        text = '@book(a, title={A (complex) title}, author={An Nguyen})'
        result = parse_bibtex(text, arxiv_id=PAPER, version=1, path="refs.bib", source_fingerprint="f")
        self.assertEqual(result.occurrences[0].entry.title, "A (complex) title")

    def test_unmatched_quote_inside_braced_value_does_not_swallow_entry(self):
        text = '@article{a, title={A " quoted word}, year={2020}}\n@book{b, title={Next}}'
        result = parse_bibtex(text, arxiv_id=PAPER, version=1, path="refs.bib", source_fingerprint="f")
        self.assertEqual([o.original_key for o in result.occurrences], ["a", "b"])
        self.assertEqual(result.occurrences[0].entry.year, 2020)

    def test_initials_with_tex_space_are_incomplete(self):
        result = parse_bibtex('@article{x, author={A.~Nguyen and B. Tran}, title={X}, year={2020}}',
                              arxiv_id=PAPER, version=1, path="refs.bib", source_fingerprint="f")
        self.assertFalse(result.occurrences[0].authors_complete)

    def test_bibitem_lines_keep_title_distinct_from_journal(self):
        raw = "\\bibitem{ref}\nH.~Abdo, N.~Cohen, and D.~Dimitrov,\n" \
              "Graphs with maximal irregularity,\n\\emph{Filomat}, 28 (2014)."
        result = parse_bibitems(raw, arxiv_id=PAPER, version=1,
                                source_spans=[SourceSpan(path="main.tex", start=0, end=len(raw))],
                                source_fingerprint="f")
        entry = result.occurrences[0].entry
        self.assertEqual(entry.title, "Graphs with maximal irregularity")
        self.assertEqual(entry.journal, "Filomat")
        self.assertEqual(entry.authors, ["H.~Abdo", "N.~Cohen", "D.~Dimitrov"])
        self.assertFalse(result.occurrences[0].authors_complete)

    def test_bibitem_colon_and_tex_quotes(self):
        raw = (r"\bibitem{one}" "\n" r"B.\ Banaschewski:" "\n"
               "Radical ideals and coherent frames.\nJournal of Frames 37 (1996).\n"
               r"\bibitem{two}" "\n" "A.~Belavin and B.~Polyakov,\n"
               "``Infinite Conformal Symmetry,''\nNucl. Phys. (1984).")
        result = parse_bibitems(raw, arxiv_id=PAPER, version=1,
                                source_spans=[SourceSpan(path="main.tex", start=0, end=len(raw))],
                                source_fingerprint="f")
        self.assertEqual([o.entry.title for o in result.occurrences],
                         ["Radical ideals and coherent frames", "Infinite Conformal Symmetry,"])
        self.assertEqual(result.occurrences[0].entry.authors, [r"B.\ Banaschewski"])
        self.assertEqual(result.occurrences[0].entry.journal, "Journal of Frames")

    def test_bibitem_span_across_two_source_files(self):
        raw = r"\bibitem{x} A work, 2020."
        split = 12
        result = parse_bibitems(raw, arxiv_id=PAPER, version=1,
                                source_spans=[
                                    SourceSpan(path="a.tex", start=40, end=40 + split,
                                               flat_start=100, flat_end=100 + split),
                                    SourceSpan(path="b.tex", start=8, end=8 + len(raw) - split,
                                               flat_start=100 + split, flat_end=100 + len(raw))],
                                source_fingerprint="f")
        self.assertEqual([(s.path, s.start, s.end) for s in result.occurrences[0].source_spans],
                         [("a.tex", 40, 52), ("b.tex", 8, 8 + len(raw) - split)])

    def test_extract_only_declared_file_and_missing_bbl(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "data") as directory:
            root = Path(directory)
            (root / "refs.bib").write_text("@article{a, title={Found}}", encoding="utf-8")
            (root / "unused.bib").write_text("@article{x, title={Ignore}}", encoding="utf-8")
            gathered, tree = make_gathered(), make_raw_tree()
            gathered.version_input.source_dir = root
            result = extract_entries(gathered, tree)
            self.assertEqual([o.original_key for o in result.occurrences], ["a"])
            gathered.bib_paths[0].exists = False
            (root / "refs.bib").unlink()
            missing = extract_entries(gathered, tree)
            self.assertEqual(missing.diagnostics[-1].code, "BIBLIOGRAPHY_MISSING")
            tree.bibliography_blocks = [BibliographyBlock(raw=r'\bibitem{x} A cited work.',
                source_spans=[SourceSpan(path="main.tex", start=0, end=30)])]
            recovered = extract_entries(gathered, tree)
            self.assertEqual(len(recovered.occurrences), 1)
            self.assertFalse(any(d.code == "BIBLIOGRAPHY_MISSING" for d in recovered.diagnostics))


if __name__ == "__main__":
    unittest.main()
