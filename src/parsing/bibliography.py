"""Extract bibliography occurrences from declared files and bibitem blocks."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .contracts import BibliographyExtraction, BibEntry, BibOccurrence, Diagnostic, GatherResult, SourceSpan, VersionTree


def _group(text: str, start: int) -> tuple[str, int]:
    close = {"{": "}", "(": ")", "[": "]"}[text[start]]
    depth, braces, quoted = 1, 0, False
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == '"' and text[start] != "{":
            quoted = not quoted
        elif not quoted:
            if char == "{":
                braces += 1
                if text[start] == "{": depth += 1
            elif char == "}" and braces:
                braces -= 1
                if text[start] == "{": depth -= 1
            elif text[start] != "{" and braces == 0 and char == text[start]:
                depth += 1
            elif char == close and braces == 0:
                depth -= 1
            if depth == 0:
                return text[start + 1:index], index + 1
        index += 1
    raise ValueError("Unclosed group")


def _split(text: str) -> list[str]:
    result, start, depth, quoted = [], 0, 0, False
    for index, char in enumerate(text):
        if char == '"' and depth == 0 and (not index or text[index - 1] != "\\"):
            quoted = not quoted
        if not quoted:
            if char == "{": depth += 1
            if char == "}": depth -= 1
            if char == "," and depth == 0:
                result.append(text[start:index].strip())
                start = index + 1
    return result + [text[start:].strip()]


def _value(text: str, macros: dict[str, str]) -> str:
    parts, start, depth, quoted = [], 0, 0, False
    for index, char in enumerate(text):
        if char == '"' and depth == 0 and (not index or text[index - 1] != "\\"):
            quoted = not quoted
        elif not quoted:
            if char == "{": depth += 1
            elif char == "}": depth -= 1
            elif char == "#" and depth == 0:
                parts.append(text[start:index])
                start = index + 1
    parts.append(text[start:])
    values = []
    for part in parts:
        part = part.strip()
        if len(part) >= 2 and part[0] + part[-1] in ('{}', '""'):
            values.append(part[1:-1])
        else:
            values.append(macros.get(part.casefold(), part))
    return "".join(values).strip()


def _authors(text: str) -> tuple[list[str], bool]:
    names, start, scanned, depth = [], 0, 0, 0
    for match in re.finditer(r"\s+and\s+", text, re.I):
        depth += text[scanned:match.start()].count("{") - text[scanned:match.start()].count("}")
        scanned = match.end()
        if depth == 0:
            names.append(text[start:match.start()].strip().strip("{}"))
            start = match.end()
    names.append(text[start:].strip().strip("{}"))
    names = [name for name in names if name]
    complete = bool(names) and all(not re.search(r"\b(?:et\s+al\.?|others)\b|(?:^|[\s~])[A-Z]\.(?:[\s~]|$)", n, re.I) for n in names)
    return names, complete


def _occ(arxiv_id: str, version: int, raw: str, key: str | None, entry: BibEntry | None,
         spans: list[SourceSpan], fingerprint: str, complete: bool, issues: list[Diagnostic]) -> BibOccurrence:
    payload = dict(arxiv_id=arxiv_id, version=version, source_fingerprint=fingerprint,
                   source_spans=[dict(path=s.path, start=s.start, end=s.end) for s in spans],
                   raw_sha256=hashlib.sha256(raw.encode()).hexdigest())
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    prefix = arxiv_id.replace(".", "-").replace("/", "-")
    return BibOccurrence(occurrence_id=f"{prefix}#bib-v{version}-{digest}",
                         arxiv_id=arxiv_id, version=version, raw=raw, original_key=key,
                         entry=entry, source_spans=spans, source_fingerprint=fingerprint,
                         authors_complete=complete, diagnostics=issues)


def _issue(arxiv_id: str, version: int, message: str, path: str | None = None, offset: int | None = None) -> Diagnostic:
    return Diagnostic(code="BIB_ENTRY_UNPARSED", severity="error", message=message, arxiv_id=arxiv_id,
                      version=version, path=path, offset=offset, affected_versions=[version])


def parse_bibtex(text: str, *, arxiv_id: str, version: int, path: str, source_fingerprint: str) -> BibliographyExtraction:
    """Parse declared BibTeX text while retaining raw occurrences and source offsets."""
    result = BibliographyExtraction(arxiv_id=arxiv_id, version=version, occurrences=[])
    macros: dict[str, str] = {}
    crossrefs: dict[str, str] = {}
    cursor = 0
    for match in re.finditer(r"@([A-Za-z]+)\s*[{(]", text):
        if match.start() < cursor: continue
        start, kind = match.start(), match.group(1).lower()
        try:
            body, cursor = _group(text, match.end() - 1)
            raw = text[start:cursor]
            if kind in {"comment", "preamble"}: continue
            if kind == "string":
                name, value = body.split("=", 1)
                macros[name.strip().casefold()] = _value(value, macros)
                continue
            parts = _split(body)
            key = parts[0].strip()
            if not key: raise ValueError("Empty citation key")
            fields = {}
            for part in parts[1:]:
                if not part: continue
                name, value = part.split("=", 1)
                fields[name.strip().casefold()] = _value(value, macros)
            if fields.get("crossref"):
                crossrefs[key] = fields["crossref"]
            authors, complete = _authors(fields.get("author", ""))
            year_text = fields.get("year", "")
            entry = BibEntry(arxiv_id=arxiv_id, citation_key=key, entry_type=kind,
                             title=fields.get("title") or None, authors=authors,
                             year=int(year_text) if re.fullmatch(r"\d{4}", year_text) else None,
                             doi=fields.get("doi") or None, journal=fields.get("journal") or None,
                             url=fields.get("url") or None)
            issues = []
        except (ValueError, KeyError) as exc:
            cursor = text.find("@", match.end())
            if cursor < 0: cursor = len(text)
            raw, key, entry, complete = text[start:cursor], None, None, False
            issues = [_issue(arxiv_id, version, str(exc), path, start)]
            result.diagnostics.extend(issues)
        result.occurrences.append(_occ(arxiv_id, version, raw, key, entry,
                                       [SourceSpan(path=path, start=start, end=cursor)],
                                       source_fingerprint, complete, issues))
    by_key = {o.original_key: o for o in result.occurrences if o.original_key and o.entry}
    for child_key, parent_key in crossrefs.items():
        child, parent_occ = by_key.get(child_key), by_key.get(parent_key)
        if child and parent_occ and child.entry.year is None:
            child.entry.year = parent_occ.entry.year
    return result


def parse_bibitems(raw: str, *, arxiv_id: str, version: int, source_spans: list[SourceSpan],
                   source_fingerprint: str) -> BibliographyExtraction:
    """Extract citation items from one bibliography block without adding prose nodes."""
    result = BibliographyExtraction(arxiv_id=arxiv_id, version=version, occurrences=[])
    matches = list(re.finditer(r"\\bibitem\b", raw))
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        fragment = raw[start:end]
        try:
            pos = len(r"\bibitem")
            while pos < len(fragment) and fragment[pos].isspace(): pos += 1
            if fragment[pos] == "[": _, pos = _group(fragment, pos)
            while pos < len(fragment) and fragment[pos].isspace(): pos += 1
            key, pos = _group(fragment, pos)
            key = key.strip()
            if not key: raise ValueError("Empty bibitem key")
            body = fragment[pos:].strip()
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            year = re.search(r"\b(?:19|20)\d{2}\b", body)
            doi = re.search(r"(?:doi:|doi\.org/)(10\.\S+)", body, re.I)
            quoted_title = re.search(r"``([^\n]+?)''|[“\"]([^”\"]+)[”\"]", body)
            line_title = None
            if len(lines) >= 2 and lines[0].endswith((",", ":")):
                candidate = lines[1].strip(" ,.;")
                if candidate and (lines[0].endswith(":") or
                                  (lines[1].endswith(",") and len(lines) >= 3)):
                    line_title = candidate
            formatted = re.search(r"\\(?:textit|emph)\s*{([^{}]+)}|{\\it\s+([^{}]+)}", body)
            if line_title and formatted and line_title.startswith(("\\", "{")):
                line_title = formatted.group(1) or formatted.group(2)
            elif not line_title and formatted and formatted.start() < (year.start() if year else len(body)):
                # A formatted phrase immediately after the author is evidence for a title.
                prefix = body[:formatted.start()].strip()
                if prefix.endswith((",", ":")) and "\n" not in prefix:
                    line_title = formatted.group(1) or formatted.group(2)
            title = (quoted_title.group(1) or quoted_title.group(2)) if quoted_title else line_title
            author_text = (lines[0].strip(" ,.;:") if line_title else
                           body[:quoted_title.start()].strip(" ,.;") if quoted_title else "")
            if line_title:
                names = re.split(r",\s*(?:and\s+)?|\s+and\s+", author_text)
                authors = [name.strip() for name in names if name.strip()]
                complete = False
            else:
                authors, complete = _authors(author_text) if author_text else ([], False)
            if authors and any(len(name.replace("~", " ").split()) < 2 for name in authors):
                authors, complete = [], False
            journal_match = re.search(r"\\(?:emph|textit)\s*{([^{}]+)}", body)
            volume_journal = (re.search(r"^(.+?)\s+\d+\s*\(\d{4}\)", lines[2])
                              if line_title and len(lines) >= 3 else None)
            entry = BibEntry(arxiv_id=arxiv_id, citation_key=key,
                             title=title,
                             authors=authors,
                             year=int(year.group()) if year else None,
                             doi=doi.group(1).rstrip(".,") if doi else None,
                             journal=(journal_match.group(1) if journal_match and line_title and
                                      journal_match.group(1) != title else
                                      volume_journal.group(1).rstrip("\\").replace(r"\ ", " ").strip(" ,.;") if volume_journal else None))
            issues = []
        except (ValueError, IndexError, KeyError) as exc:
            key, entry, complete = None, None, False
            issues = [_issue(arxiv_id, version, str(exc))]
            result.diagnostics.extend(issues)
        spans = []
        flat_base = min((s.flat_start for s in source_spans if s.flat_start is not None), default=None)
        block_offset = 0
        for source in source_spans:
            if flat_base is not None and source.flat_start is not None and source.flat_end is not None:
                block_offset = source.flat_start - flat_base
                length = source.flat_end - source.flat_start
            else:
                length = source.end - source.start
            overlap_start, overlap_end = max(start, block_offset), min(end, block_offset + length)
            if overlap_start < overlap_end:
                spans.append(SourceSpan(path=source.path, start=source.start + overlap_start - block_offset,
                                        end=source.start + overlap_end - block_offset))
            block_offset += length
        result.occurrences.append(_occ(arxiv_id, version, fragment, key, entry, spans,
                                       source_fingerprint, complete, issues))
    return result


def extract_entries(gathered: GatherResult, tree: VersionTree) -> BibliographyExtraction:
    """Read only declared bibliography sources for the given version."""
    version = gathered.version_input
    if (version.arxiv_id, version.version) != (tree.arxiv_id, tree.version):
        raise ValueError("Gather/tree mismatch")
    result = BibliographyExtraction(arxiv_id=version.arxiv_id, version=version.version, occurrences=[],
                                    diagnostics=[*gathered.diagnostics, *tree.diagnostics])
    if gathered.status in {"failed", "empty_no_tex", "blocked_input"}: return result
    missing, seen = False, set()
    for location in gathered.bib_paths:
        if location.kind != "bib":
            missing |= not location.exists
            continue
        if location.path in seen: continue
        seen.add(location.path)
        root, relative = version.source_dir, Path(location.path)
        if root is None or relative.is_absolute() or ".." in relative.parts:
            missing = True
            continue
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            missing = True
            continue
        data = target.read_bytes()
        try: content = data.decode("utf-8-sig")
        except UnicodeDecodeError: content = data.decode("latin-1")
        parsed = parse_bibtex(content, arxiv_id=version.arxiv_id, version=version.version,
                              path=location.path, source_fingerprint=version.source_fingerprint or "")
        result.occurrences.extend(parsed.occurrences)
        result.diagnostics.extend(parsed.diagnostics)
    for block in tree.bibliography_blocks:
        parsed = parse_bibitems(block.raw, arxiv_id=version.arxiv_id, version=version.version,
                                source_spans=block.source_spans,
                                source_fingerprint=version.source_fingerprint or "")
        result.occurrences.extend(parsed.occurrences)
        result.diagnostics.extend(parsed.diagnostics)
    if missing and not result.occurrences:
        result.diagnostics.append(Diagnostic(code="BIBLIOGRAPHY_MISSING", severity="error",
                                             message="Declared bibliography file missing", arxiv_id=version.arxiv_id,
                                             version=version.version, affected_versions=[version.version]))
    return result
