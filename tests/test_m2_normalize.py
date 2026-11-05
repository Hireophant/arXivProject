"""DA1 regression: cleanup, cites, D3 and raw immutability."""
import unittest
from copy import deepcopy
from dataclasses import replace
from m2_support.fixtures import make_raw_tree, make_unified_bibliography
from src.parsing.contracts import ParseConfig, RawNode
from src.parsing.normalize import normalize_leaf, normalize_tree, rebuild_component_content, rewrite_citations

class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.bib=make_unified_bibliography(); self.config=ParseConfig()

    def clean(self,text,kind='sentence',subtype=None):
        node=RawNode(local_id='x',parent_local_id='r',kind=kind,content=text,position=0,subtype=subtype)
        before=deepcopy(node)
        result=normalize_leaf(node,version=2,bibliography=self.bib,config=self.config)
        self.assertEqual(node,before)
        self.assertEqual(normalize_leaf(result,version=2,bibliography=self.bib,config=self.config),result)
        return result.content

    def test_cite_context_optional_star_multi_version(self):
        text=r'beta \citep*[see {p. 2}][Eq. {3}]{beta, alpha} \url{https://x/beta} \verb|\cite{beta}| % \cite{beta}'
        expected=r'beta \citep*[see {p. 2}][Eq. {3}]{alpha,alpha} \url{https://x/beta} \verb|\cite{beta}| % \cite{beta}'
        self.assertEqual(rewrite_citations(text,version=2,bibliography=self.bib),expected)
        self.assertEqual(rewrite_citations(r'\citet{beta}',version=1,bibliography=self.bib),r'\citet{beta}')

    def test_cleanup_math_escape_verbatim(self):
        self.assertEqual(self.clean(r' \textbf{Result \emph{works}} with \(x + y\) and \$5. '),r'Result works with $x + y$ and \$5.')
        self.assertEqual(self.clean('A  % hidden\nword.'),'A word.')
        self.assertEqual(self.clean(r'\verb|a  b \textbf{x}|'),r'\verb|a  b \textbf{x}|')

    def test_display_and_align_rows(self):
        for text in (r'\[x=y\]',r'$$x=y$$',r'\begin{equation*}x=y\end{equation*}'):
            self.assertEqual(self.clean(text,'block_formula'),r'\begin{equation}x=y\end{equation}')
        self.assertEqual(self.clean(r'\begin{align*}a&=b\\c&=d\end{align*}','block_formula'),r'\begin{equation}\begin{aligned}a&=b\\c&=d\end{aligned}\end{equation}')

    def test_table_semantics(self):
        text=r'\begin{table}[htpb]\centering\caption{\textbf{Results}}\begin{tabular}{cc}a&b\\\midrule c&d\end{tabular}\end{table}'
        out=self.clean(text,'figure','table')
        for part in (r'\caption{Results}',r'a&b\\','c&d'): self.assertIn(part,out)
        self.assertNotIn('midrule',out); self.assertNotIn('[htpb]',out)
        self.assertEqual(self.clean('ordinary [htpb] text.'),'ordinary [htpb] text.')

    def test_tree_copy_idempotence_components(self):
        raw=make_raw_tree(2); before=deepcopy(raw)
        out=normalize_tree(raw,self.bib,self.config)
        self.assertEqual(raw,before)
        self.assertEqual(out.nodes[2].content,r'We study X. See \cite{alpha}.')
        self.assertEqual(normalize_tree(out,self.bib,self.config),out)
        self.assertEqual(out.nodes[4].source_spans,raw.nodes[4].source_spans)

    def test_canonical_key_shadowed_by_other_raw_key_still_tree_idempotent(self):
        from src.parsing.contracts import BibEntry
        bib=make_unified_bibliography()
        bib.entries=[BibEntry(arxiv_id=bib.arxiv_id,citation_key='alpha'),BibEntry(arxiv_id=bib.arxiv_id,citation_key='other')]
        bib.key_map={(2,'beta'):'alpha',(2,'alpha'):'other'}
        raw=make_raw_tree(2)
        once=normalize_tree(raw,bib,self.config)
        self.assertIn(r'\cite{alpha}',once.nodes[4].content)
        self.assertEqual(normalize_tree(once,bib,self.config),once)

    def test_unresolved_has_context(self):
        raw=make_raw_tree()
        raw.nodes[4].content=r'See \cite{absent}.'
        raw.nodes[2].content=r'We study X. See \cite{absent}.'
        out=normalize_tree(raw,self.bib,self.config)
        errors=[d for d in out.diagnostics if d.code=='CITATION_UNRESOLVED']
        self.assertTrue(errors)
        self.assertTrue(all(d.version==1 and d.path=='main.tex' for d in errors))

    def test_bottom_up_nested_order_and_boundaries(self):
        def n(i,p,k,c,pos): return RawNode(local_id=i,parent_local_id=p,kind=k,content=c,position=pos)
        nodes=[n('r',None,'document','Version 1 root',0),n('l','r','itemize','',0),n('i','l','item','',0),n('p','i','paragraph','',0),n('a','p','sentence','Alpha.',0),n('b','p','sentence','Beta.',1),n('q','i','paragraph','',1),n('c','q','sentence','Gamma.',0),n('l2','i','itemize','',2),n('i2','l2','item','',0),n('d','i2','sentence','Delta.',0)]
        out={x.local_id:x.content for x in rebuild_component_content(list(reversed(nodes)))}
        self.assertEqual(out['p'],'Alpha. Beta.')
        self.assertEqual(out['i'],'Alpha. Beta.\n\nGamma.\n\\begin{itemize}\n\\item {Delta.}\n\\end{itemize}')
        self.assertEqual(out['l'],'\\begin{itemize}\n\\item {'+out['i']+'}\n\\end{itemize}')
        nodes[5]=replace(nodes[5],kind='block_formula',content=r'\begin{equation}x\end{equation}')
        out={x.local_id:x.content for x in rebuild_component_content(nodes)}
        self.assertEqual(out['p'],'Alpha.\n'+nodes[5].content)

    def test_uncovered_parent_and_cycle_rejected(self):
        raw=make_raw_tree(); raw.nodes[2].content+=' Unrepresented text.'
        out=normalize_tree(raw,self.bib,self.config)
        self.assertTrue(any(d.code=='INVALID_STRUCTURE' for d in out.diagnostics))
        self.assertIn('Unrepresented text.',out.nodes[2].content)
        raw=make_raw_tree(); raw.nodes[1].parent_local_id='p'
        with self.assertRaises(ValueError): rebuild_component_content(raw.nodes)

    def test_math_grouping_and_literal_citations_cannot_disappear_in_rebuild(self):
        raw=make_raw_tree()
        raw.nodes[3].content=r'We study $x^{ab}$.'
        raw.nodes[2].content=r'We study $x^ab$. See \cite{alpha}.'
        out=normalize_tree(raw,self.bib,self.config)
        self.assertTrue(any(d.code=='INVALID_STRUCTURE' for d in out.diagnostics))
        raw=make_raw_tree();raw.nodes[3].content=r'Code \verb|\cites{unmapped}|.'
        raw.nodes[2].content=raw.nodes[3].content+' '+raw.nodes[4].content
        out=normalize_tree(raw,self.bib,self.config)
        self.assertEqual(out.diagnostics,[])

    def test_rule_optional_thickness_does_not_become_content(self):
        self.assertEqual(self.clean(r'\begin{tabular}{c}A\\\midrule[1pt] B\end{tabular}','figure','table'),r'\begin{tabular}{c}A\\ B\end{tabular}')

    def test_comment_join_and_wrapper_word_boundaries(self):
        self.assertEqual(self.clean('micro% hidden\nscope.'),'microscope.')
        self.assertEqual(self.clean(r'A\textbf{ B }C.'),'A B C.')
        self.assertEqual(self.clean(r'A \textbf{ B } C.'),'A B C.')
        self.assertEqual(self.clean(r'A \textbf{} B.'),'A B.')
        raw=make_raw_tree();raw.nodes[3].content='AB.';raw.nodes[2].content=r'A B. See \cite{alpha}.'
        out=normalize_tree(raw,self.bib,self.config)
        self.assertTrue(any(d.code=='INVALID_STRUCTURE' for d in out.diagnostics))

    def test_math_comments_do_not_swallow_closing_delimiters(self):
        for text in ('\\begin{equation}\nx % comment\n\\end{equation}','\\[x % comment\n\\]','$$x % comment\n$$'):
            self.assertEqual(self.clean(text,'block_formula'),r'\begin{equation}x\end{equation}')
        self.assertEqual(self.clean('$x % comment\n$'),'$x$')
        self.assertEqual(self.clean('\\begin{equation}x % \\end{equation}\n+y\\end{equation}','block_formula'),r'\begin{equation}x +y\end{equation}')

    def test_comment_between_command_and_argument_is_tex_whitespace(self):
        text='See \\cite% alpha stays in this raw comment\n{beta}.'
        self.assertEqual(rewrite_citations(text,version=2,bibliography=self.bib),
                         'See \\cite% alpha stays in this raw comment\n{alpha}.')
        self.assertEqual(self.clean('A \\textbf% formatting comment\n{bold} word.'),'A bold word.')

if __name__=='__main__': unittest.main()
