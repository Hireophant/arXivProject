"""Read-only working-schema validation and final quality status (Danh / DA2).

Validates occurrence trees independently of the projected graph, D3 content, citations,
counts and typed sidecars. Status follows plan 9.3; strict is a publication policy in pipeline.
Schema validation cannot certify semantic accuracy against an unseen raw source/PDF.
"""
from __future__ import annotations

import types
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import fields, is_dataclass
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Literal, Union, get_args, get_origin, get_type_hints

from .contracts import NODE_KINDS,RawNode
from .normalize import _citation_spans,rebuild_component_content
from .contracts import ParsedPublication, ValidationIssue


@lru_cache(maxsize=None)
def _hints(cls: type) -> dict:
    return get_type_hints(cls)


def _type_errors(value: object, expected: object, path: str = '') -> list[str]:
    """Validate dataclass runtime boundaries, including bool vs int and nested sidecars."""
    origin, args = get_origin(expected), get_args(expected)
    if origin in (Union, types.UnionType):
        return [] if any(not _type_errors(value,t,path) for t in args) else [path+' has wrong union type']
    if origin is Literal:
        return [] if any(type(value) is type(a) and value == a for a in args) else [path+' has unknown value']
    if origin in (list,dict,tuple):
        if type(value) is not origin: return [path+' has wrong container type']
        errors = []
        if origin is list:
            for i,item in enumerate(value): errors.extend(_type_errors(item,args[0],f'{path}[{i}]'))
        elif origin is dict:
            for key,item in value.items():
                errors.extend(_type_errors(key,args[0],path+'.key'))
                errors.extend(_type_errors(item,args[1],f'{path}[{key!r}]'))
        else:
            if len(value) != len(args): return [path+' has wrong tuple length']
            for item,kind in zip(value,args): errors.extend(_type_errors(item,kind,path))
        return errors
    if isinstance(expected,type) and is_dataclass(expected):
        if type(value) is not expected: return [path+' has wrong record type']
        errors = []
        if set(vars(value)) != {f.name for f in fields(expected)}: errors.append(path+' has extra/missing fields')
        for name,kind in _hints(expected).items():
            if hasattr(value,name): errors.extend(_type_errors(getattr(value,name),kind,path+'.'+name))
            else: errors.append(path+'.'+name+' missing')
        return errors
    return [] if type(value) is expected else [path+' has wrong scalar type']


_INTEGRITY = frozenset(('INVALID_SCHEMA','INVALID_STRUCTURE','ROOT_UNRESOLVED','PARSE_FATAL'))


