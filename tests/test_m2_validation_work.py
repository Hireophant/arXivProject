"""Bound repeated parsing while retaining D3/citation validation semantics."""
from collections import Counter
import unittest
from unittest.mock import patch

from m2_support.fixtures import make_expected_publication, make_raw_tree
from src.parsing import normalize, validation


class ValidationWorkTests(unittest.TestCase):
    def test_exact_component_content_needs_no_second_token_scan(self):
        tree=make_raw_tree()
        with patch.object(normalize,'_content_tokens',wraps=normalize._content_tokens) as scanned:
            rebuilt=normalize.rebuild_component_content(tree.nodes)
        self.assertEqual(rebuilt[2].content,r'We study X. See \cite{alpha}.')
        self.assertEqual(scanned.call_count,0)

    def test_shared_citation_content_scanned_once_but_errors_cover_each_version(self):
        publication=make_expected_publication()
        target=next(e for e in publication.elements if e.kind=='sentence' and '\\cite' in e.content)
        target.content=r'See \cite{missing}.'
        counts=Counter()
        original=validation._citation_spans
        def scan(text):
            counts[text]+=1
            return original(text)
        with patch.object(validation,'_citation_spans',side_effect=scan):
            issues=validation.validate_publication(publication)
        self.assertEqual(counts[target.content],1)
        self.assertEqual({d.version for d in issues if d.code=='CITATION_UNRESOLVED'}, {1,2})

    def test_malformed_citation_keeps_earlier_unresolved_key_diagnostic(self):
        publication=make_expected_publication()
        target=next(e for e in publication.elements if e.kind=='sentence' and '\\cite' in e.content)
        target.content=r'\cite{missing} then \cite{unclosed'
        issues=validation.validate_publication(publication)
        self.assertEqual({d.version for d in issues if d.code=='CITATION_UNRESOLVED' and 'missing' in d.message}, {1,2})
        self.assertTrue(any(d.code=='CITATION_UNRESOLVED' and 'Unclosed' in d.message for d in issues))
