"""Distilled list failures found in the supplied prepared Danh2 snapshot."""
import unittest

from m2_support.fixtures import make_gathered
from src.parsing.contracts import ParseConfig, SourceSpan, UnifiedBibliography
from src.parsing.hierarchy import parse_version
from src.parsing.normalize import normalize_tree
from src.parsing.content_dedup import assemble_publication
from src.parsing.validation import finalize_publication


def parse_list(body):
    gathered=make_gathered()
    gathered.latex=r'\documentclass{article}\begin{document}'+body+r'\end{document}'
    gathered.source_map=[SourceSpan(path='main.tex',start=0,end=len(gathered.latex),
                                    flat_start=0,flat_end=len(gathered.latex))]
    gathered.bib_paths=[]
    tree=parse_version(gathered)
    bib=UnifiedBibliography(arxiv_id=tree.arxiv_id,entries=[],key_map={},occurrences=[])
    normalized=normalize_tree(tree,bib,ParseConfig())
    return gathered,tree,normalized,finalize_publication(assemble_publication([normalized],bib))


class RealListRegressions(unittest.TestCase):
    def test_description_labels_are_preserved_in_canonical_items(self):
        _,raw,normalized,publication=parse_list(
            r'\begin{description}\item[RQ1:] First question?'
            r'\item[\textbf{RQ2:}] Second question?\end{description}')
        self.assertTrue(publication.export_ready,publication.diagnostics)
        self.assertEqual(next(n.content for n in normalized.nodes if n.kind=='itemize'),
                         '\\begin{itemize}\n\\item {RQ1:\nFirst question?}\n'
                         '\\item {RQ2:\nSecond question?}\n\\end{itemize}')
        self.assertEqual(raw.normalized_with,None)

    def test_layout_options_and_math_labels_do_not_break_coverage(self):
        _,raw,normalized,publication=parse_list(
            r'\begin{itemize}[itemindent=0pt,labelindent=\parindent,leftmargin=*]'
            r'\item[($f_1$)] First.\item[($f_2$)] Second.\end{itemize}')
        self.assertTrue(publication.export_ready,publication.diagnostics)
        text=next(n.content for n in normalized.nodes if n.kind=='itemize')
        self.assertIn(r'($f_1$)',text)
        self.assertIn(r'($f_2$)',text)
        self.assertNotIn('leftmargin',text)
        self.assertIn('leftmargin',next(n.content for n in raw.nodes if n.kind=='itemize'))

    def test_numeric_vertical_skip_is_layout_not_a_synthetic_item(self):
        g,raw,normalized,publication=parse_list(
            r'\begin{itemize}\vskip0.06in\item[$f_1$] First.\vskip0.06in'
            r'\item[$f_2$] Second.\end{itemize}')
        self.assertTrue(publication.export_ready,publication.diagnostics)
        self.assertEqual(len([n for n in raw.nodes if n.kind=='item']),2)
        self.assertFalse(any('0.06in' in n.content for n in normalized.nodes))
        first=next(n for n in raw.nodes if n.kind=='sentence' and n.content=='First.')
        self.assertEqual(first.source_spans[0].start,g.latex.index('First.'))

    def test_label_style_options_remain_visible_and_need_review(self):
        _,raw,normalized,publication=parse_list(
            r'\begin{itemize}[label=\alph*]\item Important.\end{itemize}')
        self.assertFalse(publication.export_ready)
        self.assertTrue(any(d.severity=='error' for d in publication.diagnostics))
        self.assertIn(r'label=\alph*',next(n.content for n in normalized.nodes if n.kind=='itemize'))

    def test_unsupported_commands_inside_labels_are_not_accepted_as_plain_text(self):
        for label in (r'\unknownmacro{Hidden meaning}',r'\includegraphics{missing}',
                      r'\begin{figure}\caption{Hidden figure}\end{figure}'):
            with self.subTest(label=label):
                _,_,_,publication=parse_list(r'\begin{description}\item['+label+r'] Body.\end{description}')
                self.assertFalse(publication.export_ready)
                self.assertTrue(any(d.code=='UNSUPPORTED_CONTENT' and d.severity=='error' for d in publication.diagnostics))

    def test_literal_item_syntax_is_unchanged(self):
        _,_,normalized,publication=parse_list(r'Code \verb|\item[keep] \vskip0.06in|. Done.')
        self.assertTrue(publication.export_ready,publication.diagnostics)
        self.assertTrue(any(r'\verb|\item[keep] \vskip0.06in|' in n.content for n in normalized.nodes))

    def test_math_and_figure_labels_stay_consistent_with_parent_content(self):
        for leaf in (r'\begin{equation}\label{eq:one}x=1\end{equation}',
                     r'\begin{figure}\caption{Result}\label{fig:one}\end{figure}'):
            with self.subTest(leaf=leaf):
                _,raw,normalized,publication=parse_list(r'\begin{itemize}\item Before.'+leaf+r'After.\end{itemize}')
                self.assertTrue(publication.export_ready,publication.diagnostics)
                self.assertTrue(all('\\label{' in n.content for n in raw.nodes if n.kind in ('item','itemize','block_formula','figure')))
                if '\\begin{figure}' in leaf:
                    figure,=[n for n in normalized.nodes if n.kind=='figure']
                    self.assertEqual(figure.content,leaf)

    def test_kern_does_not_consume_visible_glue_words(self):
        for command,tail in ((r'\kern1pt','plus 2pt After.'),
                             (r'\hskip1pt plus 2pt','plus 3pt After.')):
            with self.subTest(command=command):
                _,_,normalized,publication=parse_list('Before.'+command+' '+tail)
                self.assertTrue(publication.export_ready,publication.diagnostics)
                self.assertTrue(any(tail in n.content for n in normalized.nodes if n.kind=='sentence'))

    def test_unreviewed_enumeration_keeps_valid_working_tree_and_error(self):
        _,_,normalized,publication=parse_list(
            r'\begin{enumerate}\item First.\item Second.\end{enumerate}')
        self.assertFalse(publication.export_ready)
        self.assertEqual(publication.version_states,{1:'partial'})
        self.assertFalse(any(d.code=='INVALID_STRUCTURE' for d in publication.diagnostics))
        self.assertTrue(any(d.code=='UNSUPPORTED_CONTENT' and d.severity=='error' for d in publication.diagnostics))
        self.assertIn('First.',next(n.content for n in normalized.nodes if n.kind=='itemize'))
        self.assertIn('Second.',next(n.content for n in normalized.nodes if n.kind=='itemize'))


if __name__=='__main__':
    unittest.main()
