"""Protected, deterministic sentence splitting (Khang / KG2).

A trailing prose unit needs no final punctuation. Internal bytes/whitespace are
never rewritten; only whitespace at the ends of returned units is trimmed.
English scientific abbreviations are heuristic; no language model or network.
"""
from __future__ import annotations

import re
from collections.abc import Iterator

from .khang_lex import MATH_ENVS, scan

_ABBREVIATION = re.compile(
    r"(?<![\w])(?:(?i:i\.e\.|e\.g\.|et\s+al\.|(?:Fig|Figs|Eq|Eqs|Sec|Secs|"
    r"Ref|Refs|Dr|Prof|Mr|Mrs|Ms|vs|cf|etc|Vol|No|pp)\.)|(?:[A-Z]\.){2,})")
_URL = re.compile(r"(?:https?://|www\.|doi:|10\.\d{4,9}/)[^\s<>]+", re.IGNORECASE)
_CLOSERS = '\"\'”’»)]}'


def _sentence_ranges(text: str) -> Iterator[tuple[int, int]]:
    """Offsets into text, using a forward cursor even for repeated sentences."""
    protected_dots = set()
    for pattern in (_ABBREVIATION, _URL):
        for match in pattern.finditer(text):
            stop = match.end()
            if pattern is _URL:
                while stop > match.start() and text[stop-1] in '.,!?;:)\"\'':
                    stop -= 1
            protected_dots.update(i for i in range(match.start(), stop) if text[i] in '.!?')
    start = 0
    math_depth = 0
    for token in scan(text):
        if token.kind == 'begin' and token.name in MATH_ENVS:
            math_depth += 1
        elif token.kind == 'end' and token.name in MATH_ENVS:
            math_depth = max(0, math_depth-1)
        if math_depth:
            continue
        if token.kind not in ('text', 'break'):
            continue
        for i in range(token.start, token.end):
            if text[i] not in '.!?' or i in protected_dots:
                continue
            if text[i] == '.' and i and i+1 < len(text) and text[i-1].isdigit() and text[i+1].isdigit():
                continue
            end = i+1
            while end < len(text) and (text[end] in _CLOSERS or text[end] in '.!?'):
                end += 1
            if end < len(text) and not text[end].isspace():
                continue
            a = start
            while a < end and text[a].isspace():
                a += 1
            if a < end:
                yield a, end
            start = end
    end = len(text)
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end-1].isspace():
        end -= 1
    if start < end:
        yield start, end


def split_sentences(text: str) -> list[str]:
    """Keep math, commands, groups, literals, URLs and abbreviations intact.

    Unterminated protected regions remain whole; hierarchy diagnoses these with
    source locations. Whitespace-only input yields []. A final unpunctuated unit
    is retained as a sentence. Comments are preserved by this raw-text API;
    hierarchy masks inactive comments before invoking the splitter.
    """
    return [text[a:b] for a,b in _sentence_ranges(text)]
