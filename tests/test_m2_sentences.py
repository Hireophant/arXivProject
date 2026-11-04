"""Khang KG2 / S3: independently specified sentence boundaries."""
import unittest
from src.parsing.sentences import split_sentences


class SentenceTests(unittest.TestCase):
    def test_protected_boundaries(self):
        cases = [
            ('As in Fig. 1, we use $x=3.14$. It works.', ['As in Fig. 1, we use $x=3.14$.', 'It works.']),
            ('We use i.e. a test, e.g. this one. Done.', ['We use i.e. a test, e.g. this one.', 'Done.']),
            ('Smith et al. report this in Eq. 2. We agree.', ['Smith et al. report this in Eq. 2.', 'We agree.']),
            (r'See \ref{sec.1} and \cite{a,b}. Next.', [r'See \ref{sec.1} and \cite{a,b}.', 'Next.']),
            (r'A \textbf{nested \emph{a. b.} phrase} works. Next.', [r'A \textbf{nested \emph{a. b.} phrase} works.', 'Next.']),
            ('See https://example.org/a.b?q=3.14. Next sentence.', ['See https://example.org/a.b?q=3.14.', 'Next sentence.']),
            ('Use www.example.org/path and doi:10.1234/a.b. Next.', ['Use www.example.org/path and doi:10.1234/a.b.', 'Next.']),
            (r'Use \url{https://a.b/x.y}. Done.', [r'Use \url{https://a.b/x.y}.', 'Done.']),
            (r'Use \(x=1.2\) and $y.$ together. Next.', [r'Use \(x=1.2\) and $y.$ together.', 'Next.']),
            (r'Literal \verb|a. \section{X} b.| stays. Next.', [r'Literal \verb|a. \section{X} b.| stays.', 'Next.']),
            ('Use {a. {b.} c.} as a group. Next.', ['Use {a. {b.} c.} as a group.', 'Next.']),
            ('Value 3.14 and v1.2 are stable. Tail without punctuation', ['Value 3.14 and v1.2 are stable.', 'Tail without punctuation']),
            ('He said "Yes." Next.', ['He said "Yes."', 'Next.']),
            ('Really? Yes! Fine.', ['Really?', 'Yes!', 'Fine.']),
            ('Repeat. Repeat.', ['Repeat.', 'Repeat.']),
            ('A % hidden. not a sentence\ncontinues. End.', ['A % hidden. not a sentence\ncontinues.', 'End.']),
            (r'A costs 5\%. Next.', [r'A costs 5\%.', 'Next.']),
            ('Dr. Smith uses U.S. data. Next.', ['Dr. Smith uses U.S. data.', 'Next.']),
            (r'Use \begin{math}x. y\end{math}. Next.', [r'Use \begin{math}x. y\end{math}.', 'Next.']),
            (r'Value \$5. End.', [r'Value \$5.', 'End.']),
            (r'See \url{https://example.org/a%20b}. Next.', [r'See \url{https://example.org/a%20b}.', 'Next.']),
            (r'See \cite[also {a]b}]{key}. Next.', [r'See \cite[also {a]b}]{key}.', 'Next.']),
            ('A % comment.\rcontinues. Next.', ['A % comment.\rcontinues.', 'Next.']),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(split_sentences(text), expected)

    def test_whitespace_only(self):
        for text in ('', ' ', '\n\t\r\n'):
            self.assertEqual(split_sentences(text), [])

    def test_preserves_whitespace_unicode_and_tail(self):
        self.assertEqual(split_sentences('  Tiếng Việt  $α = 1.2$.\n  Next. '), ['Tiếng Việt  $α = 1.2$.', 'Next.'])
        self.assertEqual(split_sentences('No final punctuation'), ['No final punctuation'])

    def test_unclosed_region_is_not_silently_split(self):
        for text in (r'Unfinished $x. Next.', r'Unfinished \textbf{a. Next.'):
            self.assertEqual(split_sentences(text), [text])


if __name__ == "__main__":
    unittest.main()
