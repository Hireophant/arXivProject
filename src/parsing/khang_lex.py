"""Private lexical scanner shared by Khang's hierarchy and sentence modules.

Offsets always refer to the original Unicode string. This is a bounded LaTeX
scanner, not a TeX interpreter: no macro expansion, catcode changes or file I/O.
Opaque arguments/math/literals keep structural lookalikes out of the token stream.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator

_COMMAND = re.compile(r'\\([A-Za-z@]+|[^A-Za-z@])')
_NEWLINE = re.compile(r'\r\n|\r|\n')
_NL = r'(?:\r\n|\r(?!\n)|(?<!\r)\n)'
_BLANK = re.compile(_NL+r'[ \t]*'+_NL+r'(?:[ \t]*'+_NL+r')*')
LITERAL_ENVS = frozenset(('verbatim', 'verbatim*', 'Verbatim', 'lstlisting', 'minted', 'comment'))
MATH_ENVS = frozenset(('equation', 'equation*', 'displaymath', 'align', 'align*',
                       'alignat', 'alignat*', 'gather', 'gather*', 'multline', 'multline*',
                       'eqnarray', 'eqnarray*', 'flalign', 'flalign*', 'math'))
_HEADINGS = frozenset(('part', 'chapter', 'section', 'subsection', 'subsubsection', 'paragraph', 'subparagraph'))
_NO_ARGS = frozenset(('appendix', 'par', 'maketitle', 'centering', 'noindent', 'newpage',
                      'clearpage', 'smallskip', 'medskip', 'bigskip', 'hfill', 'vfill',
                      'relax', 'protect', 'bfseries', 'itshape', 'rmfamily', 'sffamily',
                      'ttfamily', 'small', 'large', 'Large', 'tiny', 'footnotesize',
                      'normalsize', 'scriptsize', 'else', 'fi'))
_NO_ARGS = _NO_ARGS | frozenset(('tableofcontents','listoffigures','listoftables',
    'cleardoublepage','raggedright','raggedleft','normalfont','scshape','phantomsection'))
_ARITIES = {name:1 for name in ('textbf','textit','textup','textsl','textsc','textsf','textrm',
    'texttt','emph','textnormal','underline','section','subsection','subsubsection','chapter',
    'paragraph','subparagraph','caption','label','ref','eqref','autoref','cref','Cref','cite',
    'citep','citet','citealt','citealp','citeauthor','citeyear','citeyearpar','url','path','nolinkurl',
    'title','author','date','email','affiliation','affil','keywords','footnote','footnotetext',
    'thanks','bibliography','bibliographystyle','bibitem','ensuremath','sqrt','mathrm','mathbf',
    'mathcal','mathbb','text','operatorname','hat','bar','tilde','vec','dot','ddot')}
_ARITIES.update({'href':2,'frac':2,'dfrac':2,'tfrac':2,'textcolor':2,'setlength':2,
                 'addtolength':2,'setcounter':2,'addtocounter':2,'includegraphics':1,'addcontentsline':3})
_DECLARATIONS = frozenset(('newcommand','renewcommand','providecommand','DeclareRobustCommand',
                          'DeclareMathOperator','newtheorem','newenvironment','renewenvironment'))
_OPTIONAL = _HEADINGS | _DECLARATIONS | frozenset(('cite','citep','citet','citealt','citealp',
    'citeauthor','citeyear','citeyearpar','Cite','Citep','Citet','autocite','parencite',
    'textcite','footcite','smartcite','item','bibitem','sqrt','includegraphics',
    'footnote','footnotetext','author','title','lstinline'))
_OPTIONAL = _OPTIONAL | frozenset(('printbibliography','addbibresource'))


@dataclass(frozen=True)
class Token:
    kind: str
    start: int
    end: int
    name: str = ''
    argument: tuple[int, int] | None = None
    malformed: bool = False


def line_end(text: str, start: int) -> int:
    """First physical newline, preserving LF/CRLF/CR offsets without conversion."""
    match=_NEWLINE.search(text,start)
    return match.start() if match else len(text)


def group_end(text: str, start: int, opener: str = '{', closer: str = '}', *, comments: bool = True) -> tuple[int, bool]:
    """Balanced group, excluding escaped delimiters and comments from nesting."""
    depth = 1
    braces = 0
    i = start + 1
    while i < len(text):
        char = text[i]
        if char == '\\':
            # A verbatim command can contain literal braces and percent signs.
            m = _COMMAND.match(text, i)
            if m and m[1] == 'verb':
                end, ok = _verb_end(text, m.end())
                i = end
                if not ok:
                    return i, False
            else:
                i += 2
            continue
        if char == '%' and comments:
            i = line_end(text,i)
            continue
        if opener == '[':
            if char == '{':
                braces += 1
            elif char == '}':
                braces -= 1
            if braces or char == '}':
                i += 1
                continue
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return i + 1, True
        i += 1
    return len(text), False


def _verb_end(text: str, start: int) -> tuple[int, bool]:
    i = start + (start < len(text) and text[start] == '*')
    if i >= len(text) or text[i].isspace():
        return i, False
    end = text.find(text[i], i + 1)
    return (len(text), False) if end < 0 else (end + 1, True)


def _delimited_end(text: str, start: int, closing: str) -> tuple[int, bool]:
    i = start
    while i < len(text):
        if text.startswith(closing, i):
            return i + len(closing), True
        if text[i] == '%':
            i = line_end(text,i)
        elif text[i] == '\\':
            i += 2
        else:
            i += 1
    return len(text), False


def scan(text: str, *, arities: dict[str,int] | None = None) -> Iterator[Token]:
    """Scan once; command arguments are opaque and never cleaned or expanded."""
    i, plain = 0, 0
    while i < len(text):
        token = None
        char = text[i]
        if char == '%':
            token = Token('comment', i, line_end(text,i))
        elif char == '$' or text.startswith(('\\(', '\\['), i):
            opening = '$$' if text.startswith('$$', i) else text[i:i+2] if char == '\\' else '$'
            closing = {'\\(': '\\)', '\\[': '\\]'}.get(opening, opening)
            end, ok = _delimited_end(text, i + len(opening), closing)
            token = Token('block' if opening in ('$$', '\\[') else 'inline', i, end, opening, malformed=not ok)
        elif char == '\\':
            m = _COMMAND.match(text, i)
            if m is None:
                token = Token('command', i, i+1, malformed=True)
            else:
                name, end = m[1], m.end()
                if name in ('def','gdef','edef','xdef'):
                    p=end
                    while p<len(text) and text[p].isspace(): p+=1
                    target=_COMMAND.match(text,p)
                    opening=text.find('{',target.end()) if target else -1
                    if opening>=0:
                        end,ok=group_end(text,opening)
                        token=Token('declaration',i,end,name,malformed=not ok)
                    else:
                        token=Token('declaration',i,end,name,malformed=True)
                elif name in ('verb','lstinline'):
                    if name=='lstinline':
                        p=end
                        while p<len(text) and text[p].isspace(): p+=1
                        if p<len(text) and text[p]=='[':
                            end,_=group_end(text,p,'[',']')
                    end, ok = _verb_end(text, end)
                    token = Token('literal', i, end, name, malformed=not ok)
                else:
                    if end < len(text) and text[end] == '*':
                        end += 1
                    argument = None
                    malformed = False
                    # begin/end consume only the environment name, not body groups.
                    # A zero-argument layout redefinition of section often
                    # forwards its following title to @startsection. Preserve
                    # the intrinsic structural signature of known commands.
                    limit = _ARITIES.get(name,(arities or {}).get(name,1))
                    if name in _NO_ARGS or len(name)==1: limit=0
                    if name in _DECLARATIONS: limit=1000000
                    if name=='item': limit=1
                    count = 0
                    while count < limit:
                        p = end
                        while p < len(text) and text[p].isspace():
                            p += 1
                        if p >= len(text) or text[p] not in ('{', '['):
                            break
                        if text[p]=='[' and name not in _OPTIONAL:
                            break
                        if name == 'item' and text[p] != '[':
                            break
                        opener = text[p]
                        literal_url = name in ('url','path','nolinkurl') or (name=='href' and argument is None)
                        q, ok = group_end(text, p, opener, '}' if opener == '{' else ']', comments=not literal_url)
                        if argument is None and (opener == '{' or name == 'item'):
                            argument = (p + 1, q - 1 if ok else q)
                        end, malformed = q, malformed or not ok
                        if opener=='{' or name=='item': count += 1
                        if name in _HEADINGS and opener == '{':
                            break
                        if not ok:
                            break
                    if name in ('begin', 'end') and argument is not None:
                        env = text[argument[0]:argument[1]].strip()
                        if name=='begin' and env in ('itemize','enumerate','description','minipage'):
                            p=end
                            while p<len(text) and text[p].isspace(): p+=1
                            if p<len(text) and text[p]=='[':
                                end,ok=group_end(text,p,'[',']')
                                malformed=malformed or not ok
                            if env=='minipage':
                                p=end
                                while p<len(text) and text[p].isspace(): p+=1
                                if p<len(text) and text[p]=='{':
                                    end,ok=group_end(text,p)
                                    malformed=malformed or not ok
                        if name == 'begin' and env in LITERAL_ENVS:
                            closing = '\\end{' + env + '}'
                            stop = text.find(closing, end)
                            token = Token('comment' if env == 'comment' else 'literal', i,
                                          len(text) if stop < 0 else stop+len(closing), env, malformed=stop < 0)
                        else:
                            token = Token(name, i, end, env, argument, malformed)
                    else:
                        token = Token('declaration' if name in _DECLARATIONS else 'command', i, end, name, argument, malformed)
        elif char == '{':
            end, ok = group_end(text, i)
            token = Token('group', i, end, malformed=not ok)
        elif char == '\n' or char == '\r':
            m = _BLANK.match(text, i)
            if m:
                token = Token('break', i, m.end())
        if token is None:
            i += 1
            continue
        if plain < i:
            yield Token('text', plain, i)
        yield token
        i = plain = token.end
    if plain < len(text):
        yield Token('text', plain, len(text))
