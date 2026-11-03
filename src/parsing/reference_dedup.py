"""Publication-local bibliography identity, field union and citation key mapping."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import fields
from itertools import combinations

from .contracts import BibliographyExtraction, BibEntry, BibOccurrence, Diagnostic, FieldConflict, IdentityDecision, UnifiedBibliography


def _hash(value: object) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def _plain(value: str | None) -> str:
    value = re.sub(r"\\(?:textbf|textit|emph|mathrm|mbox)\s*{", "{", value or "")
    value = value.replace("{", "").replace("}", "").replace("~", " ").replace("\\ ", " ")
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _doi(value: str | None) -> str:
    return re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", (value or "").strip(), flags=re.I).casefold()


def _identity(occ: BibOccurrence) -> tuple[str, tuple[str, tuple[str, ...], int | None]]:
    entry = occ.entry
    assert entry is not None
    return _doi(entry.doi), (_plain(entry.title), tuple(_plain(a) for a in entry.authors), entry.year)


def _decision(arxiv_id: str, pair: list[BibOccurrence], outcome: str, rule: str, evidence: str,
              review: IdentityDecision | None = None) -> IdentityDecision:
    ids = sorted(o.occurrence_id for o in pair)
    return IdentityDecision(decision_id=_hash([arxiv_id, ids, outcome, rule]), arxiv_id=arxiv_id,
                            occurrence_ids=ids, source_fingerprints={o.occurrence_id: o.source_fingerprint for o in pair},
                            outcome=outcome, rule=rule, evidence=evidence,
                            reviewer=review.reviewer if review else None,
                            input_snapshot_id=review.input_snapshot_id if review else None,
                            code_revision=review.code_revision if review else "identity_v1")


def unify_entries(arxiv_id: str, extractions: list[BibliographyExtraction], *,
                  review_decisions: list[IdentityDecision] | None = None) -> UnifiedBibliography:
    """Unify one publication's entries and return version-specific citation key mappings."""
    if any(e.arxiv_id != arxiv_id for e in extractions):
        raise ValueError("Extraction publication mismatch")
    occurrences = sorted((o for e in extractions for o in e.occurrences), key=lambda o: o.occurrence_id)
    if any(o.arxiv_id != arxiv_id for o in occurrences):
        raise ValueError("Occurrence publication mismatch")
    if len({o.occurrence_id for o in occurrences}) != len(occurrences):
        raise ValueError("Duplicate occurrence IDs")
    diagnostics = [d for e in extractions for d in e.diagnostics]
    good = [o for o in occurrences if o.entry is not None]
    by_id = {o.occurrence_id: o for o in good}
    reviews: dict[frozenset[str], IdentityDecision] = {}
    for review in review_decisions or []:
        key = frozenset(review.occurrence_ids)
        if review.arxiv_id != arxiv_id or len(key) < 2 or any(i not in by_id for i in key):
            continue
        if not review.reviewer or not review.evidence or not review.input_snapshot_id:
            continue
        if any(review.source_fingerprints.get(i) != by_id[i].source_fingerprint for i in key):
            continue
        if review.outcome in {"merge", "keep_separate"}:
            for pair in combinations(sorted(key), 2):
                reviews[frozenset(pair)] = review
    parent = {o.occurrence_id: o.occurrence_id for o in good}
    members = {o.occurrence_id: {o.occurrence_id} for o in good}
    keep_pairs = {pair for pair, review in reviews.items() if review.outcome == "keep_separate"}

    def root(identifier: str) -> str:
        while parent[identifier] != identifier:
            identifier = parent[identifier]
        return identifier

    def join(a: str, b: str) -> bool:
        ra, rb = root(a), root(b)
        if ra == rb: return True
        if any(frozenset((left, right)) in keep_pairs for left in members[ra] for right in members[rb]):
            return False
        if rb < ra: ra, rb = rb, ra
        parent[rb] = ra
        members[ra] |= members.pop(rb)
        return True

    # DOI groups are authoritative. A DOI-less entry may join only one DOI cluster.
    doi_groups: dict[str, list[BibOccurrence]] = defaultdict(list)
    for occ in good:
        doi = _identity(occ)[0]
        if doi: doi_groups[doi].append(occ)
    decisions: list[IdentityDecision] = []
    for group in doi_groups.values():
        for occ in group[1:]:
            pair = [group[0], occ]
            if join(group[0].occurrence_id, occ.occurrence_id):
                decisions.append(_decision(arxiv_id, pair, "merge", "identity_v1.doi", "Same normalized DOI"))
            else:
                review = reviews.get(frozenset(o.occurrence_id for o in pair))
                if review:
                    decisions.append(_decision(arxiv_id, pair, "keep_separate", "review", review.evidence, review))

    signatures: dict[tuple[str, tuple[str, ...], int], list[BibOccurrence]] = defaultdict(list)
    for occ in good:
        _, (title, authors, year) = _identity(occ)
        if title and authors and year is not None and occ.authors_complete:
            signatures[(title, authors, year)].append(occ)
    pending_pairs: set[tuple[str, str]] = set()
    for group in signatures.values():
        dois = {_identity(o)[0] for o in group if _identity(o)[0]}
        if len(dois) > 1:
            for occ in group:
                if not _identity(occ)[0]:
                    for other in group:
                        if _identity(other)[0]:
                            pending_pairs.add(tuple(sorted((occ.occurrence_id, other.occurrence_id))))
            continue
        anchor = group[0]
        for occ in group[1:]:
            pair = [anchor, occ]
            review = reviews.get(frozenset(o.occurrence_id for o in pair))
            if review and review.outcome == "keep_separate":
                decisions.append(_decision(arxiv_id, pair, "keep_separate", "review", review.evidence, review))
                continue
            if join(anchor.occurrence_id, occ.occurrence_id):
                decisions.append(_decision(arxiv_id, pair, "merge", "identity_v1.full_authors_title_year",
                                           "Same normalized title, complete ordered authors and year"))

    reviewed_dois: dict[str, set[str]] = defaultdict(set)
    for pair, review in reviews.items():
        if review.outcome != "merge" or len(review.occurrence_ids) != 2:
            continue
        for identifier in pair:
            if not _identity(by_id[identifier])[0]:
                reviewed_dois[identifier].update(_identity(by_id[other])[0] for other in pair - {identifier}
                                                 if _identity(by_id[other])[0])
    contradictory_reviews = {identifier for identifier, dois in reviewed_dois.items() if len(dois) > 1}
    for pair, review in sorted(reviews.items(), key=lambda item: sorted(item[0])):
        left, right = (by_id[i] for i in sorted(pair))
        if review.outcome == "keep_separate":
            decisions.append(_decision(arxiv_id, [left, right], review.outcome, "review", review.evidence, review))
            continue
        if pair & contradictory_reviews:
            pending_pairs.add(tuple(sorted(pair)))
            continue
        combined = members[root(left.occurrence_id)] | members[root(right.occurrence_id)]
        dois = {_identity(by_id[i])[0] for i in combined if _identity(by_id[i])[0]}
        if len(dois) > 1 and not combined.issubset(set(review.occurrence_ids)):
            pending_pairs.add(tuple(sorted(pair)))
            continue
        if join(left.occurrence_id, right.occurrence_id):
            decisions.append(_decision(arxiv_id, [left, right], review.outcome, "review", review.evidence, review))

    # Missing year or incomplete authors can be reviewed, but never merged by key alone.
    title_groups: dict[str, list[BibOccurrence]] = defaultdict(list)
    for occ in good:
        title = _identity(occ)[1][0]
        if title: title_groups[title].append(occ)
    for group in title_groups.values():
        for index, left in enumerate(group):
            for right in group[index + 1:]:
                if root(left.occurrence_id) == root(right.occurrence_id): continue
                ld, (lt, la, ly) = _identity(left)
                rd, (rt, ra, ry) = _identity(right)
                if ld and rd and ld != rd: continue
                if la and ra and la != ra and left.authors_complete and right.authors_complete: continue
                if ly is not None and ry is not None and ly != ry: continue
                if (la and ra and la == ra) or not left.authors_complete or not right.authors_complete:
                    pending_pairs.add(tuple(sorted((left.occurrence_id, right.occurrence_id))))

    for ids in sorted(pending_pairs):
        left, right = (by_id[i] for i in ids)
        if root(ids[0]) == root(ids[1]): continue
        review = reviews.get(frozenset(ids))
        if review:
            if review.outcome == "keep_separate":
                continue
        decisions.append(_decision(arxiv_id, [left, right], "pending", "identity_v1.ambiguous",
                                   "Same title with incomplete identity evidence or DOI bridge"))
        diagnostics.append(Diagnostic(code="REFERENCE_IDENTITY_REVIEW", severity="error",
                                      message=f"Review identity: {ids[0]} / {ids[1]}", arxiv_id=arxiv_id,
                                      affected_versions=sorted({left.version, right.version})))

    clusters: dict[str, list[BibOccurrence]] = defaultdict(list)
    for occ in good: clusters[root(occ.occurrence_id)].append(occ)
    entries: list[BibEntry] = []
    conflicts: list[FieldConflict] = []
    canonical: dict[str, str] = {}
    used: set[str] = set()
    for cluster in sorted(clusters.values(), key=lambda c: min(o.occurrence_id for o in c)):
        cluster.sort(key=lambda o: o.occurrence_id)
        key = min(o.original_key for o in cluster if o.original_key)
        if key in used:
            key += "__" + _hash([arxiv_id, sorted(o.occurrence_id for o in cluster)])
        used.add(key)
        for occ in cluster: canonical[occ.occurrence_id] = key
        selected = {}
        for field in fields(BibEntry):
            name = field.name
            if name in {"arxiv_id", "citation_key"}: continue
            candidates = [(getattr(o.entry, name), o) for o in cluster if getattr(o.entry, name)]
            if not candidates:
                selected[name] = [] if name == "authors" else None
                continue
            candidates.sort(key=lambda item: (-sum(bool(getattr(item[1].entry, f.name)) for f in fields(BibEntry)),
                                              item[1].version, item[1].occurrence_id))
            selected[name] = candidates[0][0]
            values = {json.dumps(v, ensure_ascii=False) for v, _ in candidates}
            if len(values) > 1:
                conflicts.append(FieldConflict(arxiv_id=arxiv_id, occurrence_ids=[o.occurrence_id for o in cluster],
                                               field_name=name, values=sorted(values),
                                               selected_value=json.dumps(selected[name], ensure_ascii=False),
                                               resolution="Most populated source, earliest version, occurrence ID"))
        entries.append(BibEntry(arxiv_id=arxiv_id, citation_key=key, **selected))
    key_targets: dict[tuple[int, str], set[str]] = defaultdict(set)
    for occ in good:
        if occ.original_key: key_targets[(occ.version, occ.original_key)].add(canonical[occ.occurrence_id])
    key_map = {}
    for pair, targets in sorted(key_targets.items()):
        if len(targets) == 1:
            key_map[pair] = next(iter(targets))
        else:
            diagnostics.append(Diagnostic(code="KEY_CONFLICT", severity="error", message=f"Ambiguous citation key {pair[1]}",
                                          arxiv_id=arxiv_id, version=pair[0], affected_versions=[pair[0]]))
    decisions = list({decision.decision_id: decision for decision in decisions}.values())
    return UnifiedBibliography(arxiv_id=arxiv_id, entries=sorted(entries, key=lambda e: e.citation_key),
                               key_map=key_map, occurrences=occurrences, conflicts=conflicts,
                               identity_decisions=decisions, diagnostics=diagnostics)
