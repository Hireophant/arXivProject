"""Exact publication-local element sharing and occurrence projection (Danh / DA2).

Dictionary identity is (kind, normalized content); roots remain version-specific.
Occurrences preserve multiplicity/order/spans even when projected edges collapse or cycle.
Primary hash collisions are compared by actual content and disambiguated deterministically.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from copy import deepcopy

from .contracts import DedupCount, ElementOccurrence, ElementRow, HierarchyRow, NODE_KINDS
from .contracts import ParsedPublication, UnifiedBibliography, VersionTree


def assemble_publication(trees: list[VersionTree], bibliography: UnifiedBibliography) -> ParsedPublication:
    """API chính, cần >=1 VersionTree cùng publication, version unique; giữ mọi expected version.
    Đòi normalized_with giống nhau và khác None cho trees có nodes; không dedup raw content.
    Sinh IDs publication prefix (dot/slash -> hyphen) + kind + SHA256 canonical JSON [kind,content].
    Root ID riêng '#root-vN'; root không dedup; hash collisions so nội dung thật và xử lý deterministic.
    Exact match theo (kind,content), không fuzzy/cross-paper. Giữ mọi occurrence/position/source spans.
    Projection hierarchy unique theo (arxiv_id,version,element_id,parent_id), không thêm position cột cuối.
    Các occurrences trùng edge giữ trong occurrences sidecar; shared element có thể có nhiều parents.
    Không ép projected graph thành occurrence tree (có thể self-edge/cycle sau dedup); validate tree gốc qua sidecar.
    Root mapping version->ID, empty/blocked root None. Counts before là occurrences, after distinct theo kind;
    bibtex before gồm mọi attempted BibOccurrence kể cả entry hỏng, ghi lỗi riêng; không gọi drop là dedup success.
    Tập hợp bib_occurrences, key_map, decisions/conflicts/diagnostics, export_ready=False cho đến finalize.
    Kiểm S7/S10/S11: cùng câu đổi parent, paragraph đổi body, item đảo thứ tự, repeated sentence trong một version.

    Quy tắc ID chính xác: prefix = arxiv_id.replace('.', '-').replace('/', '-');
    root prefix+'#root-vN'; node khác prefix+'#'+kind+'-'+SHA256(canonical JSON [kind,content]).
    Canonical JSON: ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':').
    Mẫu kiểm tay: v1/v2 câu không đổi chỉ một elements row, vẫn đủ edges/occurrences.
    Dùng make_normalized_tree/make_unified_bibliography trong tests/m2_support/fixtures.py
    để làm độc lập; fixtures IDs là expected minh họa, không ép production theo IDs fixture.
    """
    if not trees: raise ValueError('At least one expected version is required')
    paper = bibliography.arxiv_id
    if any(t.arxiv_id != paper for t in trees): raise ValueError('Mixed publications')
    if any(type(t.version) is not int or t.version < 1 for t in trees): raise ValueError('Invalid version')
    if len({t.version for t in trees}) != len(trees): raise ValueError('Duplicate version')
    revisions = {t.normalized_with for t in trees if t.nodes}
    if revisions and (None in revisions or len(revisions) != 1): raise ValueError('Normalize all body trees with the same revision')
    prefix = paper.replace('.', '-').replace('/', '-')
    trees = sorted(trees, key=lambda t:t.version)
    pairs = {(n.kind,n.content) for t in trees for n in t.nodes if n.local_id != t.root_local_id}
    buckets: dict[str, list[tuple[str,str]]] = defaultdict(list)
    for pair in sorted(pairs):
        payload = json.dumps(pair, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')).encode('utf-8')
        buckets[pair[0]+'-'+hashlib.sha256(payload).hexdigest()].append(pair)
    identities = {}
    for discriminant, bucket in buckets.items():
        for pair in bucket:
            suffix = ''
            if len(bucket) > 1:
                payload = json.dumps(pair, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                suffix = '-'+hashlib.sha512(payload).hexdigest()
            identities[pair] = prefix+'#'+discriminant+suffix
    elements = {eid:ElementRow(arxiv_id=paper,element_id=eid,kind=kind,content=content)
                for (kind,content),eid in identities.items()}
    if len(elements) != len(identities): raise ValueError('Secondary ID collision')
    occurrences, edges, roots, diagnostics = [], set(), {}, deepcopy(bibliography.diagnostics)
    for tree in trees:
        index = {n.local_id:n for n in tree.nodes}
        if len(index) != len(tree.nodes): raise ValueError('Duplicate occurrence ID')
        if tree.nodes and tree.root_local_id not in index: raise ValueError('Root not in nodes')
        local_map = {n.local_id:(prefix+f'#root-v{tree.version}' if n.local_id == tree.root_local_id else identities[n.kind,n.content]) for n in tree.nodes}
        roots[tree.version] = local_map.get(tree.root_local_id)
        children = defaultdict(list)
        for node in tree.nodes: children[node.parent_local_id].append(node)
        ordered, seen = [], set()
        stack = sorted(children[None],key=lambda n:(n.position,n.local_id),reverse=True)
        while stack:
            node = stack.pop()
            if node.local_id in seen: raise ValueError('Occurrence cycle')
            seen.add(node.local_id); ordered.append(node)
            stack.extend(sorted(children[node.local_id],key=lambda n:(n.position,n.local_id),reverse=True))
        if len(ordered) != len(tree.nodes): raise ValueError('Unreachable occurrence')
        for node in ordered:
            eid = local_map[node.local_id]
            if node.local_id == tree.root_local_id:
                if node.kind != 'document' or node.parent_local_id is not None: raise ValueError('Invalid root')
                elements[eid] = ElementRow(element_id=eid,arxiv_id=paper,kind='document',content=f'Version {tree.version} root')
            if node.parent_local_id is not None:
                if node.parent_local_id not in local_map: raise ValueError('Orphan occurrence')
                edges.add((tree.version,eid,local_map[node.parent_local_id]))
            occurrences.append(ElementOccurrence(arxiv_id=paper,version=tree.version,local_id=node.local_id,
                parent_local_id=node.parent_local_id,element_id=eid,position=node.position,
                source_spans=deepcopy(node.source_spans),heading_level=node.heading_level,subtype=node.subtype))
        for diagnostic in tree.diagnostics:
            if diagnostic not in diagnostics: diagnostics.append(deepcopy(diagnostic))
    before = Counter(n.kind for t in trees for n in t.nodes)
    after = Counter(e.kind for e in elements.values())
    counts = [DedupCount(kind=k,before=before[k],after=after[k]) for k in NODE_KINDS if before[k] or after[k]]
    if bibliography.occurrences or bibliography.entries:
        counts.append(DedupCount(kind='bibtex',before=len(bibliography.occurrences),after=len(bibliography.entries)))
    return ParsedPublication(arxiv_id=paper,elements=sorted(elements.values(),key=lambda e:e.element_id),
        hierarchy=[HierarchyRow(arxiv_id=paper,version=v,element_id=e,parent_id=p) for v,e,p in sorted(edges)],
        bibtex=deepcopy(bibliography.entries),version_states={t.version:t.status for t in trees},occurrences=occurrences,
        root_ids=roots,key_map=dict(bibliography.key_map),bib_occurrences=deepcopy(bibliography.occurrences),
        identity_decisions=deepcopy(bibliography.identity_decisions),conflicts=deepcopy(bibliography.conflicts),
        diagnostics=diagnostics,counts_before_after=counts,export_ready=False)

