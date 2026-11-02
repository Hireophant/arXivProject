"""DA2: exact sharing, distinct roots and complete ordered occurrences."""
import unittest
from dataclasses import replace
from unittest.mock import patch
from m2_support.fixtures import make_normalized_tree, make_unified_bibliography
from src.parsing.content_dedup import assemble_publication
from src.parsing.contracts import RawNode,ParseConfig

class DedupTests(unittest.TestCase):
    def build(self,trees): return assemble_publication(trees,make_unified_bibliography())

    def test_shared_sentence_moved_and_repeated(self):
        trees=[make_normalized_tree(1),make_normalized_tree(2)]
        trees[1].nodes[1].content='Background'
        trees[1].nodes[3].parent_local_id='h'
        trees[1].nodes[3].position=1
        trees[1].nodes.append(replace(trees[1].nodes[3],local_id='repeat',position=2))
        p=self.build(trees)
        rows=[e for e in p.elements if e.kind=='sentence' and e.content=='We study X.']
        self.assertEqual(len(rows),1)
        occ=[o for o in p.occurrences if o.element_id==rows[0].element_id]
        self.assertEqual([(o.version,o.local_id,o.position) for o in occ],[(1,'s1',0),(2,'s1',1),(2,'repeat',2)])
        self.assertEqual(len([e for e in p.hierarchy if e.element_id==rows[0].element_id]),2)
        self.assertNotEqual(p.root_ids[1],p.root_ids[2])

    def test_exact_body_kind_and_determinism(self):
        trees=[make_normalized_tree(1),make_normalized_tree(2)]
        trees[1].nodes[2].content='Changed body.'
        trees[1].nodes[3].content='We study Y.'
        trees[1].nodes.append(RawNode(local_id='other',parent_local_id='r',kind='heading',content='We study X.',position=1))
        p=self.build(trees)
        self.assertEqual(len([e for e in p.elements if e.kind=='paragraph']),2)
        self.assertEqual(len([e for e in p.elements if e.content=='We study X.']),2)
        self.assertEqual(p,self.build(list(reversed(trees))))

    def test_hash_collision_does_not_merge_and_is_order_independent(self):
        class Collision:
            def hexdigest(self): return '0'*64
        with patch('src.parsing.content_dedup.hashlib.sha256',return_value=Collision()):
            a=self.build([make_normalized_tree(1),make_normalized_tree(2)])
            b=self.build([make_normalized_tree(2),make_normalized_tree(1)])
        self.assertEqual(a,b)
        self.assertEqual(len(a.elements),6)
        self.assertEqual(len({x.element_id for x in a.elements}),6)

    def test_reject_raw_duplicate_versions_wrong_paper(self):
        raw=make_normalized_tree();raw.normalized_with=None
        for trees in ([raw],[make_normalized_tree(),make_normalized_tree()],[replace(make_normalized_tree(),arxiv_id='other')]):
            with self.assertRaises(ValueError): self.build(trees)

    def test_reversed_items_change_list_id_and_heading_shares_title(self):
        from src.parsing.normalize import normalize_tree
        bib=make_unified_bibliography()
        def tree(version,reverse=False):
            t=make_normalized_tree(version)
            def n(i,p,k,text,pos):return RawNode(local_id=i,parent_local_id=p,kind=k,content=text,position=pos)
            t.nodes=t.nodes[:2]+[n('l','h','itemize','',0),n('a','l','item','',int(reverse)),n('sa','a','sentence','Alpha.',0),n('b','l','item','',int(not reverse)),n('sb','b','sentence','Beta.',0)]
            return normalize_tree(t,bib,ParseConfig())
        p=self.build([tree(1),tree(2,True)])
        self.assertEqual(len([e for e in p.elements if e.kind=='itemize']),2)
        self.assertEqual(len([e for e in p.elements if e.kind=='heading']),1)

    def test_all_empty_no_fake_elements(self):
        tree=replace(make_normalized_tree(),nodes=[],root_local_id=None,status='empty_no_tex',normalized_with=None)
        bib=make_unified_bibliography();bib.entries=[];bib.occurrences=[];bib.key_map={};bib.identity_decisions=[]
        p=assemble_publication([tree],bib)
        self.assertEqual((p.elements,p.hierarchy,p.occurrences),([],[],[]));self.assertEqual(p.root_ids,{1:None})

if __name__=='__main__': unittest.main()
