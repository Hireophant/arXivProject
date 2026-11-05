"""Semantic cleanup, version-specific citations and D3 component content (Danh / DA1).

Uses a protected-context scanner and indexed iterative postorder; raw trees are never
mutated. Unsupported/uncovered content is retained with error diagnostics. C3 identity
belongs to reference_dedup; this module only consumes its version-specific key map.
"""
from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import replace
from typing import Iterator

from .contracts import Diagnostic
from .contracts import ParseConfig, RawNode, UnifiedBibliography, VersionTree
from .khang_lex import _layout_list_options, _argument_space, scan, FLOAT_ENVS
from .khang_macros import Declarations

_CITES = frozenset(('cite', 'citep', 'citet', 'citealt', 'citealp', 'citeauthor',
                    'citeyear', 'citeyearpar', 'Citep', 'Citet', 'Cite', 'nocite',
                    'autocite', 'parencite', 'textcite', 'footcite', 'smartcite'))
_WRAPPERS = frozenset(('textbf', 'textit', 'emph', 'textrm', 'textsf', 'texttt',
                       'textnormal', 'textup', 'textsl', 'underline', 'mbox'))
_COMMAND = re.compile(r'\\([A-Za-z@]+|[^A-Za-z])')
_BEGIN = re.compile(r'\\begin\{([^}]+)\}')
_END = re.compile(r'\\end\{([^}]+)\}')
_LIST_WRAPPER = re.compile(r'\\(?:begin|end)\{(?:itemize|description|enumerate)\}|\\item\b')
_MATH_ENVS = {'equation', 'equation*', 'displaymath', 'align', 'align*',
              'gather', 'gather*', 'eqnarray', 'eqnarray*', 'multline', 'multline*',
              'alignat', 'alignat*', 'flalign', 'flalign*'}


