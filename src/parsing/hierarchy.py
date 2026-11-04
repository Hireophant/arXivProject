"""Occurrence hierarchy from gathered LaTeX (Khang / KG1, KG3).

The scanner keeps raw offsets, opaque arguments, math and literal regions. An
indexed source map maps every occurrence back to its source, including repeated
includes. No gathering, macro expansion, normalization or deduplication here.
Unsupported content stays in the raw tree with an error rather than disappearing.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import replace
import re

from .contracts import BibliographyBlock, Diagnostic, GatherResult, RawNode, SourceSpan, VersionTree
from .khang_lex import MATH_ENVS, Token, scan
from .khang_macros import declarations
from .sentences import _sentence_ranges

_HEADINGS = {'part': 0, 'chapter': 0, 'section': 1, 'subsection': 2,
             'subsubsection': 3, 'paragraph': 4, 'subparagraph': 5}
_LISTS = frozenset(('itemize', 'enumerate', 'description'))
_FLOATS = frozenset(('figure', 'figure*', 'table', 'table*', 'tabular', 'tabular*', 'longtable'))
_FLOATS = _FLOATS | frozenset(('Figure','deluxetable','deluxetable*','tabularx','tabularx*',
    'tabulary','sidewaystable','sidewaystable*','sidewaysfigure','wrapfigure','wraptable',
    'algorithm','algorithm*','algorithm2e','algorithmic','algorithmicx','tikzpicture','tikzcd'))
_TRANSPARENT = frozenset(('center', 'flushleft', 'flushright', 'quote', 'quotation',
                          'abstract', 'proof', 'theorem', 'lemma', 'proposition',
                          'corollary', 'definition', 'remark', 'example', 'claim',
                          'conjecture', 'solution', 'acknowledgements', 'acknowledgments',
                          'appendix', 'appendices', 'subequations'))
_TRANSPARENT = _TRANSPARENT | frozenset(('minipage','sloppypar','centering','widetext',
    'frontmatter','titlepage','samepage','multicols','ack','acks','acknowledgement',
    'IEEEkeywords','keywords','keyword','highlights','credits'))
_METADATA = frozenset(('label', 'bibliography', 'bibliographystyle', 'addbibresource',
                       'printbibliography', 'nocite', 'maketitle', 'tableofcontents',
                       'listoffigures', 'listoftables', 'appendix', 'newpage',
                       'clearpage', 'cleardoublepage', 'pagebreak', 'noindent',
                       'centering', 'raggedright', 'raggedleft', 'smallskip',
                       'medskip', 'bigskip', 'vspace', 'hspace', 'vfill', 'hfill',
                       'setcounter', 'pagestyle', 'thispagestyle'))
_METADATA = _METADATA | frozenset(('bfseries', 'itshape', 'scshape', 'rmfamily',
    'sffamily', 'ttfamily', 'normalfont', 'small', 'large', 'Large', 'tiny',
    'footnotesize', 'scriptsize', 'normalsize'))
# These commands are preserved raw; Danh owns actual cleanup and citation rewrite.
_PROSE_COMMANDS = frozenset(('textbf', 'textit', 'emph', 'textrm', 'textsf', 'texttt',
    'textsc', 'textnormal', 'text', 'underline', 'mbox', 'makebox', 'fbox',
    'ref', 'eqref', 'autoref', 'cref', 'Cref', 'pageref', 'url', 'href', 'path', 'nolinkurl',
    'cite', 'citep', 'citet', 'citealt', 'citealp', 'citeauthor', 'citeyear', 'citeyearpar',
    'Citep', 'Citet', 'Cite', 'autocite', 'parencite', 'textcite', 'footcite', 'smartcite',
    'footnote', 'footnotetext', 'thanks', 'LaTeX', 'TeX', 'ldots', 'dots', 'textbackslash', 'textasciitilde',
    'textasciicircum', 'textpercent', 'textendash', 'textemdash', 'textquotedblleft',
    'textquotedblright', 'textquoteleft', 'textquoteright', 'textregistered', 'copyright',
    'textsuperscript', 'textsubscript', 'ensuremath', 'protect', 'relax', 'normalfont',
    'bfseries', 'itshape', 'scshape', 'rmfamily', 'sffamily', 'ttfamily', 'small', 'large',
    'Large', 'tiny', 'footnotesize', 'scriptsize', 'normalsize', 'color', 'textcolor',
    'index', 'hypertarget', 'hyperref', 'newline', 'linebreak'))
_PROSE_COMMANDS = _PROSE_COMMANDS | frozenset(('textup','textsl','title','author','date',
    'affiliation','affil','email','altaffiliation','ead','keywords','keyword','thanks'))
_REF_TITLES = frozenset(('references', 'bibliography', 'literature cited', r'\refname', r'\bibname'))


def _tokens(text: str) -> list[Token]:
    r"""Open standalone TeX groups containing structure, never command arguments.

    A formatting scope such as {\small \begin{table}...} must still yield a
    figure. Ordinary prose groups stay opaque to the sentence splitter.
    """
    declared=declarations(text)
    def expand(token: Token, depth: int) -> list[Token]:
        if token.kind=='command' and token.name in declared.math_aliases:
            kind,name=declared.math_aliases[token.name]
            token=replace(token,kind=kind,name=name)
        elif token.kind=='command' and token.name in declared.heading_aliases:
            token=replace(token,name=declared.heading_aliases[token.name])
        if token.kind!='group' or token.malformed or depth>=64:
            return [token]
        inner=[replace(t,start=t.start+token.start+1,end=t.end+token.start+1,
                       argument=(t.argument[0]+token.start+1,t.argument[1]+token.start+1) if t.argument else None)
               for t in scan(text[token.start+1:token.end-1],arities=declared.arities)]
        opened=[]
        for child in inner:
            opened.extend(expand(child,depth+1))
        if not any(t.kind in ('begin','end','block') or
                   (t.kind=='command' and (t.name in _HEADINGS or t.name=='item')) for t in opened):
            return [token]
        return [Token('group_delimiter',token.start,token.start+1), *opened,
                Token('group_delimiter',token.end-1,token.end)]
    result=[]
    for token in scan(text,arities=declared.arities):
        result.extend(expand(token,0))
    return result


class _SourceIndex:
    def __init__(self, spans: list[SourceSpan]):
        self.spans = sorted((s for s in spans if s.flat_start is not None and s.flat_end is not None),
                            key=lambda s: s.flat_start)
        self.ends = [s.flat_end for s in self.spans]

    def ranges(self, start: int, end: int) -> list[SourceSpan]:
        result = []
        i = bisect_right(self.ends, start)
        while i < len(self.spans):
            span = self.spans[i]
            if span.flat_start >= end:
                break
            a, b = max(start, span.flat_start), min(end, span.flat_end)
            if a < b:
                result.append(SourceSpan(path=span.path, start=span.start+a-span.flat_start,
                    end=span.start+b-span.flat_start, flat_start=a, flat_end=b))
            i += 1
        return result


def _environment_pairs(tokens: list[Token]) -> tuple[dict[int, int], list[Token]]:
    pairs, stack, errors = {}, [], []
    for i,t in enumerate(tokens):
        if t.kind == 'begin':
            stack.append(i)
        elif t.kind == 'end':
            if stack and tokens[stack[-1]].name == t.name:
                begin = stack.pop()
                pairs[begin] = i
            else:
                errors.append(t)
    errors.extend(tokens[i] for i in stack)
    return pairs, errors


def _title(text: str, token: Token) -> str:
    return text[slice(*token.argument)].strip() if token.argument else ''


def _bib_ranges(text: str, tokens: list[Token], pairs: dict[int,int]) -> list[tuple[int,int]]:
    """Environment ranges plus unwrapped bibitems, bounded by the next heading."""
    ranges = []
    inside_until = -1
    boundaries = [i for i,t in enumerate(tokens) if (t.kind == 'command' and
        (t.name in _HEADINGS or t.name == 'appendix')) or (t.kind == 'end' and t.name == 'document')]
    for i,t in enumerate(tokens):
        if t.start < inside_until:
            continue
        if t.kind == 'begin' and t.name == 'thebibliography':
            end = tokens[pairs[i]].end if i in pairs else next(
                (tokens[j].start for j in boundaries if j > i), len(text))
            ranges.append((t.start,end)); inside_until=end
        elif t.kind == 'command' and t.name == 'bibitem':
            j = bisect_right(boundaries, i)
            end = tokens[boundaries[j]].start if j < len(boundaries) else len(text)
            ranges.append((t.start,end)); inside_until=end
    # References sometimes use unwrapped prose rather than bibitem. Keep that
    # evidence for extraction without letting it become body sentences.
    for k,i in enumerate(boundaries):
        t=tokens[i]
        if t.kind!='command' or t.name not in _HEADINGS or _title(text,t).casefold() not in _REF_TITLES:
            continue
        last=boundaries[k+1] if k+1<len(boundaries) else len(tokens)
        end=tokens[last].start if last<len(tokens) else len(text)
        if any(t.end<=a<end for a,b in ranges):
            continue
        active=any(x.kind not in ('comment','break') and
                   (x.kind!='text' or text[x.start:x.end].strip()) and
                   not (x.kind=='command' and x.name in _METADATA)
                   for x in tokens[i+1:last])
        if active:
            ranges.append((t.end,end))
    return sorted(ranges)


def extract_bibliography_blocks(gathered: GatherResult) -> list[BibliographyBlock]:
    """Keep active thebibliography/bibitem blocks verbatim, never an appendix.

    Literal/comment examples do not declare references. Missing external bib
    declarations stay in gathered.bib_paths for Nguyên; they are not fake blocks.
    """
    tokens = _tokens(gathered.latex)
    pairs,_ = _environment_pairs(tokens)
    source = _SourceIndex(gathered.source_map)
    return [BibliographyBlock(raw=gathered.latex[a:b], source_spans=source.ranges(a,b))
            for a,b in _bib_ranges(gathered.latex,tokens,pairs)]


class _Parser:
    def __init__(self, gathered: GatherResult):
        self.g = gathered
        self.text = gathered.latex
        self.declared = declarations(self.text)
        self.tokens = _tokens(self.text)
        self.starts = [t.start for t in self.tokens]
        self.pairs, self.env_errors = _environment_pairs(self.tokens)
        self.source = _SourceIndex(gathered.source_map)
        self.nodes: list[RawNode] = []
        self.children: dict[str,list[RawNode]] = defaultdict(list)
        self.diagnostics = list(gathered.version_input.diagnostics)
        self.diagnostics.extend(d for d in gathered.diagnostics if d not in self.diagnostics)
        self.bibs = _bib_ranges(self.text,self.tokens,self.pairs)
        self.bib_by_start = {a:b for a,b in self.bibs}
        # A References heading is omitted, but the next real heading/appendix
        # resumes the body. Unwrapped reference prose remains raw for review.
        boundaries = [i for i,t in enumerate(self.tokens) if
            (t.kind=='command' and (t.name in _HEADINGS or t.name=='appendix')) or
            (t.kind=='end' and t.name=='document')]
        self.reference_sections = {}
        for k,i in enumerate(boundaries):
            t = self.tokens[i]
            if t.kind=='command' and t.name in _HEADINGS and _title(self.text,t).casefold() in _REF_TITLES:
                end = self.tokens[boundaries[k+1]].start if k+1<len(boundaries) else len(self.text)
                self.reference_sections[t.start] = end
        self.mask = []
        for t in self.tokens:
            if t.kind in ('comment','group_delimiter','declaration') or (t.kind == 'command' and t.name in _METADATA):
                self.mask.append((t.start,t.end))
        self.mask_ends = [b for a,b in self.mask]
        self.reported = set()

    def report(self, token: Token, message: str, code: str = 'UNSUPPORTED_CONTENT', *, severity: str = 'error') -> None:
        key = token.start,message,code
        if key in self.reported:
            return
        self.reported.add(key)
        spans = self.source.ranges(token.start,token.end)
        self.diagnostics.append(Diagnostic(code=code,severity=severity,message=message,
            arxiv_id=self.g.version_input.arxiv_id,version=self.g.version_input.version,
            path=spans[0].path if spans else None,offset=spans[0].start if spans else None))

    def content(self, start: int, end: int) -> str:
        """Mask inactive material with spaces, keeping the original offset grid."""
        parts = []
        cursor = start
        i = bisect_right(self.mask_ends,start)
        while i < len(self.mask):
            a,b = self.mask[i]
            if a >= end:
                break
            a,b = max(start,a),min(end,b)
            parts.append(self.text[cursor:a])
            parts.append(''.join('\n' if c=='\n' else '\r' if c=='\r' else ' ' for c in self.text[a:b]))
            cursor=b; i+=1
        parts.append(self.text[cursor:end])
        return ''.join(parts)

    def add(self, kind: str, parent: str | None, start: int, end: int, *,
            content: str | None = None, level: int | None = None, subtype: str | None = None) -> RawNode:
        local = 'r' if parent is None else f'n{len(self.nodes):06d}'
        node = RawNode(local_id=local,parent_local_id=parent,kind=kind,
            content=self.content(start,end).strip() if content is None else content,
            position=len(self.children[parent]),source_spans=self.source.ranges(start,end),
            heading_level=level,subtype=subtype)
        self.nodes.append(node)
        self.children[parent].append(node)
        return node

    def prose(self, start: int, end: int, parent: str) -> None:
        text = self.content(start,end)
        a,b=0,len(text)
        while a < b and text[a].isspace(): a+=1
        while b > a and text[b-1].isspace(): b-=1
        if a == b:
            return
        paragraph = self.add('paragraph',parent,start+a,start+b,content=text[a:b])
        for x,y in _sentence_ranges(text[a:b]):
            self.add('sentence',paragraph.local_id,start+a+x,start+a+y,content=text[a+x:a+y])

    def body(self, lo: int, hi: int, parent: str, *, headings: bool = True) -> None:
        i = bisect_right(self.starts,lo-1)
        cursor = lo
        heading_stack: list[tuple[int,str]] = []
        def current():
            return heading_stack[-1][1] if heading_stack else parent
        while i < len(self.tokens) and self.tokens[i].start < hi:
            t=self.tokens[i]
            if t.start < cursor:
                i+=1; continue
            skip = self.bib_by_start.get(t.start)
            reference_end = self.reference_sections.get(t.start)
            if reference_end is not None:
                self.prose(cursor,t.start,current())
                cursor=min(reference_end,hi)
                i=bisect_right(self.starts,cursor-1)
                continue
            structural = skip is not None or t.kind in ('block','begin','end','break') or (
                t.kind=='command' and (t.name in _HEADINGS or t.name in ('par','appendix','item')))
            if t.malformed:
                self.report(t,'Unterminated '+(t.name or t.kind))
            if structural:
                self.prose(cursor,t.start,current())
                if skip is not None:
                    cursor=min(skip,hi)
                    i=bisect_right(self.starts,cursor-1); continue
                if t.kind=='command' and t.name in _HEADINGS:
                    title=_title(self.text,t)
                    if title.casefold() not in _REF_TITLES:
                        level=_HEADINGS[t.name]
                        while heading_stack and heading_stack[-1][0]>=level: heading_stack.pop()
                        h=self.add('heading',current(),t.start,t.end,content=title,level=level)
                        if not title:
                            self.report(t,'Heading has no readable title')
                        heading_stack.append((level,h.local_id))
                    cursor=t.end
                elif t.kind=='block':
                    self.add('block_formula',current(),t.start,t.end,content=self.text[t.start:t.end],subtype=t.name)
                    cursor=t.end
                elif t.kind=='begin':
                    close=self.pairs.get(i)
                    close_token=self.tokens[close] if close is not None else None
                    stop=min(close_token.end if close_token else hi,hi)
                    inner_end=min(close_token.start if close_token else hi,hi)
                    if t.name in MATH_ENVS or (t.name in _FLOATS and t.name not in self.declared.environments):
                        kind='block_formula' if t.name in MATH_ENVS and t.name!='math' else 'figure'
                        if t.name=='math':
                            self.prose(t.start,stop,current())
                        else:
                            subtype='table' if t.name.lower().startswith(('table','tabular','longtable','deluxetable','sidewaystable','wraptable')) else t.name
                            self.add(kind,current(),t.start,stop,content=self.text[t.start:stop],subtype=subtype)
                            if not self.text[t.start:t.end].startswith('\\begin'):
                                self.report(t,'Declared math alias parsed as '+t.name+'; raw delimiters need normalization')
                    elif t.name in _LISTS:
                        self.list_body(i,close,current(),stop)
                    elif t.name=='document':
                        self.body(t.end,inner_end,current())
                    else:
                        if t.name not in _TRANSPARENT and t.name not in self.declared.environments:
                            self.report(t,'Unsupported environment '+t.name+'; raw body retained')
                        self.body(t.end,inner_end,current(),headings=headings)
                    cursor=stop
                    i=bisect_right(self.starts,cursor-1); continue
                elif t.kind=='end':
                    self.report(t,'Unexpected environment end '+t.name)
                    cursor=t.end
                elif t.kind=='command' and t.name=='item':
                    self.report(t,'Item outside a list')
                    cursor=t.end
                elif t.kind=='command' and t.name=='appendix':
                    heading_stack.clear()
                    cursor=t.end
                else:
                    cursor=t.end
            elif t.kind=='command' and t.name not in _PROSE_COMMANDS and t.name not in _METADATA and len(t.name)>1:
                if self.declared.inline(t.name):
                    self.report(t,'Declared inline macro \\'+t.name+' retained with its raw arguments',
                                'MACRO_PRESERVED',severity='warning')
                else:
                    self.report(t,'Unexpanded command \\'+t.name+'; raw arguments retained')
            elif t.kind=='declaration':
                self.report(t,'Body-local macro definition retained in source; dynamic scope needs review')
            i+=1
        self.prose(cursor,hi,current())

    def list_body(self, begin: int, close: int | None, parent: str, stop: int) -> None:
        t=self.tokens[begin]
        last=close if close is not None else bisect_right(self.starts,stop-1)
        inner_end=self.tokens[close].start if close is not None else stop
        list_node=self.add('itemize',parent,t.start,stop,subtype=t.name)
        if t.name!='itemize':
            self.report(t,'List '+t.name+' preserved; current component_content_v1 normalizer only supports itemize')
        items=[]; i=begin+1
        while i < last:
            token=self.tokens[i]
            if token.kind=='command' and token.name=='item':
                items.append(i)
            if token.kind=='begin' and i in self.pairs:
                i=self.pairs[i]+1
            else:
                i+=1
        first=self.tokens[items[0]].start if items else inner_end
        prefix=self.content(t.end,first).strip()
        # List placement options are not prose. Any genuine pre-item text must survive.
        prefix=re.sub(r'^\[[^\]]*\]\s*','',prefix)
        if '[' in self.text[t.start:t.end]:
            self.report(t,'List options retained in raw content; normalizer support required')
        if prefix:
            self.report(t,'Text before first list item retained in a synthetic item')
            item=self.add('item',list_node.local_id,t.end,first,content=prefix)
            self.prose(t.end,first,item.local_id)
        for offset,idx in enumerate(items):
            it=self.tokens[idx]
            end=self.tokens[items[offset+1]].start if offset+1<len(items) else inner_end
            # Labels are semantic content; make them an explicit first sentence.
            a=it.argument[0] if it.argument else it.end
            content=self.content(a,end).strip()
            if it.argument:
                label=_title(self.text,it)
                content=label+' '+self.content(it.end,end).strip()
                self.report(it,'Explicit item label retained; component_content_v1 normalizer support required')
            if not content:
                self.report(it,'Empty list item omitted from semantic tree')
                continue
            item=self.add('item',list_node.local_id,a,end,content=content)
            if it.argument:
                label=_title(self.text,it)
                if label:
                    self.add('sentence',item.local_id,*it.argument,content=label)
            self.body(it.end,end,item.local_id,headings=False)
            if not self.children[item.local_id]:
                self.report(it,'Item contains only empty structural wrappers; omitted from semantic tree')
                self.nodes.remove(item)
                self.children[list_node.local_id].remove(item)
        if not self.children[list_node.local_id]:
            self.report(t,'Empty list has no semantic items')
            self.nodes.remove(list_node)
            self.children[parent].remove(list_node)

    def run(self) -> VersionTree:
        starts=[i for i,t in enumerate(self.tokens) if t.kind=='begin' and t.name=='document']
        if not starts:
            self.report(Token('text',0,len(self.text)),'No document environment in gathered source','PARSE_FATAL')
            return self.finish('failed',None)
        begin=starts[0]; token=self.tokens[begin]; close=self.pairs.get(begin)
        hi=self.tokens[close].start if close is not None else len(self.text)
        self.add('document',None,token.end,hi,content=f'Version {self.g.version_input.version} root')
        for t in self.env_errors:
            if token.start<=t.start<=hi:
                self.report(t,'Unbalanced environment '+t.name)
        self.body(token.end,hi,'r')
        status='partial' if self.g.status=='partial' or any(d.severity=='error' for d in self.diagnostics) else 'parsed'
        return self.finish(status,'r')

    def finish(self, status: str, root: str | None) -> VersionTree:
        v=self.g.version_input
        return VersionTree(arxiv_id=v.arxiv_id,version=v.version,root_local_id=root,nodes=self.nodes,
            bibliography_blocks=[BibliographyBlock(raw=self.text[a:b],source_spans=self.source.ranges(a,b)) for a,b in self.bibs],
            status=status,source_fingerprint=v.source_fingerprint,diagnostics=self.diagnostics)


def parse_version(gathered: GatherResult) -> VersionTree:
    """Build an ordered occurrence tree, preserving raw component content and spans.

    Production IDs are r/n000001/... in preorder. Inline math stays in sentences;
    display math and figures/tables are leaves. References are retained separately.
    parsed here is provisional: bibliography, normalization and final validation
    determine publication quality. The input and raw files are never modified.
    """
    v=gathered.version_input
    status = ('empty_no_tex' if v.source_status=='no_tex' else
              'blocked_input' if v.source_status=='blocked' else
              gathered.status if gathered.status in ('empty_no_tex','blocked_input','failed') else None)
    if status:
        diagnostics=list(v.diagnostics)
        diagnostics.extend(d for d in gathered.diagnostics if d not in diagnostics)
        return VersionTree(arxiv_id=v.arxiv_id,version=v.version,root_local_id=None,nodes=[],bibliography_blocks=[],
                           status=status,source_fingerprint=v.source_fingerprint,diagnostics=diagnostics)
    parser = _Parser(gathered)
    try:
        return parser.run()
    except RecursionError:
        # TeX can nest arbitrarily. Do not publish a truncated, seemingly valid
        # tree or crash the remaining publications at Python's recursion limit.
        parser.nodes.clear()
        parser.report(Token('text',0,len(gathered.latex)),
                      'Structural nesting exceeds the supported recursion depth','PARSE_FATAL')
        return parser.finish('failed',None)
