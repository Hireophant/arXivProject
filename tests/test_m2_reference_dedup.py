import unittest
from copy import deepcopy

from src.parsing.contracts import BibliographyExtraction, BibEntry, BibOccurrence, IdentityDecision, ParseConfig, SourceSpan
from src.parsing.normalize import normalize_tree, rewrite_citations
from src.parsing.content_dedup import assemble_publication
from src.parsing.reference_dedup import unify_entries
from tests.m2_support.fixtures import PAPER, make_extraction, make_raw_tree


def occurrence(version, key, *, doi=None, year=2020, title="A study", authors=None, complete=True):
    return BibOccurrence(occurrence_id=f"{PAPER}-v{version}-{key}-{doi}", arxiv_id=PAPER, version=version,
                         entry=BibEntry(arxiv_id=PAPER, citation_key=key, title=title,
                                        authors=authors if authors is not None else ["An Nguyen"], year=year, doi=doi),
                         original_key=key, source_spans=[SourceSpan(path="refs.bib", start=0, end=10)],
                         source_fingerprint=str(version) * 64, raw=f"@article{{{key}}}", authors_complete=complete)


def extracts(*items):
    return [BibliographyExtraction(arxiv_id=PAPER, version=o.version, occurrences=[o]) for o in items]


class ReferenceDedupTests(unittest.TestCase):
    def test_union_and_order_independence(self):
        a, b = make_extraction(1), make_extraction(2)
        first = unify_entries(PAPER, [a, b])
        second = unify_entries(PAPER, [b, a])
        self.assertEqual(first.entries, second.entries)
        self.assertEqual(first.key_map, second.key_map)
        self.assertEqual(len(first.entries), 1)
        self.assertEqual(first.entries[0].doi, "10.1234/example")
        self.assertEqual(first.entries[0].year, 2020)

    def test_doi_bridge_stays_pending(self):
        a = occurrence(1, "a", doi="10.1/x")
        b = occurrence(2, "b")
        c = occurrence(3, "c", doi="10.1/y")
        result = unify_entries(PAPER, extracts(a, b, c))
        self.assertEqual(len(result.entries), 3)
        self.assertIn("REFERENCE_IDENTITY_REVIEW", [d.code for d in result.diagnostics])
        reversed_result = unify_entries(PAPER, list(reversed(extracts(a, b, c))))
        self.assertEqual(result.key_map, reversed_result.key_map)

    def test_missing_year_pending_and_different_authors_separate(self):
        a = occurrence(1, "a")
        b = occurrence(2, "b", year=None)
        c = occurrence(3, "c", authors=["Other Person"])
        result = unify_entries(PAPER, extracts(a, b, c))
        self.assertEqual(len(result.entries), 3)
        self.assertEqual(sum(d.code == "REFERENCE_IDENTITY_REVIEW" for d in result.diagnostics), 1)

    def test_title_wrapper_with_full_authors_merges(self):
        a = occurrence(1, "a", title=r"\textbf{A {study}}")
        b = occurrence(2, "b", title="A study")
        result = unify_entries(PAPER, extracts(a, b))
        self.assertEqual(len(result.entries), 1)

    def test_three_versions_keep_year_when_last_has_only_doi(self):
        a = occurrence(1, "old", year=2020, title="A study")
        b = occurrence(2, "new", doi="https://doi.org/10.1/x", year=2020, title="A study")
        c = occurrence(3, "latest", doi="doi:10.1/X", year=None, title=None, authors=[])
        result = unify_entries(PAPER, extracts(a, b, c))
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(result.entries[0].year, 2020)
        self.assertEqual(result.key_map[(3, "latest")], "latest")

    def test_same_key_different_doi_in_one_version_has_no_map(self):
        a = occurrence(1, "same", doi="10.1/x")
        b = occurrence(1, "same", doi="10.1/y")
        b.occurrence_id += "-second"
        result = unify_entries(PAPER, [BibliographyExtraction(arxiv_id=PAPER, version=1, occurrences=[a, b])])
        self.assertEqual(len(result.entries), 2)
        self.assertNotIn((1, "same"), result.key_map)
        self.assertIn("KEY_CONFLICT", [d.code for d in result.diagnostics])

    def test_same_key_in_different_versions_can_map_to_different_entries(self):
        a = occurrence(1, "shared", doi="10.1/x")
        b = occurrence(2, "shared", doi="10.1/y")
        result = unify_entries(PAPER, extracts(a, b))
        self.assertEqual(len(result.entries), 2)
        self.assertNotEqual(result.key_map[(1, "shared")], result.key_map[(2, "shared")])

    def test_review_requires_current_fingerprints(self):
        a = occurrence(1, "a")
        b = occurrence(2, "b", year=None)
        decision = IdentityDecision(decision_id="review-1", arxiv_id=PAPER,
                                    occurrence_ids=[a.occurrence_id, b.occurrence_id],
                                    source_fingerprints={a.occurrence_id: a.source_fingerprint,
                                                         b.occurrence_id: b.source_fingerprint},
                                    outcome="merge", rule="human", evidence="Checked source PDFs",
                                    reviewer="Nguyen", input_snapshot_id="snapshot", code_revision="rev")
        merged = unify_entries(PAPER, extracts(a, b), review_decisions=[decision])
        self.assertEqual(len(merged.entries), 1)
        stale = deepcopy(decision)
        stale.source_fingerprints[b.occurrence_id] = "old"
        pending = unify_entries(PAPER, extracts(a, b), review_decisions=[stale])
        self.assertEqual(len(pending.entries), 2)
        self.assertIn("REFERENCE_IDENTITY_REVIEW", [d.code for d in pending.diagnostics])

    def test_review_can_resolve_missing_title_and_keep_same_doi_separate(self):
        a = occurrence(1, "a", doi="10.1/x", title=None)
        b = occurrence(2, "b", doi="10.1/y", title=None)
        review = IdentityDecision(decision_id="review-2", arxiv_id=PAPER,
                                  occurrence_ids=[a.occurrence_id, b.occurrence_id],
                                  source_fingerprints={a.occurrence_id: a.source_fingerprint,
                                                       b.occurrence_id: b.source_fingerprint},
                                  outcome="merge", rule="human", evidence="Compared original source records",
                                  reviewer="Nguyen", input_snapshot_id="snapshot", code_revision="rev")
        merged = unify_entries(PAPER, extracts(a, b), review_decisions=[review])
        self.assertEqual(len(merged.entries), 1)
        self.assertTrue(any(c.field_name == "doi" for c in merged.conflicts))
        same_doi = deepcopy(b)
        same_doi.entry.doi = a.entry.doi
        keep = deepcopy(review)
        keep.outcome = "keep_separate"
        keep.occurrence_ids = [a.occurrence_id, same_doi.occurrence_id]
        kept = unify_entries(PAPER, extracts(a, same_doi), review_decisions=[keep])
        self.assertEqual(len(kept.entries), 2)

    def test_two_pair_reviews_cannot_bridge_opposing_doi_clusters(self):
        a = occurrence(1, "a", doi="10.1/x")
        b = occurrence(2, "b")
        c = occurrence(3, "c", doi="10.1/y")
        reviews = []
        for other in (a, c):
            reviews.append(IdentityDecision(
                decision_id=f"review-{other.original_key}", arxiv_id=PAPER,
                occurrence_ids=[b.occurrence_id, other.occurrence_id],
                source_fingerprints={o.occurrence_id: o.source_fingerprint for o in (b, other)},
                outcome="merge", rule="human", evidence="Checked this pair",
                reviewer="Nguyen", input_snapshot_id="snapshot", code_revision="rev"))
        result = unify_entries(PAPER, extracts(a, b, c), review_decisions=reviews)
        self.assertEqual(len(result.entries), 3)
        self.assertIn("REFERENCE_IDENTITY_REVIEW", [d.code for d in result.diagnostics])

    def test_citation_rewrite_uses_version_key_map(self):
        bibliography = unify_entries(PAPER, [make_extraction(1), make_extraction(2)])
        text = r"See \cite[pp. 1-2]{beta,missing} and beta."
        rewritten = rewrite_citations(text, version=2, bibliography=bibliography)
        self.assertEqual(rewritten, r"See \cite[pp. 1-2]{alpha,missing} and beta.")

    def test_rewritten_citation_shares_sentence_across_versions(self):
        bibliography = unify_entries(PAPER, [make_extraction(1), make_extraction(2)])
        trees = [normalize_tree(make_raw_tree(version), bibliography, ParseConfig(code_revision="test"))
                 for version in (1, 2)]
        publication = assemble_publication(trees, bibliography)
        cited = [row for row in publication.elements
                 if row.kind == "sentence" and row.content == r"See \cite{alpha}."]
        self.assertEqual(len(cited), 1)
        self.assertEqual({row.version for row in publication.hierarchy
                          if row.element_id == cited[0].element_id}, {1, 2})


if __name__ == "__main__":
    unittest.main()