def _balanced(text: str, start: int, opener: str = '{', closer: str = '}') -> int:
    """Return exclusive end, respecting nested braces, escapes and comments."""
    if start >= len(text) or text[start] != opener:
        raise ValueError(f'Expected {opener} at {start}')
    depth, braces, i = 1, 0, start + 1
    while i < len(text):
        ch = text[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '%':
            end = text.find('\n', i)
            i = len(text) if end < 0 else end + 1
            continue
        if opener == '[':
            if ch == '{': braces += 1
            if ch == '}': braces -= 1
        if not braces:
            if ch == opener: depth += 1
            if ch == closer:
                depth -= 1
                if depth == 0: return i + 1
        i += 1
    raise ValueError(f'Unclosed {opener} at {start}')


def _skip_space(text: str, i: int) -> int:
    return _argument_space(text,i)


def _protected_end(text: str, i: int) -> int | None:
    """Comments, literal environments, verb, URL arguments (math is scanned separately)."""
    if text[i] == '%':
        end = text.find('\n', i)
        return len(text) if end < 0 else end + 1
    if text[i] != '\\': return None
    match = _COMMAND.match(text, i)
    if not match: return None
    name, end = match.group(1), match.end()
    if name == 'verb':
        if end < len(text) and text[end] == '*': end += 1
        if end >= len(text): raise ValueError('Unclosed verb')
        stop = text.find(text[end], end + 1)
        if stop < 0: raise ValueError('Unclosed verb')
        return stop + 1
    env = _BEGIN.match(text, i)
    if env and env.group(1) in ('verbatim', 'verbatim*', 'lstlisting', 'minted'):
        closing = '\\end{' + env.group(1) + '}'
        stop = text.find(closing, env.end())
        if stop < 0: raise ValueError('Unclosed literal environment')
        return stop + len(closing)
    if name in ('url', 'path', 'href'):
        start = _skip_space(text, end)
        if start < len(text) and text[start] == '{': return _balanced(text, start)
    return None


def _citation_spans(text: str) -> Iterator[tuple[int, int, list[str]]]:
    """Yield key-group ranges only; consumers share the same context-aware scanner."""
    i = 0
    while i < len(text):
        protected = _protected_end(text, i)
        if protected is not None:
            i = protected
            continue
        match = _COMMAND.match(text, i)
        if not match:
            i += 1
            continue
        name, i = match.group(1), match.end()
        if name not in _CITES: continue
        if i < len(text) and text[i] == '*': i += 1
        i = _skip_space(text, i)
        while i < len(text) and text[i] == '[':
            i = _skip_space(text, _balanced(text, i, '[', ']'))
        if i >= len(text) or text[i] != '{': raise ValueError('Citation missing key group')
        end = _balanced(text, i)
        keys = [key.strip() for key in text[i+1:end-1].split(',')]
        yield i, end, keys
        i = end


def _math_end(text: str, i: int, closing: str) -> int:
    cursor = i
    while cursor < len(text):
        if text.startswith(closing, cursor): return cursor
        if text[cursor] == '\\': cursor += 2
        elif text[cursor] == '%':
            end = text.find('\n', cursor)
            cursor = len(text) if end < 0 else end + 1
        else: cursor += 1
    raise ValueError('Unclosed math delimiter')


def _environment_end(text: str, start: int, name: str) -> int:
    depth,i = 1,start
    while i < len(text):
        end = _protected_end(text,i)
        if end is not None: i = end;continue
        begin = _BEGIN.match(text,i)
        closing = _END.match(text,i)
        if begin and begin.group(1) == name:
            depth += 1;i = begin.end();continue
        if closing and closing.group(1) == name:
            depth -= 1
            if depth == 0: return i
            i = closing.end();continue
        command = _COMMAND.match(text,i)
        i = command.end() if command else i+1
    raise ValueError('Unclosed math environment')


def _math_body(text: str) -> str:
    # TeX comments consume the newline; remove them before trimming so the
    # emitted closing delimiter cannot accidentally become part of a comment.
    parts,i = [],0
    while i < len(text):
        end = _protected_end(text,i)
        if end is not None:
            if text[i] != '%': parts.append(text[i:end])
            i = end;continue
        command = _COMMAND.match(text,i)
        if command: parts.append(command.group());i = command.end()
        else: parts.append(text[i]);i += 1
    return ''.join(parts).strip()


def _clean(text: str, *, table: bool = False, trim: bool = True) -> str:
    """Normalize prose fragments without rewriting whitespace inside protected fragments."""
    out: list[str] = []
    i = 0
    while i < len(text):
        end = _protected_end(text, i)
        if end is not None:
            if text[i] != '%': out.append(text[i:end])
            i = end
            continue
        if text[i].isspace():
            if not out or not out[-1].endswith(' '): out.append(' ')
            i += 1
            continue
        delimiter = next((x for x in ('$$', '\\[', '\\(', '$') if text.startswith(x, i)), None)
        if delimiter:
            closing = {'$$':'$$', '\\[':'\\]', '\\(':'\\)', '$':'$'}[delimiter]
            end = _math_end(text, i + len(delimiter), closing)
            body = _math_body(text[i+len(delimiter):end])
            out.append('$'+body+'$' if delimiter in ('$', '\\(') else '\\begin{equation}'+body+'\\end{equation}')
            i = end + len(closing)
            continue
        match = _COMMAND.match(text, i)
        if not match:
            out.append(text[i]); i += 1
            continue
        name = match.group(1)
        start = _skip_space(text, match.end())
        if name == 'item' and start < len(text) and text[start] == '[':
            end = _balanced(text,start,'[',']')
            out.append('\\item {'+_clean(text[start+1:end-1],table=table)+'} ')
            i = end
            continue
        if name in _WRAPPERS and start < len(text) and text[start] == '{':
            end = _balanced(text, start)
            fragment = _clean(text[start+1:end-1], table=table, trim=False)
            if out and out[-1].endswith(' '): fragment = fragment.lstrip(' ')
            if fragment: out.append(fragment)
            i = end
            continue
        if name == 'centering' or (table and name in ('midrule', 'toprule', 'bottomrule', 'hline')):
            i = match.end()
            if table and name != 'centering' and start < len(text) and text[start] == '[':
                i = _balanced(text,start,'[',']')
            continue
        env = _BEGIN.match(text, i)
        if env and env.group(1) in ('itemize','description','enumerate'):
            out.append(env.group());i=env.end()
            start=_skip_space(text,i)
            if start<len(text) and text[start]=='[':
                end=_balanced(text,start,'[',']')
                if _layout_list_options(text[start+1:end-1]): i=end
            continue
        if env and env.group(1) in _MATH_ENVS:
            name = env.group(1)
            closing = '\\end{' + name + '}'
            end = _environment_end(text,env.end(),name)
            body = _math_body(text[env.end():end])
            base = name.rstrip('*')
            inner = {'align':'aligned', 'eqnarray':'aligned', 'gather':'gathered', 'alignat':'alignedat', 'flalign':'aligned'}.get(base)
            if inner: body = '\\begin{'+inner+'}'+body+'\\end{'+inner+'}'
            # multline keeps its explicit rows in gathered form, never flattens to a single row.
            if base == 'multline': body = '\\begin{gathered}'+body+'\\end{gathered}'
            out.append('\\begin{equation}'+body+'\\end{equation}')
            i = end + len(closing)
            continue
        if env and env.group(1).rstrip('*') in ('figure', 'table'):
            out.append(env.group()); i = env.end()
            start = _skip_space(text, i)
            if start < len(text) and text[start] == '[': i = _balanced(text, start, '[', ']')
            continue
        out.append(match.group()); i = match.end()
    result = ''.join(out)
    return result.strip() if trim else result


def _content_tokens(text: str) -> list[tuple[str,str]]:
    # Comparison only. Ignore prose grouping/list wrappers, but preserve math and
    # literal bytes: x^{ab} must never compare equal to x^ab at the coverage gate.
    result,prose = [],[]
    i = 0
    def protected(fragment: str) -> None:
        if prose:
            normalized = ' '.join(''.join(prose).split())
            if normalized: result.append(('prose',normalized))
            prose.clear()
        result.append(('protected',fragment))
    while i < len(text):
        end = _protected_end(text,i)
        if end is not None:
            protected(text[i:end]);i = end;continue
        delimiter = next((d for d in ('$$','\\[','\\(','$') if text.startswith(d,i)),None)
        if delimiter:
            closing = {'$$':'$$','\\[':'\\]','\\(':'\\)','$':'$'}[delimiter]
            end = _math_end(text,i+len(delimiter),closing)+len(closing)
            protected(text[i:end]);i = end;continue
        env = _BEGIN.match(text,i)
        if env and env.group(1) in _MATH_ENVS | FLOAT_ENVS:
            closing = '\\end{'+env.group(1)+'}'
            end = _environment_end(text,env.end(),env.group(1))
            end += len(closing);protected(text[i:end]);i = end;continue
        wrapper = _LIST_WRAPPER.match(text,i)
        if wrapper:
            # List boundaries separate fragments even without source whitespace:
            # \end{itemize}After. must not compare as Inner.After.
            prose.append(' ')
            i = wrapper.end();continue
        match = _COMMAND.match(text,i)
        if match:
            prose.append(match.group());i = match.end();continue
        if text[i] not in '{}': prose.append(text[i])
        i += 1
    if prose:
        normalized = ' '.join(''.join(prose).split())
        if normalized: result.append(('prose',normalized))
    return result


def _unsupported_cites(text: str) -> list[str]:
    names,i = [],0
    while i < len(text):
        end = _protected_end(text,i)
        if end is not None: i = end;continue
        match = _COMMAND.match(text,i)
        if match:
            name = match.group(1)
            if 'cite' in name.lower() and name not in _CITES: names.append(name)
            i = match.end()
        else: i += 1
    return names


def rewrite_citations(text: str, *, version: int, bibliography: UnifiedBibliography) -> str:
    """Chỉ đổi keys trong citation commands được hỗ trợ bằng key_map theo version.
    Scan balanced braces và optional args; hỗ trợ cite/citep/citet cùng star/multi-key có test.
    Không thay key xuất hiện trong prose, URL, verbatim hoặc comment; giữ optional args và thứ tự keys.
    Không map được thì giữ nguyên key; normalize_tree phát CITATION_UNRESOLVED có vị trí.
    Không tự gộp entry; chỉ dùng UnifiedBibliography của Nguyên.
    """
    parts, cursor = [], 0
    for start, end, keys in _citation_spans(text):
        parts.extend((text[cursor:start], '{'+','.join(
            bibliography.key_map.get((version, key), key) for key in keys)+'}'))
        cursor = end
    parts.append(text[cursor:])
    return ''.join(parts)


def normalize_leaf(node: RawNode, *, version: int, bibliography: UnifiedBibliography, config: ParseConfig) -> RawNode:
    """Trả COPY không mutate node/source input. Rewrite cites rồi cleanup theo kind.
    Bỏ wrapper formatting nhưng giữ text; bỏ centering/placement/midrule đúng ngữ cảnh.
    Inline math -> $...$; block -> equation wrapper thống nhất, align giữ hàng và alignment semantics.
    Không dùng replace toàn văn làm hỏng math/escape/verbatim/table cells.
    Giữ source_spans/position/kind/heading_level/subtype. Heading cleanup title không ghép body.
    Cleanup idempotent; helper nhận raw node để rewrite một lần. Dùng normalize_tree khi gọi lặp:
    normalized_with phân biệt canonical keys với raw keys có thể trùng tên nhưng chỉ tài liệu khác.
    Không thể suy trạng thái raw/canonical chỉ từ một chuỗi không có provenance marker.
    """
    text = rewrite_citations(node.content, version=version, bibliography=bibliography)
    return replace(node, content=_clean(text, table=node.subtype == 'table' or '\\begin{tabular}' in text),
                   source_spans=deepcopy(node.source_spans))


def _expand_math_aliases(text: str, context: Declarations, depth: int = 0) -> str:
    """Expand only math aliases proved by gathered preamble declarations.

    Literal/URL/command argument tokens remain opaque. This is not general TeX
    expansion: unsafe/body-local definitions stay unsupported in hierarchy.
    """
    if depth >= 32: raise ValueError('Math alias expansion cycle/depth exceeded')
    parts=[];cursor=0
    for token in scan(text,arities=context.arities):
        if token.kind!='command' or token.name not in context.math_aliases: continue
        kind,environment=context.math_aliases[token.name]
        body=context.bodies.get(token.name)
        if body is None:
            # Exact delimited display macros: the opener/terminator are tokens,
            # not executable commands with arguments of their own.
            expanded='\\'+kind+'{'+environment+'}'
        else:
            if '##' in body: raise ValueError('Unsupported literal parameter in math alias')
            end=_COMMAND.match(text,token.start).end()
            arguments={}
            for number in range(1,context.arities.get(token.name,0)+1):
                start=_skip_space(text,end)
                end=_balanced(text,start)
                arguments[str(number)]=text[start+1:end-1]
            body=re.sub(r'#([1-9])',lambda match:arguments.get(match[1],match[0]),body)
            expanded=_expand_math_aliases(body,context,depth+1)+text[end:token.end]
        parts.extend((text[cursor:token.start],expanded));cursor=token.end
    parts.append(text[cursor:])
    return ''.join(parts)


def rebuild_component_content(nodes: list[RawNode]) -> list[RawNode]:
    """Bottom-up theo occurrence tree, không theo thứ tự list tùy ý; trả copies.
    D3: paragraph nối sentences bằng space, block/list bằng newline; item nối paragraphs bằng blank line;
    itemize wrapper chuẩn và mỗi item một dòng; heading chỉ title; document nhãn Version N root đã đặt.
    Order lấy position theo parent_local_id; list lồng giữ wrapper; không join mọi children bằng space.
    Không gộp container rỗng có body bị thiếu; cấu trúc không hợp lệ -> ValueError để normalize_tree diagnostic.
    Cây fixture có container raw content đầy đủ để kiểm không mất text ngoài child coverage.
    """
    copied = [replace(node, source_spans=deepcopy(node.source_spans)) for node in nodes]
    index = {n.local_id:n for n in copied}
    if len(index) != len(copied): raise ValueError('Duplicate local IDs')
    children: dict[str | None, list[RawNode]] = defaultdict(list)
    for node in copied:
        if node.parent_local_id is not None and node.parent_local_id not in index: raise ValueError('Orphan node')
        children[node.parent_local_id].append(node)
    if copied and len(children[None]) != 1: raise ValueError('Expected one occurrence root')
    for siblings in children.values():
        siblings.sort(key=lambda n:n.position)
        if len({n.position for n in siblings}) != len(siblings): raise ValueError('Duplicate sibling position')
    # Iterative postorder also detects disconnected cycles and handles deep lists.
    visited: set[str] = set()
    stack = [(children[None][0], False)] if copied else []
    while stack:
        node, exiting = stack.pop()
        if not exiting:
            if node.local_id in visited: raise ValueError('Cycle')
            visited.add(node.local_id)
            stack.append((node, True))
            stack.extend((child, False) for child in reversed(children.get(node.local_id, [])))
            continue
        fragments = children.get(node.local_id, [])
        if node.kind not in ('paragraph', 'item', 'itemize') or not fragments: continue
        if node.kind == 'itemize':
            if any(c.kind != 'item' for c in fragments): raise ValueError('Non-item in itemize')
            content = '\\begin{itemize}\n'+'\n'.join('\\item {'+c.content+'}' for c in fragments)+'\n\\end{itemize}'
        else:
            parts = []
            for offset, child in enumerate(fragments):
                if offset:
                    previous = fragments[offset-1]
                    separator = ' ' if previous.kind == child.kind == 'sentence' else '\n'
                    if node.kind == 'item' and previous.kind == child.kind == 'paragraph': separator = '\n\n'
                    parts.append(separator)
                parts.append(child.content)
            content = ''.join(parts)
        if node.content and node.content != content and _content_tokens(node.content) != _content_tokens(content):
            raise ValueError(f'Uncovered or inconsistent component body: {node.local_id}')
        node.content = content
    if len(visited) != len(copied): raise ValueError('Unreachable nodes or cycle')
    return copied


def normalize_tree(tree: VersionTree, bibliography: UnifiedBibliography, config: ParseConfig, *,
                   macro_context: Declarations | None = None) -> VersionTree:
    """API chính; không gọi hierarchy/bibliography. Nhận fixtures raw tree/unified bib.
    Kiểm arxiv_id, rewrite/cleanup leaves và headings, rebuild containers bottom-up.
    Giữ diagnostics gốc và bổ sung cite unresolved/unsupported; bibliography errors propagate theo affected_versions.
    Empty/blocked/failed vẫn giữ version và state; không sinh fake root.
    Set normalized_with=config.normalization_version, cây raw không bị mutate.
    Status chưa là kết luận cuối; validation.finalize_publication xử lý sau assemble.
    Test S4/S7/S11: hai sentences chỉ khác cite key sau rewrite phải có cùng normalized content.
    Optional macro_context comes from the same version's gathered preamble; it
    allows declared math aliases without guessing delimiters or changing wire schemas.
    """
    if tree.arxiv_id != bibliography.arxiv_id: raise ValueError('Publication identity mismatch')
    if tree.normalized_with is not None and tree.normalized_with != config.normalization_version:
        raise ValueError('Normalization revision changed; rebuild from the raw occurrence tree')
    # A canonical key can also be an unrelated old key in this version. The
    # existing tree provenance marker, rather than string heuristics, prevents
    # applying that raw-key rewrite to an already normalized tree a second time.
    rewrite_bibliography = replace(bibliography,key_map={}) if tree.normalized_with is not None else bibliography
    diagnostics = deepcopy(tree.diagnostics)
    for diagnostic in bibliography.diagnostics:
        if diagnostic.version == tree.version or tree.version in diagnostic.affected_versions or (
                diagnostic.version is None and not diagnostic.affected_versions):
            if diagnostic not in diagnostics: diagnostics.append(deepcopy(diagnostic))
    nodes = []
    canonical = {entry.citation_key for entry in bibliography.entries}
    for node in tree.nodes:
        def report(code: str, message: str) -> None:
            span = node.source_spans[0] if node.source_spans else None
            issue = Diagnostic(code=code, severity='error', message=message, arxiv_id=tree.arxiv_id,
                               version=tree.version, path=span.path if span else None, offset=span.start if span else None)
            if issue not in diagnostics: diagnostics.append(issue)
        try:
            if node.kind=='itemize' and node.subtype=='enumerate':
                report('UNSUPPORTED_CONTENT','Enumeration numbering/style requires review; ordered body and raw source spans retained')
            expanded = replace(node,content=_expand_math_aliases(node.content,macro_context)) if macro_context else node
            cleaned = normalize_leaf(expanded, version=tree.version, bibliography=rewrite_bibliography, config=config)
            if node.kind=='block_formula' and node.subtype in _MATH_ENVS and not cleaned.content.startswith('\\begin{equation}'):
                report('UNSUPPORTED_CONTENT','Math alias requires matching gathered declaration context')
            if node.kind == 'document': cleaned.content = f'Version {tree.version} root'
            for _, _, keys in _citation_spans(node.content):
                for key in keys:
                    if key == '*': continue
                    if (tree.version,key) not in rewrite_bibliography.key_map and key not in canonical:
                        report('CITATION_UNRESOLVED', f'Unresolved citation {key!r} in {node.local_id}')
            # Unsupported cite families are preserved and explicitly need review.
            if _unsupported_cites(node.content): report('UNSUPPORTED_CONTENT', 'Unsupported citation command')
            nodes.append(cleaned)
        except ValueError as exc:
            report('UNSUPPORTED_CONTENT', str(exc))
            nodes.append(deepcopy(node))
    try:
        nodes = rebuild_component_content(nodes)
    except ValueError as exc:
        issue = Diagnostic(code='INVALID_STRUCTURE', severity='error', message=str(exc), arxiv_id=tree.arxiv_id, version=tree.version)
        if issue not in diagnostics: diagnostics.append(issue)
    return replace(tree, nodes=nodes, bibliography_blocks=deepcopy(tree.bibliography_blocks),
                   diagnostics=diagnostics, normalized_with=config.normalization_version)

