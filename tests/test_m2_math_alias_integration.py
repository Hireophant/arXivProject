"""Declared math aliases must normalize using actual gathered declaration evidence."""
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.parsing.contracts import ParseConfig,PublicationInput,VersionInput
from src.parsing.pipeline import process_publication

SCRATCH=Path(__file__).resolve().parents[1]/'data/milestone2-dev/integration'


class MathAliasIntegrationTests(unittest.TestCase):
    def parse(self,preamble,body):
        SCRATCH.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=SCRATCH) as temporary:
            root=Path(temporary)
            text=r'\documentclass{article}'+preamble+r'\begin{document}'+body+r'\end{document}'
            (root/'main.tex').write_text(text,encoding='utf-8')
            version=VersionInput(arxiv_id='2606.20274',version=1,source_dir=root,source_status='tex',
                                 source_fingerprint=hashlib.sha256(text.encode()).hexdigest())
            publication=PublicationInput(arxiv_id=version.arxiv_id,versions=[version],snapshot_id='a'*64,
                                         preparation_run_id='synthetic-alias-test',corpus_root=root)
            return process_publication(publication,ParseConfig(code_revision='test-aliases'))

    def test_delimited_align_macro_becomes_equation_and_keeps_following_text(self):
        out=self.parse(r'\def\al#1\eal{\begin{align}#1\end{align}}',
                       r'Before.\al x&=1\\y&=2\eal{After.} Tail.')
        self.assertTrue(out.export_ready,out.diagnostics)
        formula,=[e.content for e in out.elements if e.kind=='block_formula']
        self.assertEqual(formula,r'\begin{equation}\begin{aligned}x&=1\\y&=2\end{aligned}\end{equation}')
        self.assertTrue(any('After.' in e.content for e in out.elements if e.kind=='sentence'))

    def test_closing_alias_argument_preserves_equation_label(self):
        out=self.parse(r'\def\be{\begin{eqnarray}}\def\ee#1{\label{#1}\end{eqnarray}}',
                       r'\be x&=1\ee{eq:one} After.')
        self.assertTrue(out.export_ready,out.diagnostics)
        formula,=[e.content for e in out.elements if e.kind=='block_formula']
        self.assertIn(r'\label{eq:one}',formula)
        self.assertIn(r'\begin{equation}',formula)

    def test_alias_in_nested_list_has_consistent_parent_content(self):
        out=self.parse(r'\newcommand{\startmath}{\begin{equation}}\def\stopmath{\end{equation}}',
                       r'\begin{itemize}\item Before.\begin{itemize}\item '
                       r'\startmath{x}^2=1\stopmath\end{itemize}After.\end{itemize}')
        self.assertTrue(out.export_ready,out.diagnostics)
        self.assertTrue(any(e.kind=='block_formula' and '{x}^2=1' in e.content for e in out.elements))

    def test_literal_alias_examples_are_not_expanded(self):
        out=self.parse(r'\newcommand{\be}{\begin{equation}}\def\ee{\end{equation}}',
                       r'Example \verb|\be x\ee|.\be x=1\ee')
        self.assertTrue(out.export_ready,out.diagnostics)
        self.assertTrue(any(r'\verb|\be x\ee|' in e.content for e in out.elements if e.kind=='sentence'))

    def test_undefined_alias_is_not_guessed(self):
        out=self.parse('',r'\be Important text.\ee After.')
        self.assertFalse(out.export_ready)
        self.assertTrue(any('Important text.' in e.content for e in out.elements))

    def test_multiple_closing_arguments_are_substituted_without_rewriting_argument_bytes(self):
        out=self.parse(r'\def\be{\begin{equation}}\def\ee#1#2{\label{#1:#2}\end{equation}}',
                       r'\be x=1\ee{part\#2}{last}')
        self.assertTrue(out.export_ready,out.diagnostics)
        self.assertTrue(any(r'\label{part\#2:last}' in e.content for e in out.elements if e.kind=='block_formula'))

    def test_star_after_delimited_opener_remains_in_the_math_body(self):
        out=self.parse(r'\def\al#1\eal{\begin{align}#1\end{align}}',r'\al*x=1\eal')
        self.assertTrue(out.export_ready,out.diagnostics)
        self.assertTrue(any(r'\begin{aligned}*x=1' in e.content for e in out.elements if e.kind=='block_formula'))

    def test_unsupported_redefinition_invalidates_prior_math_proof(self):
        out=self.parse(r'\def\be{\begin{equation}}\def\ee{\end{equation}}'
                       r'\renewcommand{\be}[1][Opening]{#1}\renewcommand{\ee}[1][Closing]{#1}',
                       r'\be Important meaning.\ee')
        self.assertFalse(out.export_ready)
        self.assertFalse(any(e.kind=='block_formula' for e in out.elements))

    def test_providecommand_does_not_replace_an_existing_macro(self):
        out=self.parse(r'\def\be{Opening}\providecommand{\be}{\begin{equation}}',
                       r'\be Important meaning.')
        self.assertTrue(out.export_ready,out.diagnostics)
        self.assertFalse(any(e.kind=='block_formula' for e in out.elements))

    def test_let_copies_the_current_meaning_not_a_future_redefinition(self):
        out=self.parse(r'\def\be{Opening}\let\start=\be\def\be{\begin{equation}}',
                       r'\start Important meaning.')
        self.assertTrue(out.export_ready,out.diagnostics)
        self.assertFalse(any(e.kind=='block_formula' for e in out.elements))