def _unique_diagnostics(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    result = []
    for issue in issues:
        if issue not in result: result.append(issue)
    return result


def validate_publication(publication: ParsedPublication) -> list[ValidationIssue]:
    """API chỉ đọc: kiểm schema đúng cột/types/nullability, unique IDs/keys và foreign keys cùng publication.
    Kiểm root_ids/version_states phủ cùng tập; occurrence tree mỗi version có một root, parent hợp lệ,
    không cycle, position siblings unique; every node reachable và kind leaf đúng sentence/formula/figure.
    Không cấm projected hierarchy nhiều parent/self-edge/cycle nếu occurrence tree đúng sau dedup.
    Đối chiếu projection edges với occurrences/root; không đòi root có parent row.
    Cite sau normalize map được vào bibtex; key collision/entry chưa parse/missing bibliography phải là error.
    Kiểm normalized semantics/counts khi có evidence; không giả vờ đảm bảo accuracy chỉ bằng schema.
    Bổ sung diagnostics mới, không lặp lại toàn bộ errors sẵn có để counts nhân đôi.
    Không tự sửa row hỏng, không set parsed/export_ready ở hàm này.
    """
    issues = []
    paper = publication.arxiv_id
    def add(code: str, message: str, version: int | None = None) -> None:
        issue = ValidationIssue(code=code,severity='error',message=message,arxiv_id=paper,version=version)
        if issue not in publication.diagnostics and issue not in issues: issues.append(issue)
    type_errors = _type_errors(publication, ParsedPublication, 'publication')
    for message in type_errors: add('INVALID_SCHEMA',message)
    if type_errors: return issues
    versions = set(publication.version_states)
    if not paper or not versions or any(v < 1 for v in versions) or set(publication.root_ids) != versions:
        add('INVALID_STRUCTURE','Expected version/root coverage mismatch')
    tables = (publication.elements,publication.hierarchy,publication.bibtex,publication.occurrences,
              publication.bib_occurrences,publication.identity_decisions,publication.conflicts,publication.diagnostics)
    if any(row.arxiv_id != paper for table in tables for row in table): add('INVALID_SCHEMA','Cross-publication record')
    elements = {e.element_id:e for e in publication.elements}
    if len(elements) != len(publication.elements): add('INVALID_SCHEMA','Duplicate element IDs')
    for element in publication.elements:
        if not element.element_id or not element.content or element.kind not in NODE_KINDS:
            add('INVALID_SCHEMA','Invalid or empty element')
    bibkeys = {e.citation_key for e in publication.bibtex}
    if all(s == 'empty_no_tex' for s in publication.version_states.values()) and (publication.elements or publication.hierarchy or publication.bibtex or publication.bib_occurrences or publication.key_map):
        add('INVALID_SCHEMA','All-no_tex publication must have empty tables and citation occurrences')
    if len(bibkeys) != len(publication.bibtex) or '' in bibkeys: add('INVALID_SCHEMA','Duplicate/empty bibliography keys')
    for entry in publication.bibtex:
        if entry.year is not None and entry.year < 1: add('INVALID_SCHEMA','Invalid bibliography year')
        if any(not author.strip() for author in entry.authors): add('INVALID_SCHEMA','Empty author name')
    for (version,key),canonical in publication.key_map.items():
        if version not in versions or not key or canonical not in bibkeys:
            add('CITATION_UNRESOLVED',f'Invalid citation key map {key!r} -> {canonical!r}',version if version in versions else None)
    actual_edges = set()
    for row in publication.hierarchy:
        key = (row.version,row.element_id,row.parent_id)
        if key in actual_edges: add('INVALID_STRUCTURE','Duplicate projected edge',row.version)
        actual_edges.add(key)
        if row.version not in versions or row.element_id not in elements or row.parent_id not in elements:
            add('INVALID_STRUCTURE','Invalid projected foreign key',row.version if row.version in versions else None)
    by_version = defaultdict(list)
    for occurrence in publication.occurrences:
        if occurrence.version not in versions: add('INVALID_STRUCTURE','Unknown occurrence version')
        by_version[occurrence.version].append(occurrence)
        if occurrence.element_id not in elements: add('INVALID_STRUCTURE','Occurrence element missing',occurrence.version)
        if occurrence.position < 0: add('INVALID_STRUCTURE','Negative sibling position',occurrence.version)
        for span in occurrence.source_spans:
            path = PurePosixPath(span.path)
            if not span.path or path.is_absolute() or '..' in path.parts or '\\' in span.path or ':' in span.path or span.start < 0 or span.end < span.start:
                add('INVALID_STRUCTURE','Invalid source span',occurrence.version)
            if (span.flat_start is None) != (span.flat_end is None) or (span.flat_start is not None and (span.flat_start < 0 or span.flat_end < span.flat_start)):
                add('INVALID_STRUCTURE','Invalid flattened source span',occurrence.version)
    expected_edges, referenced = set(), set()
    for version,state in publication.version_states.items():
        occurrences = by_version[version]
        index = {o.local_id:o for o in occurrences}
        root = publication.root_ids.get(version)
        if len(index) != len(occurrences) or '' in index: add('INVALID_STRUCTURE','Duplicate/empty local ID',version)
        if state in ('empty_no_tex','blocked_input'):
            if occurrences or root is not None: add('INVALID_STRUCTURE','Empty/blocked version has body',version)
            continue
        if not occurrences and root is None:
            if state != 'failed': add('INVALID_STRUCTURE','No trustworthy body/root',version)
            continue
        roots = [o for o in occurrences if o.parent_local_id is None]
        if len(roots) != 1 or not roots or roots[0].element_id != root or root not in elements or elements[root].kind != 'document':
            add('INVALID_STRUCTURE','Occurrence root mismatch',version)
        elif roots[0].position != 0 or elements[root].content != f'Version {version} root':
            add('INVALID_STRUCTURE','Invalid root label/position',version)
        children, positions = defaultdict(list), set()
        for o in occurrences:
            referenced.add(o.element_id)
            sibling = (o.parent_local_id,o.position)
            if sibling in positions: add('INVALID_STRUCTURE','Duplicate sibling position',version)
            positions.add(sibling)
            if o.parent_local_id is not None:
                parent = index.get(o.parent_local_id)
                if parent is None: add('INVALID_STRUCTURE','Orphan occurrence',version)
                else:
                    children[parent.local_id].append(o)
                    expected_edges.add((version,o.element_id,parent.element_id))
            element = elements.get(o.element_id)
            if element:
                if element.kind == 'document' and (not roots or o is not roots[0]): add('INVALID_STRUCTURE','Non-root document',version)
                if element.kind == 'heading' and (o.heading_level is None or o.heading_level < 0): add('INVALID_STRUCTURE','Heading level missing',version)
                try:
                    for _,_,keys in _citation_spans(element.content):
                        for key in keys:
                            if key != '*' and key not in bibkeys: add('CITATION_UNRESOLVED',f'Citation {key!r} absent from unified bibliography',version)
                except ValueError as exc: add('CITATION_UNRESOLVED',str(exc),version)
        reached, stack = set(), [o.local_id for o in roots]
        while stack:
            local = stack.pop()
            if local in reached:
                add('INVALID_STRUCTURE','Occurrence cycle',version); continue
            reached.add(local)
            stack.extend(c.local_id for c in children[local])
        if reached != set(index): add('INVALID_STRUCTURE','Unreachable occurrence/cycle',version)
        for o in occurrences:
            element = elements.get(o.element_id)
            if not element: continue
            descendants = children[o.local_id]
            if not descendants and element.kind not in ('sentence','block_formula','figure'):
                add('INVALID_STRUCTURE','Container is a leaf without semantic children',version)
            if descendants and element.kind in ('sentence','block_formula','figure'):
                add('INVALID_STRUCTURE','Semantic leaf has children',version)
            if element.kind == 'itemize' and any(elements.get(c.element_id) and elements[c.element_id].kind != 'item' for c in descendants):
                add('INVALID_STRUCTURE','Itemize has non-item child',version)
        try:
            nodes = [RawNode(local_id=o.local_id,parent_local_id=o.parent_local_id,kind=elements[o.element_id].kind,
                     content=elements[o.element_id].content,position=o.position) for o in occurrences if o.element_id in elements]
            rebuilt = rebuild_component_content(nodes)
            if any(a.content != b.content for a,b in zip(nodes,rebuilt)):
                add('INVALID_STRUCTURE','D3 component content differs from ordered children',version)
        except ValueError as exc:
            add('INVALID_STRUCTURE','D3: '+str(exc),version)
    if expected_edges != actual_edges:
        affected = {v for v,_,_ in expected_edges ^ actual_edges}
        for version in affected: add('INVALID_STRUCTURE','Projection differs from occurrences',version)
    if referenced != set(elements): add('INVALID_STRUCTURE','Unused element rows')
    root_values = [r for r in publication.root_ids.values() if r is not None]
    if len(set(root_values)) != len(root_values): add('INVALID_STRUCTURE','Shared root across versions')
    before = Counter(elements[o.element_id].kind for o in publication.occurrences if o.element_id in elements)
    after = Counter(e.kind for e in publication.elements)
    before['bibtex'],after['bibtex'] = len(publication.bib_occurrences),len(publication.bibtex)
    counts = {c.kind:c for c in publication.counts_before_after}
    if len(counts) != len(publication.counts_before_after): add('INVALID_SCHEMA','Duplicate dedup count kind')
    for kind in set(counts) | set(before) | set(after):
        count = counts.get(kind)
        if (count is None and (before[kind] or after[kind])) or (count is not None and (count.before != before[kind] or count.after != after[kind] or kind not in (*NODE_KINDS,'bibtex'))):
            add('INVALID_SCHEMA',f'Count mismatch for {kind}')
    ids = set()
    bib_index = {o.occurrence_id:o for o in publication.bib_occurrences}
    for occurrence in publication.bib_occurrences:
        if not occurrence.occurrence_id or occurrence.occurrence_id in ids or occurrence.version not in versions or not occurrence.source_fingerprint:
            add('INVALID_SCHEMA','Invalid bibliography occurrence')
        ids.add(occurrence.occurrence_id)
        if publication.version_states.get(occurrence.version) in ('empty_no_tex','blocked_input'):
            add('INVALID_SCHEMA','Empty/blocked version contributed bibliography')
        if occurrence.entry is not None and (occurrence.entry.arxiv_id != paper or occurrence.original_key != occurrence.entry.citation_key):
            add('INVALID_SCHEMA','Bibliography raw entry identity mismatch')
        if occurrence.entry is None: add('BIB_ENTRY_UNPARSED','Unparsed bibliography occurrence '+occurrence.occurrence_id,occurrence.version)
    decision_ids = set()
    for decision in publication.identity_decisions:
        if not decision.decision_id or decision.decision_id in decision_ids: add('INVALID_SCHEMA','Duplicate/empty identity decision ID')
        decision_ids.add(decision.decision_id)
        if (not decision.occurrence_ids or len(set(decision.occurrence_ids)) != len(decision.occurrence_ids)
                or set(decision.source_fingerprints) != set(decision.occurrence_ids)
                or any(oid not in bib_index or decision.source_fingerprints.get(oid) != bib_index[oid].source_fingerprint for oid in decision.occurrence_ids)):
            add('INVALID_SCHEMA','Stale or unknown identity decision occurrences/fingerprints')
        if not decision.evidence.strip() or (decision.reviewer is not None and (not decision.reviewer.strip() or not decision.input_snapshot_id)):
            add('INVALID_SCHEMA','Identity decision requires provenance evidence')
        if decision.outcome == 'pending':
            affected = sorted({o.version for o in publication.bib_occurrences if o.occurrence_id in decision.occurrence_ids})
            for version in affected or [None]: add('REFERENCE_IDENTITY_REVIEW','Pending identity decision '+decision.decision_id,version)
    return issues


def finalize_publication(publication: ParsedPublication) -> ParsedPublication:
    """Trả COPY sau validate_publication, merge/dedup diagnostics và tính status cuối theo kế hoạch 9.3.
    Giữ empty_no_tex/blocked_input. Version có body tin cậy + lỗi include/bib/cite/identity -> partial;
    root/body/schema/occurrence integrity hỏng -> failed. Error không định vị version chặn cả publication có TeX.
    Field vốn thiếu hoặc field conflict đã giải có evidence -> warning; không hạ error để tăng success.
    export_ready=True chỉ khi mọi expected version parsed/empty_no_tex và không error publication/schema.
    All-no_tex hợp lệ có ba bảng rỗng và export_ready=True. Strict không ảnh hưởng status; pipeline chọn publish.
    Test S13 với cùng input strict True/False phải có cùng status.
    """
    result = deepcopy(publication)
    result.diagnostics = _unique_diagnostics(result.diagnostics + validate_publication(publication))
    for version,state in result.version_states.items():
        if state in ('empty_no_tex','blocked_input'): continue
        errors = [d for d in result.diagnostics if d.severity == 'error' and (
            d.version == version or version in d.affected_versions or (d.version is None and not d.affected_versions))]
        if state == 'failed' or any(d.code in _INTEGRITY for d in errors): result.version_states[version] = 'failed'
        elif errors or state == 'partial': result.version_states[version] = 'partial'
        else: result.version_states[version] = 'parsed'
    result.export_ready = bool(result.version_states) and all(s in ('parsed','empty_no_tex') for s in result.version_states.values()) and not any(d.severity == 'error' for d in result.diagnostics)
    return result

