"""Kiểm contract/fixtures/scaffold; KHÔNG phải nghiệm thu parser M2."""
from dataclasses import asdict, fields
import importlib
import inspect
import unittest

from src.parsing import contracts as c
from m2_support.fixtures import (make_gathered, make_raw_tree, make_extraction,
                                make_unified_bibliography, make_expected_publication)


class ScaffoldTests(unittest.TestCase):
    def test_final_tables_match_declared_columns(self):
        for table, cls in (("elements", c.ElementRow), ("hierarchy", c.HierarchyRow), ("bibtex", c.BibEntry)):
            self.assertEqual(tuple(f.name for f in fields(cls)), c.TABLE_COLUMNS[table])

    def test_fixtures_are_fresh_and_owner_independent(self):
        first, second = make_raw_tree(), make_raw_tree()
        first.nodes[0].content = "changed"
        self.assertNotEqual(first.nodes[0].content, second.nodes[0].content)
        self.assertEqual(make_extraction(2).occurrences[0].original_key, "beta")
        self.assertEqual(make_unified_bibliography().key_map[(2,"beta")], "alpha")

    def test_synthetic_expected_projection_is_consistent(self):
        p = make_expected_publication()
        ids = {r.element_id for r in p.elements}
        self.assertEqual(len(ids), len(p.elements))
        self.assertEqual(len(p.occurrences), 10)
        self.assertEqual(len(p.hierarchy), 8)
        for edge in p.hierarchy:
            self.assertIn(edge.element_id, ids)
            self.assertIn(edge.parent_id, ids)
        self.assertEqual(sum(x.before for x in p.counts_before_after if x.kind != "bibtex"), 10)
        self.assertEqual(sum(x.after for x in p.counts_before_after if x.kind != "bibtex"), 6)

    def test_gather_fixture_has_real_character_ranges(self):
        g = make_gathered()
        for span in g.source_map:
            self.assertEqual(g.latex[span.flat_start:span.flat_end], g.latex[span.start:span.end])
        declaration = g.bib_paths[0].declared_at
        self.assertEqual(g.latex[declaration.start:declaration.end], r"\bibliography{refs}")

    def test_contract_defaults_do_not_share_mutable_lists(self):
        first = c.BibEntry(arxiv_id="x", citation_key="a")
        second = c.BibEntry(arxiv_id="x", citation_key="b")
        first.authors.append("Someone")
        self.assertEqual(second.authors, [])
        self.assertEqual(c.ParseConfig().strict, True)

    def test_public_apis_have_type_annotations_and_implementation_guides(self):
        # Test này còn hợp lệ sau khi owner triển khai, không đòi stub tồn tại mãi.
        modules = ("inputs", "gather", "hierarchy", "sentences", "bibliography", "reference_dedup",
                   "normalize", "content_dedup", "validation", "serialization", "pipeline", "metrics", "benchmark")
        for name in modules:
            module = importlib.import_module("src.parsing."+name)
            funcs = [v for k,v in vars(module).items() if not k.startswith('_') and inspect.isfunction(v) and v.__module__==module.__name__]
            self.assertTrue(funcs, name)
            for func in funcs:
                with self.subTest(module=name, function=func.__name__):
                    self.assertTrue(func.__doc__)
                    signature = inspect.signature(func)
                    self.assertIsNot(signature.return_annotation, inspect.Signature.empty)
                    for p in signature.parameters.values():
                        self.assertIsNot(p.annotation, inspect.Parameter.empty)


if __name__ == '__main__':
    unittest.main()
