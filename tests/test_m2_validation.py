"""DA2: schema/occurrence integrity and final status, independent expected fixture."""
import unittest
from copy import deepcopy
from m2_support.fixtures import make_expected_publication
from src.parsing.contracts import Diagnostic
from src.parsing.validation import finalize_publication,validate_publication

class ValidationTests(unittest.TestCase):
    def test_expected_read_only(self):
        p=make_expected_publication();before=deepcopy(p)
        self.assertEqual(validate_publication(p),[]);self.assertEqual(p,before)
        self.assertTrue(finalize_publication(p).export_ready)

    def test_schema_bad_types_duplicate_keys_fks_counts(self):
        mutations=[lambda p:setattr(p.bibtex[0],'authors','bad'),lambda p:setattr(p.bibtex[0],'year',True),lambda p:setattr(p.hierarchy[0],'parent_id','other#root'),lambda p:p.elements.append(deepcopy(p.elements[0])),lambda p:setattr(p.counts_before_after[0],'before',99),lambda p:setattr(p.occurrences[-1],'position',0),lambda p:p.root_ids.pop(2)]
        for mutate in mutations:
            p=make_expected_publication();mutate(p)
            with self.subTest(mutate=mutate):
                self.assertTrue(validate_publication(p));self.assertFalse(finalize_publication(p).export_ready)

    def test_cycles_orphans_missing_projection(self):
        for mutate in (lambda p:setattr(p.occurrences[1],'parent_local_id','p'),lambda p:setattr(p.occurrences[1],'parent_local_id','absent'),lambda p:p.hierarchy.pop()):
            p=make_expected_publication();mutate(p)
            self.assertIn('failed',finalize_publication(p).version_states.values())

    def test_errors_affected_versions_and_warning(self):
        for code in ('INCLUDE_MISSING','BIB_ENTRY_UNPARSED','REFERENCE_IDENTITY_REVIEW','CITATION_UNRESOLVED'):
            p=make_expected_publication();p.diagnostics=[Diagnostic(code=code,severity='error',message='fixture',arxiv_id=p.arxiv_id,affected_versions=[2])]
            out=finalize_publication(p)
            self.assertEqual(out.version_states,{1:'parsed',2:'partial'});self.assertFalse(out.export_ready)
            self.assertEqual(finalize_publication(out),out)
        p=make_expected_publication();p.diagnostics=[Diagnostic(code='FIELD_CONFLICT',severity='warning',message='resolved evidence',arxiv_id=p.arxiv_id)]
        self.assertTrue(finalize_publication(p).export_ready)

    def test_unresolved_cite_and_key_map(self):
        p=make_expected_publication();p.bibtex=[]
        out=finalize_publication(p)
        self.assertTrue(any(d.code=='CITATION_UNRESOLVED' for d in out.diagnostics));self.assertFalse(out.export_ready)

    def test_d3_parent_content_must_match_ordered_children(self):
        p=make_expected_publication()
        next(e for e in p.elements if e.kind=='paragraph').content='Unrelated body.'
        out=finalize_publication(p)
        self.assertFalse(out.export_ready)
        self.assertIn('failed',out.version_states.values())

    def test_projected_self_edge_is_valid_if_occurrences_form_tree(self):
        from src.parsing.contracts import RawNode,VersionTree,UnifiedBibliography,NORMALIZATION_VERSION
        from src.parsing.content_dedup import assemble_publication
        def n(i,parent,kind,text):return RawNode(local_id=i,parent_local_id=parent,kind=kind,content=text,position=0)
        tree=VersionTree(arxiv_id='paper',version=1,root_local_id='r',nodes=[n('r',None,'document','Version 1 root'),n('p1','r','paragraph','X.'),n('p2','p1','paragraph','X.'),n('s','p2','sentence','X.')],bibliography_blocks=[],status='parsed',source_fingerprint='f',normalized_with=NORMALIZATION_VERSION)
        bib=UnifiedBibliography(arxiv_id='paper',entries=[],key_map={},occurrences=[])
        p=assemble_publication([tree],bib)
        self.assertTrue(any(e.element_id==e.parent_id for e in p.hierarchy))
        self.assertTrue(finalize_publication(p).export_ready)

    def test_all_empty_and_blocked_preserve_states(self):
        p=make_expected_publication()
        p.elements=[];p.hierarchy=[];p.occurrences=[];p.bibtex=[];p.bib_occurrences=[];p.key_map={};p.identity_decisions=[];p.counts_before_after=[]
        p.root_ids={1:None,2:None};p.version_states={1:'empty_no_tex',2:'empty_no_tex'}
        self.assertTrue(finalize_publication(p).export_ready)
        p.version_states[2]='blocked_input'
        out=finalize_publication(p)
        self.assertEqual(out.version_states[2],'blocked_input');self.assertFalse(out.export_ready)

    def test_empty_versions_cannot_contribute_bibliography_or_stale_decisions(self):
        p=make_expected_publication()
        p.elements=[];p.hierarchy=[];p.occurrences=[];p.counts_before_after=[]
        p.root_ids={1:None,2:None};p.version_states={1:'empty_no_tex',2:'empty_no_tex'}
        self.assertFalse(finalize_publication(p).export_ready)
        p=make_expected_publication();p.identity_decisions[0].source_fingerprints[p.bib_occurrences[0].occurrence_id]='wrong'
        self.assertFalse(finalize_publication(p).export_ready)

if __name__=='__main__': unittest.main()
