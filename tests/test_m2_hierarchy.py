"""Khang KG1/KG3 / S2/S4/S9/S11; no dependency on unfinished gather."""
import unittest
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict

from src.parsing.contracts import Diagnostic, ParseConfig, SourceSpan
from src.parsing.hierarchy import extract_bibliography_blocks, parse_version
from src.parsing.normalize import normalize_leaf, normalize_tree
from src.parsing.content_dedup import assemble_publication
from src.parsing.validation import finalize_publication
from m2_support.fixtures import make_gathered, make_unified_bibliography


def gathered(body, version=1):
    g = make_gathered(version)
    g.latex = '\\documentclass{article}\n\\begin{document}\n' + body + '\n\\end{document}\n'
    g.source_map = [SourceSpan(path='main.tex', start=0, end=len(g.latex), flat_start=0, flat_end=len(g.latex))]
    g.bib_paths = []
    return g


class HierarchyTests(unittest.TestCase):
    def assert_invariants(self, tree):
        self.assertIsNone(tree.normalized_with)
        index = {n.local_id: n for n in tree.nodes}
        self.assertEqual(len(index), len(tree.nodes))
        self.assertEqual([n.local_id for n in tree.nodes], ['r'] + [f'n{i:06d}' for i in range(1, len(tree.nodes))])
        children = defaultdict(list)
        for n in tree.nodes:
            if n.parent_local_id is not None:
                self.assertIn(n.parent_local_id, index)
                children[n.parent_local_id].append(n)
        for siblings in children.values():
            self.assertEqual([n.position for n in siblings], list(range(len(siblings))))
        for n in tree.nodes:
            if not children[n.local_id] and n.kind not in ('document', 'heading'):
                self.assertIn(n.kind, ('sentence', 'block_formula', 'figure'))
            self.assertTrue(n.content)

    def test_minimal_expected_tree(self):
        tree = parse_version(gathered('\\section{Intro}\nFirst. Second.'))
        index = {n.local_id:n for n in tree.nodes}
        actual = [(n.kind, n.content, index[n.parent_local_id].kind if n.parent_local_id else None) for n in tree.nodes]
        self.assertEqual(actual, [('document','Version 1 root',None), ('heading','Intro','document'),
                         ('paragraph','First. Second.','heading'), ('sentence','First.','paragraph'), ('sentence','Second.','paragraph')])
        self.assertEqual(tree.status, 'parsed')
        self.assert_invariants(tree)

    def test_prose_skipped_levels_ack_and_appendix(self):
        tree = parse_version(gathered('Before.\n\\subsection{Deep {nested} title}\nDeep text.\n'
                             '\\section*{Acknowledgements}\nThanks.\n\\appendix\n\\section{Proof}\nProof text.'))
        hs = [n for n in tree.nodes if n.kind == 'heading']
        self.assertEqual([(n.content,n.heading_level,n.parent_local_id) for n in hs],
                         [('Deep {nested} title',2,'r'), ('Acknowledgements',1,'r'), ('Proof',1,'r')])
        self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'], ['Before.','Deep text.','Thanks.','Proof text.'])
        self.assert_invariants(tree)

    def test_heading_stack_and_short_title(self):
        tree = parse_version(gathered(r'\chapter{C}\section[Short]{Long title}\subsection{A}One.\subsection{B}Two.\section{D}Three.'))
        hs = [n for n in tree.nodes if n.kind=='heading']
        self.assertEqual([n.content for n in hs], ['C','Long title','A','B','D'])
        self.assertEqual([n.parent_local_id for n in hs], ['r', hs[0].local_id, hs[1].local_id, hs[1].local_id, hs[0].local_id])

    def test_paragraph_boundaries(self):
        tree = parse_version(gathered('First.\n\nSecond.\\par Third.'))
        self.assertEqual([n.content for n in tree.nodes if n.kind=='paragraph'], ['First.','Second.','Third.'])

    def test_bibliography_does_not_swallow_appendix(self):
        bib = r'\begin{thebibliography}{99}\bibitem[Author]{a} A {nested {title}}.\end{thebibliography}'
        g = gathered('Body.\n\\section*{References}\n'+bib+'\n\\appendix\n\\section{Appendix}After.')
        blocks = extract_bibliography_blocks(g)
        self.assertEqual([b.raw for b in blocks], [bib])
        span = blocks[0].source_spans[0]
        self.assertEqual(g.latex[span.flat_start:span.flat_end], bib)
        tree = parse_version(g)
        self.assertEqual(tree.bibliography_blocks, blocks)
        self.assertEqual([n.content for n in tree.nodes if n.kind=='heading'], ['Appendix'])
        self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'], ['Body.','After.'])

    def test_bare_bibitems_end_at_heading(self):
        tree = parse_version(gathered(r'\section*{References}\bibitem{a} Alpha. \bibitem{b} Beta.\section*{Acknowledgements}Thanks.'))
        self.assertEqual(len(tree.bibliography_blocks), 1)
        self.assertIn(r'\bibitem{b}', tree.bibliography_blocks[0].raw)
        self.assertNotIn('Thanks', tree.bibliography_blocks[0].raw)
        self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'], ['Thanks.'])

    def test_bibliography_declarations_and_comments(self):
        tree = parse_version(gathered('Text.\n% \\section{Fake}\n\\bibliographystyle{plain}\n\\bibliography{refs}\n\\section{Appendix}After.'))
        self.assertEqual([n.content for n in tree.nodes if n.kind=='heading'], ['Appendix'])
        self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'], ['Text.','After.'])

    def test_literal_bibliography_is_not_extracted(self):
        g = gathered(r'Use \verb|\bibitem{fake}|. \begin{verbatim}\begin{thebibliography}{9}\bibitem{x} X.\end{thebibliography}\end{verbatim}')
        self.assertEqual(extract_bibliography_blocks(g), [])

    def test_inline_and_block_math(self):
        tree = parse_version(gathered(r'We use $x=3.14$ and \(y.\). Next.'+'\n'+
                      r'\begin{equation}x=1\end{equation}$$y=2$$\[z=3\]\begin{align}a&=b\\c&=d\end{align}'))
        self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'], [r'We use $x=3.14$ and \(y.\).','Next.'])
        blocks = [n for n in tree.nodes if n.kind=='block_formula']
        self.assertEqual(len(blocks), 4)
        self.assertIn(r'a&=b\\c&=d', blocks[-1].content)
        self.assert_invariants(tree)

    def test_figure_table_caption_and_rows(self):
        fig = r'\begin{figure}[htpb]\centering\includegraphics{missing}\caption{A caption.}\end{figure}'
        tab = r'\begin{table}\caption{Results}\begin{tabular}{cc}A&B\\\midrule 1&2\end{tabular}\end{table}'
        tree = parse_version(gathered(fig+tab))
        self.assertEqual([(n.content,n.subtype) for n in tree.nodes if n.kind=='figure'], [(fig,'figure'),(tab,'table')])
        self.assert_invariants(tree)

    def test_nested_itemize_formula_and_label(self):
        body = r'\begin{itemize}\item First.\begin{itemize}\item Nested $x$. \[x=1\]\end{itemize}\item[Label] Second.\end{itemize}'
        tree = parse_version(gathered(body))
        lists = [n for n in tree.nodes if n.kind=='itemize']; items = [n for n in tree.nodes if n.kind=='item']
        self.assertEqual(len(lists),2); self.assertEqual(len(items),3)
        self.assertEqual(lists[1].parent_local_id,items[0].local_id)
        self.assertIn('Label',items[-1].content)
        self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'], ['First.','Nested $x$.','Label','Second.'])
        self.assert_invariants(tree)

    def test_comments_percent_commands_and_verb(self):
        body = 'Keep 5\\%. % hidden \\section{Fake}\nStill here.\n'+r'\textbf{A \emph{nested.} phrase}. \verb|\section{Fake} a.b| stays.'
        tree = parse_version(gathered(body))
        self.assertFalse(any(n.kind=='heading' for n in tree.nodes))
        ss = [n.content for n in tree.nodes if n.kind=='sentence']
        self.assertIn(r'Keep 5\%.',ss)
        self.assertTrue(any(r'\emph{nested.}' in s for s in ss))
        self.assertTrue(any(r'\verb|\section{Fake} a.b|' in s for s in ss))
        self.assertFalse(any('hidden' in s for s in ss))

    def test_repeated_sentences_have_correct_occurrence_spans(self):
        g = gathered('Same. Same.'); tree = parse_version(g)
        ss = [n for n in tree.nodes if n.kind=='sentence']; start=g.latex.index('Same.')
        self.assertEqual([n.source_spans[0].start for n in ss],[start,start+6])
        self.assertNotEqual(ss[0].local_id,ss[1].local_id)

    def test_repeated_include_ranges_and_unicode(self):
        g = gathered('α. Same. Same.'); first=g.latex.index('Same.'); second=first+6
        g.source_map = [SourceSpan(path='main.tex',start=0,end=first,flat_start=0,flat_end=first),
            SourceSpan(path='part.tex',start=20,end=25,flat_start=first,flat_end=first+5),
            SourceSpan(path='part.tex',start=20,end=25,flat_start=second,flat_end=second+5)]
        ss = [n for n in parse_version(g).nodes if n.kind=='sentence' and n.content=='Same.']
        self.assertEqual([(n.source_spans[0].path,n.source_spans[0].start,n.source_spans[0].flat_start) for n in ss],
                         [('part.tex',20,first),('part.tex',20,second)])

    def test_cross_file_sentence(self):
        g = gathered('One joined sentence.'); a=g.latex.index('One'); cut=a+4; b=a+len('One joined sentence.')
        g.source_map = [SourceSpan(path='a.tex',start=8,end=12,flat_start=a,flat_end=cut),
                        SourceSpan(path='b.tex',start=0,end=b-cut,flat_start=cut,flat_end=b)]
        n = next(n for n in parse_version(g).nodes if n.kind=='sentence')
        self.assertEqual([(s.path,s.start,s.end) for s in n.source_spans],[('a.tex',8,12),('b.tex',0,b-cut)])

    def test_statuses_and_input_diagnostics(self):
        for status in ('empty_no_tex','blocked_input','failed'):
            g=make_gathered(); g.status=status; g.latex=''; g.root_path=None
            g.diagnostics=[Diagnostic(code='SOURCE_MISSING',severity='error',message='Evidence',arxiv_id=g.version_input.arxiv_id,version=1)]
            t=parse_version(g)
            self.assertEqual(t.status,status); self.assertEqual(t.nodes,[]); self.assertIsNone(t.root_local_id)
            self.assertEqual(t.diagnostics,g.diagnostics)
        g=gathered('Body.'); g.status='partial'
        self.assertEqual(parse_version(g).status,'partial')

    def test_source_status_overrides_ready(self):
        for source,status in [('blocked','blocked_input'),('no_tex','empty_no_tex')]:
            g=gathered('Body.'); g.version_input.source_status=source
            t=parse_version(g); self.assertEqual(t.status,status); self.assertEqual(t.nodes,[])

    def test_unknown_macro_kept_with_error(self):
        t=parse_version(gathered(r'Before. \mystery{Important text.} After.'))
        self.assertEqual(t.status,'partial')
        self.assertTrue(any(d.code=='UNSUPPORTED_CONTENT' and d.severity=='error' for d in t.diagnostics))
        self.assertTrue(any('Important text.' in n.content for n in t.nodes if n.kind=='sentence'))

    def test_malformed_content_diagnosed(self):
        for body in (r'Before. \begin{equation}x=1',r'Before. \begin{itemize}\item A.',r'Before. $unclosed',r'Before. \textbf{unclosed'):
            with self.subTest(body=body):
                t=parse_version(gathered(body))
                self.assertIn(t.status,('partial','failed'))
                self.assertTrue(any(d.severity=='error' for d in t.diagnostics))

    def test_input_immutable_and_output_deterministic(self):
        g=gathered(r'\section{A}Same. Same.'); before=deepcopy(asdict(g))
        self.assertEqual(asdict(parse_version(g)),asdict(parse_version(g)))
        self.assertEqual(asdict(g),before)

    def test_full_components_normalize_idempotently(self):
        body=r'\section{A}Before $x$.\begin{itemize}\item First. \begin{itemize}\item Nested.\end{itemize}\item Second.\end{itemize}'
        raw=parse_version(gathered(body)); bib=make_unified_bibliography(); config=ParseConfig()
        norm=normalize_tree(raw,bib,config)
        self.assertFalse(any(d.severity=='error' for d in norm.diagnostics))
        self.assertEqual(asdict(normalize_tree(norm,bib,config)),asdict(norm))
        self.assertTrue(any(n.kind=='itemize' and 'Nested.' in n.content for n in norm.nodes))
        self.assertIsNone(raw.normalized_with)

    def test_order_changes_component_content(self):
        contents=[]
        for a,b in [('First.','Second.'),('Second.','First.')]:
            t=normalize_tree(parse_version(gathered(r'\begin{itemize}\item '+a+r'\item '+b+r'\end{itemize}')),
                             make_unified_bibliography(),ParseConfig())
            contents.append(next(n.content for n in t.nodes if n.kind=='itemize'))
        self.assertNotEqual(*contents)

    def test_reference_prose_is_separate_and_public_extractor_agrees(self):
        g=gathered(r'Body.\section*{References}Author. Title.'
                   r'\section*{Acknowledgements}Thanks.')
        t=parse_version(g)
        self.assertEqual(t.bibliography_blocks,extract_bibliography_blocks(g))
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Body.','Thanks.'])
        self.assertIn('Author. Title.',t.bibliography_blocks[0].raw)

    def test_group_after_heading_is_body_and_empty_item_does_not_break_ids(self):
        t=parse_version(gathered(r'\section{A}{Grouped text.} After.\begin{itemize}\item\item B.\end{itemize}'))
        self.assertTrue(any('Grouped text.' in n.content for n in t.nodes if n.kind=='sentence'))
        self.assert_invariants(t)

    def test_semantic_list_styles_and_numbering_still_need_review(self):
        for body in (r'\begin{itemize}[label=\alph*]\item Text.\end{itemize}',
                     r'\begin{enumerate}\item Text.\end{enumerate}'):
            t=parse_version(gathered(body))
            self.assertEqual(t.status,'partial')
            self.assertTrue(any(d.code=='UNSUPPORTED_CONTENT' for d in t.diagnostics))

    def test_citation_normalization_dedup_and_validation_consumer(self):
        bib=make_unified_bibliography(); trees=[]
        for version,key in [(1,'alpha'),(2,'beta')]:
            t=parse_version(gathered(r'\section{Intro}Same. See \cite{'+key+'}.',version))
            trees.append(normalize_tree(t,bib,ParseConfig()))
        publication=finalize_publication(assemble_publication(trees,bib))
        self.assertTrue(publication.export_ready)
        self.assertEqual(publication.version_states,{1:'parsed',2:'parsed'})
        self.assertEqual(len([e for e in publication.elements if e.kind=='sentence']),2)
        ss=[o for o in publication.occurrences if o.element_id in {
            e.element_id for e in publication.elements if e.kind=='sentence' and e.content=='Same.'}]
        self.assertEqual(len(ss),2)

    def test_structure_in_standalone_formatting_groups(self):
        t=parse_version(gathered(r'{\small \section{Grouped}Text. '
              r'{\begin{table}\caption{C}\begin{tabular}{c}A\end{tabular}\end{table}}}'
              r'\section{After}End.'))
        self.assertEqual([n.content for n in t.nodes if n.kind=='heading'],['Grouped','After'])
        self.assertEqual(len([n for n in t.nodes if n.kind=='figure' and n.subtype=='table']),1)
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Text.','End.'])
        self.assert_invariants(t)

    def test_table_and_multiline_math_survive_normalization(self):
        body=(r'\begin{table}[htpb]\centering\caption{Results}'
              r'\begin{tabular}{cc}A&B\\\midrule 1&2\end{tabular}\end{table}'
              r'\begin{align}x&=1\\ y&=2\end{align}')
        t=parse_version(gathered(body))
        ns=[normalize_leaf(n,version=1,bibliography=make_unified_bibliography(),config=ParseConfig())
            for n in t.nodes if n.kind in ('figure','block_formula')]
        self.assertIn('Results',ns[0].content)
        self.assertIn('A&B',ns[0].content)
        self.assertIn('1&2',ns[0].content)
        self.assertNotIn(r'\midrule',ns[0].content)
        self.assertIn(r'\begin{equation}',ns[1].content)
        self.assertIn(r'x&=1\\ y&=2',ns[1].content)

    def test_bibliography_spans_across_two_files(self):
        bib=r'\begin{thebibliography}{9}\bibitem{a} A.\end{thebibliography}'
        g=gathered(bib);a=g.latex.index(bib);cut=a+len(bib)//2;end=a+len(bib)
        g.source_map=[SourceSpan(path='one.tex',start=0,end=cut-a,flat_start=a,flat_end=cut),
                      SourceSpan(path='two.tex',start=4,end=4+end-cut,flat_start=cut,flat_end=end)]
        b=extract_bibliography_blocks(g)[0]
        self.assertEqual(b.raw,bib)
        self.assertEqual([s.path for s in b.source_spans],['one.tex','two.tex'])

    def test_crlf_offsets_are_unicode_not_bytes(self):
        g=gathered('α.\r\nNext.')
        ss=[n for n in parse_version(g).nodes if n.kind=='sentence']
        self.assertEqual(ss[1].source_spans[0].start,g.latex.index('Next.'))

    def test_comment_between_short_and_long_heading_arguments(self):
        for heading in ('\\section[Short]% hidden\n{Long title}',
                        '\\section% hidden\n{Long title}'):
            with self.subTest(heading=heading):
                g=gathered(heading+'Body.')
                tree=parse_version(g)
                self.assertEqual([n.content for n in tree.nodes if n.kind=='heading'],['Long title'])
                self.assertEqual([n.content for n in tree.nodes if n.kind=='sentence'],['Body.'])
                self.assertEqual(tree.status,'parsed')

    def test_standalone_appendix_heading_is_outline_metadata_not_a_body_leaf(self):
        from src.parsing.contracts import UnifiedBibliography
        raw=parse_version(gathered(r'Body.\section*{Appendix}\appendix\section{Proof}Proof body.'))
        bib=UnifiedBibliography(arxiv_id=raw.arxiv_id,entries=[],key_map={},occurrences=[])
        publication=finalize_publication(assemble_publication([normalize_tree(raw,bib,ParseConfig())],bib))
        self.assertTrue(publication.export_ready,publication.diagnostics)
        self.assertTrue(any(e.kind=='heading' and e.content=='Appendix' for e in publication.elements))
        self.assertTrue(any(e.kind=='sentence' and e.content=='Proof body.' for e in publication.elements))
        empty=parse_version(gathered(r'\section{}Body.'))
        rejected=finalize_publication(assemble_publication([normalize_tree(empty,bib,ParseConfig())],bib))
        self.assertFalse(rejected.export_ready)
        self.assertTrue(any(d.code=='INVALID_SCHEMA' for d in rejected.diagnostics))

    def test_missing_document_is_failed_with_evidence(self):
        g=make_gathered();g.latex=r'\section{A}No document.'
        t=parse_version(g)
        self.assertEqual(t.status,'failed');self.assertIsNone(t.root_local_id)
        self.assertTrue(any(d.code=='PARSE_FATAL' for d in t.diagnostics))

    def test_excessive_nesting_is_a_failed_version_not_an_exception(self):
        t=parse_version(gathered(r'\begin{quote}'*1100+'Text.'+r'\end{quote}'*1100))
        self.assertEqual(t.status,'failed');self.assertEqual(t.nodes,[])
        self.assertTrue(any(d.code=='PARSE_FATAL' for d in t.diagnostics))

    def test_delimited_math_macro_is_a_formula_with_raw_evidence(self):
        g=gathered(r'Before. \al x&=1.\\y&=2\eal After.')
        prefix=r'\def\al#1\eal{\begin{align}#1\end{align}}'+'\n'
        g.latex=prefix+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        formulas=[n for n in t.nodes if n.kind=='block_formula']
        self.assertEqual(len(formulas),1)
        self.assertEqual(formulas[0].content,r'\al x&=1.\\y&=2\eal')
        self.assertEqual(formulas[0].subtype,'align')
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Before.','After.'])
        self.assertTrue(any('normaliz' in d.message.lower() for d in t.diagnostics))

    def test_separate_math_aliases_and_declared_theorem(self):
        g=gathered(r'\begin{claimbox}Claim.\end{claimbox}\be x=1\ee')
        g.latex=r'\newtheorem{claimbox}{Claim}\newcommand{\be}{\begin{equation}}\def\ee{\end{equation}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        self.assertEqual([n.content for n in t.nodes if n.kind=='block_formula'],[r'\be x=1\ee'])
        self.assertFalse(any('Unsupported environment claimbox' in d.message for d in t.diagnostics))

    def test_delimited_math_terminator_does_not_consume_following_group(self):
        g=gathered(r'Before.\al {x}&=1\eal{After.} Tail.')
        g.latex=r'\def\al#1\eal{\begin{align}#1\end{align}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        before=deepcopy(g)
        t=parse_version(g)
        formula=next(n for n in t.nodes if n.kind=='block_formula')
        self.assertEqual(formula.content,r'\al {x}&=1\eal')
        self.assertEqual(formula.subtype,'align')
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],
                         ['Before.','{After.} Tail.'])
        self.assertEqual(formula.source_spans[0].end,g.latex.index('{After.}'))
        self.assertEqual(g,before)
        self.assert_invariants(t)

    def test_nested_itemize_retains_adjacent_tail_and_formula_source_ranges(self):
        body=(r'\begin{itemize}\item Outer.\begin{itemize}\item Inner.'
              r'\[x=1\]\end{itemize}After.\end{itemize}')
        g=gathered(body)
        t=parse_version(g)
        outer,inner=[n for n in t.nodes if n.kind=='itemize']
        outer_item,inner_item=[n for n in t.nodes if n.kind=='item']
        tail=next(n for n in t.nodes if n.kind=='sentence' and n.content=='After.')
        tail_paragraph=next(n for n in t.nodes if n.local_id==tail.parent_local_id)
        formula=next(n for n in t.nodes if n.kind=='block_formula')
        self.assertEqual(t.status,'parsed')
        self.assertEqual(t.diagnostics,[])
        self.assertEqual(outer.content,body)
        self.assertEqual(inner.parent_local_id,outer_item.local_id)
        self.assertEqual(inner_item.parent_local_id,inner.local_id)
        self.assertEqual(formula.parent_local_id,inner_item.local_id)
        self.assertEqual(tail_paragraph.parent_local_id,outer_item.local_id)
        self.assertEqual([n.kind for n in t.nodes if n.parent_local_id==outer_item.local_id],
                         ['paragraph','itemize','paragraph'])
        self.assertEqual(formula.content,r'\[x=1\]')
        self.assertEqual(tail.source_spans[0].start,g.latex.index('After.'))
        self.assertEqual(formula.source_spans[0].start,g.latex.index(r'\[x=1\]'))
        self.assert_invariants(t)

    def test_declared_inline_macro_and_standard_author_commands(self):
        g=gathered(r'\title{A title}\author{A Name}\textup{Upright.} A \modelname{arg.} works.')
        g.latex=r'\newcommand{\modelname}[1]{\textbf{#1}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        self.assertEqual(t.status,'parsed')
        self.assertTrue(any(r'\modelname{arg.}' in n.content for n in t.nodes))
        self.assertTrue(any(d.code=='MACRO_PRESERVED' and d.severity=='warning' for d in t.diagnostics))

    def test_literal_environments_preserved_without_fake_structure(self):
        g=gathered(r'\begin{verbatim}\section{Fake} A. B.\end{verbatim} Next.')
        t=parse_version(g)
        self.assertEqual(t.status,'parsed')
        self.assertFalse(any(n.kind=='heading' for n in t.nodes))
        self.assertTrue(any(r'\section{Fake}' in n.content for n in t.nodes))

    def test_zero_arity_command_does_not_swallow_following_group(self):
        t=parse_version(gathered(r'\begin{itemize}\item First. {\begin{itemize}\item Second.\end{itemize}}\end{itemize}'))
        self.assertEqual(len([n for n in t.nodes if n.kind=='itemize']),2)
        self.assert_invariants(t)

    def test_list_options_with_nested_brackets_do_not_create_an_item(self):
        t=parse_version(gathered(r'\begin{itemize}[label={\textbf{[x]}}]\item Text.\end{itemize}'))
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Text.'])
        self.assertEqual(len([n for n in t.nodes if n.kind=='item']),1)

    def test_unknown_nested_macro_is_not_silently_promoted(self):
        g=gathered(r'A \outer{Text.} continues.')
        g.latex=r'\newcommand{\outer}[1]{\mystery{#1}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        self.assertEqual(parse_version(g).status,'partial')

    def test_minipage_width_is_not_body_prose(self):
        t=parse_version(gathered(r'\begin{minipage}[t]{0.5\textwidth}Text.\end{minipage}'))
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Text.'])

    def test_layout_redefinition_does_not_remove_heading_argument(self):
        g=gathered(r'\section{Introduction}Text.')
        g.latex=r'\renewcommand{\section}{\@startsection{section}{1}{0}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        self.assertEqual([n.content for n in parse_version(g).nodes if n.kind=='heading'],['Introduction'])

    def test_labeled_math_closing_alias_balances_environment(self):
        g=gathered(r'\be x&=1\ee{eq:one} After.')
        g.latex=r'\def\be{\begin{eqnarray}}\def\ee#1{\label{#1}\end{eqnarray}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        self.assertFalse(any(d.message.startswith('Unbalanced environment') for d in t.diagnostics))
        self.assertEqual([n.content for n in t.nodes if n.kind=='block_formula'],[r'\be x&=1\ee{eq:one}'])


    def test_appendix_heading_alias_keeps_title_and_level(self):
        g=gathered(r'\appendix\appendixsubsection{Details}Proof.')
        g.latex=r'\newcommand{\appendixsubsection}[1]{\addcontentsline{toc}{subsection}{#1}\subsection*{#1}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        self.assertEqual([(n.content,n.heading_level) for n in parse_version(g).nodes if n.kind=='heading'],[('Details',2)])

    def test_algorithm_float_retains_caption_and_statement_order(self):
        body=r'\begin{algorithm}\caption{Procedure}\begin{algorithmic}\State First\State Second\end{algorithmic}\end{algorithm}'
        t=parse_version(gathered(body))
        nodes=[n for n in t.nodes if n.kind=='figure']
        self.assertEqual(len(nodes),1);self.assertEqual(nodes[0].subtype,'algorithm')
        self.assertEqual(nodes[0].content,body)
        self.assertEqual(t.status,'parsed')

    def test_body_macro_definition_is_not_rendered_as_prose(self):
        t=parse_version(gathered(r'Before.\renewcommand{\x}{Not printed.}After.'))
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Before.','After.'])
        self.assertEqual(t.status,'partial')


    def test_math_intervals_after_operators_do_not_hide_environment_ends(self):
        body=(r'\begin{equation}\begin{aligned}x\in[0,1)'
              r'\cup[2,3)\end{aligned}\end{equation}\section{After}Text.')
        t=parse_version(gathered(body))
        self.assertEqual(t.status,'parsed')
        self.assertEqual(len([n for n in t.nodes if n.kind=='block_formula']),1)
        self.assertEqual([n.content for n in t.nodes if n.kind=='heading'],['After'])


    def test_conditional_macro_definition_is_not_assumed_active(self):
        g=gathered(r'Before. \be x=1\ee After.')
        g.latex=r'\iffalse\def\be{\begin{equation}}\def\ee{\end{equation}}\fi'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        self.assertFalse(any(n.kind=='block_formula' for n in t.nodes))
        self.assertEqual(t.status,'partial')


    def test_heading_macro_with_extra_text_is_not_truncated(self):
        g=gathered(r'\myheading{Title}Body.')
        g.latex=r'\newcommand{\myheading}[1]{Extra text.\section{#1}}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        self.assertEqual(parse_version(g).status,'partial')
        self.assertFalse(any(n.kind=='heading' for n in parse_version(g).nodes))


    def test_empty_nested_list_does_not_leave_an_item_leaf(self):
        t=parse_version(gathered(r'\begin{itemize}\item\begin{itemize}\item\end{itemize}\end{itemize}After.'))
        self.assertEqual([n.kind for n in t.nodes],['document','paragraph','sentence'])
        self.assertEqual(t.nodes[-1].content,'After.')
        self.assert_invariants(t)
        self.assertEqual(t.status,'partial')


    def test_bibliography_options_do_not_become_body_sentences(self):
        t=parse_version(gathered(r'Before.\printbibliography[title={References},heading=bibintoc]'
                                 r'\section{Appendix}After.'))
        self.assertEqual([n.content for n in t.nodes if n.kind=='sentence'],['Before.','After.'])

    def test_zero_argument_layout_commands_do_not_consume_prose_groups(self):
        for command in ('raggedright','raggedleft','normalfont','tableofcontents'):
            with self.subTest(command=command):
                t=parse_version(gathered('\\'+command+'{Important text.}'))
                self.assertTrue(any('Important text.' in n.content for n in t.nodes if n.kind=='sentence'))


    def test_cr_only_comments_and_paragraphs_preserve_document(self):
        g=gathered('First.\n\nSecond.')
        g.latex=g.latex.replace('\n','\r').replace('\\begin{document}', '% preamble comment\r\\begin{document}')
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        self.assertEqual(t.status,'parsed')
        self.assertEqual([n.content for n in t.nodes if n.kind=='paragraph'],['First.','Second.'])
        self.assertEqual([n.source_spans[0].start for n in t.nodes if n.kind=='sentence'],
                         [g.latex.index('First.'),g.latex.index('Second.')])


    def test_declared_algorithm_theorem_preserves_nested_itemize(self):
        g=gathered(r'\begin{algorithm}\begin{itemize}\item First.'
                   r'\begin{itemize}\item Second.\[x=1\]\end{itemize}\end{itemize}\end{algorithm}')
        g.latex=r'\newtheorem{algorithm}{Algorithm}'+g.latex
        g.source_map=[SourceSpan(path='main.tex',start=0,end=len(g.latex),flat_start=0,flat_end=len(g.latex))]
        t=parse_version(g)
        self.assertEqual(len([n for n in t.nodes if n.kind=='itemize']),2)
        self.assertEqual(len([n for n in t.nodes if n.kind=='block_formula']),1)
        self.assertFalse(any(n.kind=='figure' for n in t.nodes))
        self.assert_invariants(t)


if __name__ == "__main__":
    unittest.main()
