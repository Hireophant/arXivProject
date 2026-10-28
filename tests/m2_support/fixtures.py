"""Mẫu contract dựng tay để owner làm độc lập, KHÔNG gọi prototype nào.

Khánh: tự tạo thư mục/files theo TEX/BIB khi test gather (TemporaryDirectory).
Khang/Nguyên: make_gathered()/make_raw_tree(), không cần Khánh code xong.
Danh: make_raw_tree()/make_unified_bibliography()/make_normalized_tree().
Metrics: make_expected_publication() là expected dựng tay, không phải parser output.
Mỗi lần gọi tạo objects mới. Không sửa fixtures chung trong nhánh owner.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

from src.parsing.contracts import (
    BibliographyExtraction, BibliographyLocation, BibEntry, BibOccurrence,
    DedupCount, ElementOccurrence, ElementRow, GatherResult, HierarchyRow,
    IdentityDecision, ParsedPublication, PublicationInput, RawNode, SourceFile, SourceSpan,
    UnifiedBibliography, VersionInput, VersionTree,
)

PAPER = "2606.20274"
SNAPSHOT = "a" * 64  # Synthetic, không phải snapshot của raw thật.
TITLE = "A synthetic reference"
AUTHORS = ["An Nguyen", "Binh Tran"]
NORMALIZED_SENTENCE = r"We study X."
CITED_SENTENCE = r"See \cite{alpha}."


def tex(version: int = 1) -> str:
    key = "alpha" if version == 1 else "beta"
    return ("\\documentclass{article}\n\\begin{document}\n\\section{Introduction}\n"
            f"We study X. See \\cite{{{key}}}.\n"
            "\\bibliography{refs}\n\\end{document}\n")


def bib(version: int = 1) -> str:
    if version == 1:
        return "@article{alpha, title={A synthetic reference}, author={An Nguyen and Binh Tran}, year={2020}}"
    return "@article{beta, title={A synthetic reference}, author={An Nguyen and Binh Tran}, year={2020}, doi={10.1234/example}}"


def make_version(version: int = 1, source_dir: Path | None = None) -> VersionInput:
    return VersionInput(arxiv_id=PAPER, version=version,
                        source_dir=source_dir or Path('/SYNTHETIC-NOT-A-REAL-CORPUS') / f'v{version}',
                        source_status="tex", source_fingerprint=str(version) * 64)


def make_publication_input() -> PublicationInput:
    return PublicationInput(arxiv_id=PAPER, versions=[make_version(1), make_version(2)],
                            snapshot_id=SNAPSHOT, preparation_run_id="synthetic-preparation",
                            corpus_root=Path('/SYNTHETIC-NOT-A-REAL-CORPUS'))


def make_gathered(version: int = 1) -> GatherResult:
    text = tex(version)
    start = text.index(r"\bibliography")
    declared = SourceSpan(path="main.tex", start=start, end=start + len(r"\bibliography{refs}"),
                          flat_start=start, flat_end=start + len(r"\bibliography{refs}"))
    return GatherResult(version_input=make_version(version), root_path="main.tex", latex=text,
                        source_map=[SourceSpan(path="main.tex", start=0, end=len(text), flat_start=0, flat_end=len(text))],
                        bib_paths=[BibliographyLocation(path="refs.bib", kind="bib", declared_at=declared, exists=True)],
                        source_files=[SourceFile(path="main.tex", encoding="utf-8-sig",
                                                 sha256=hashlib.sha256(text.encode()).hexdigest())], status="ready")


def make_raw_tree(version: int = 1) -> VersionTree:
    text = tex(version)
    key = "alpha" if version == 1 else "beta"
    def span(fragment):
        start = text.index(fragment)
        return [SourceSpan(path="main.tex", start=start, end=start+len(fragment),
                           flat_start=start, flat_end=start+len(fragment))]
    first, second = "We study X.", f"See \\cite{{{key}}}."
    paragraph = first + " " + second
    return VersionTree(arxiv_id=PAPER, version=version, root_local_id="r", status="parsed",
                       source_fingerprint=str(version)*64, bibliography_blocks=[], nodes=[
        RawNode(local_id="r", parent_local_id=None, kind="document", content=f"Version {version} root", position=0),
        RawNode(local_id="h", parent_local_id="r", kind="heading", content="Introduction", position=0,
                heading_level=1, source_spans=span("Introduction")),
        RawNode(local_id="p", parent_local_id="h", kind="paragraph", content=paragraph, position=0,
                source_spans=span(paragraph)),
        RawNode(local_id="s1", parent_local_id="p", kind="sentence", content=first, position=0, source_spans=span(first)),
        RawNode(local_id="s2", parent_local_id="p", kind="sentence", content=second, position=1, source_spans=span(second)),
    ])


def make_extraction(version: int = 1) -> BibliographyExtraction:
    raw = bib(version)
    key = "alpha" if version == 1 else "beta"
    entry = BibEntry(arxiv_id=PAPER, citation_key=key, entry_type="article", title=TITLE,
                     authors=list(AUTHORS), year=2020, doi=None if version == 1 else "10.1234/example")
    occurrence = BibOccurrence(occurrence_id=f"{PAPER}:v{version}:refs.bib:0:{len(raw)}",
                              arxiv_id=PAPER, version=version, entry=entry, original_key=key,
                              source_spans=[SourceSpan(path="refs.bib", start=0, end=len(raw))],
                              source_fingerprint=str(version)*64, raw=raw, authors_complete=True)
    return BibliographyExtraction(arxiv_id=PAPER, version=version, occurrences=[occurrence])


def make_unified_bibliography() -> UnifiedBibliography:
    # Expected thủ công: full authors/year đều khớp nên C3 cho merge, DOI được union.
    return UnifiedBibliography(arxiv_id=PAPER, entries=[BibEntry(arxiv_id=PAPER,
        citation_key="alpha", entry_type="article", title=TITLE, authors=list(AUTHORS),
        year=2020, doi="10.1234/example")], key_map={(1,"alpha"):"alpha", (2,"beta"):"alpha"},
        occurrences=[make_extraction(1).occurrences[0], make_extraction(2).occurrences[0]],
        identity_decisions=[IdentityDecision(decision_id="synthetic-auto-merge-1", arxiv_id=PAPER,
            occurrence_ids=[make_extraction(1).occurrences[0].occurrence_id, make_extraction(2).occurrences[0].occurrence_id],
            source_fingerprints={make_extraction(v).occurrences[0].occurrence_id: str(v)*64 for v in (1,2)},
            outcome="merge", rule="identity_v1.full_authors_title_year", evidence="Synthetic title/full authors/year match; DOI union.",
            reviewer=None, input_snapshot_id=None, code_revision="synthetic-fixture")])


def make_normalized_tree(version: int = 1) -> VersionTree:
    from src.parsing.contracts import NORMALIZATION_VERSION
    tree = deepcopy(make_raw_tree(version))
    # Expected dựng tay, không gọi normalize/rewrite prototypes.
    tree.nodes[2].content = "We study X. See \\cite{alpha}."
    tree.nodes[4].content = "See \\cite{alpha}."
    tree.normalized_with = NORMALIZATION_VERSION
    return tree


def make_expected_publication() -> ParsedPublication:
    # IDs fixture là discriminants hợp lệ dựng tay; không khẳng định hash algorithm đã chạy.
    prefix = "2606-20274#"
    elements = [ElementRow(arxiv_id=PAPER, element_id=prefix+"root-v1", kind="document", content="Version 1 root"),
                ElementRow(arxiv_id=PAPER, element_id=prefix+"root-v2", kind="document", content="Version 2 root")]
    for local, kind, content in [("h","heading","Introduction"),
        ("p","paragraph","We study X. See \\cite{alpha}."),
        ("s1","sentence","We study X."), ("s2","sentence","See \\cite{alpha}.")]:
        elements.append(ElementRow(arxiv_id=PAPER, element_id=prefix+local, kind=kind, content=content))
    edges, occurrences = [], []
    for version in (1,2):
        for node in make_normalized_tree(version).nodes:
            eid = prefix+(f"root-v{version}" if node.local_id=="r" else node.local_id)
            parent_eid = None if node.parent_local_id is None else prefix+(f"root-v{version}" if node.parent_local_id=="r" else node.parent_local_id)
            if parent_eid is not None:
                edges.append(HierarchyRow(arxiv_id=PAPER,version=version,element_id=eid,parent_id=parent_eid))
            occurrences.append(ElementOccurrence(arxiv_id=PAPER, version=version, local_id=node.local_id,
                parent_local_id=node.parent_local_id, element_id=eid, position=node.position,
                source_spans=node.source_spans, heading_level=node.heading_level))
    unified = make_unified_bibliography()
    return ParsedPublication(arxiv_id=PAPER,elements=elements,hierarchy=edges,bibtex=unified.entries,
        version_states={1:"parsed",2:"parsed"},occurrences=occurrences,
        root_ids={1:prefix+"root-v1",2:prefix+"root-v2"}, key_map=unified.key_map,
        bib_occurrences=unified.occurrences, identity_decisions=unified.identity_decisions, conflicts=[], diagnostics=[],
        counts_before_after=[DedupCount(kind="document",before=2,after=2),
            DedupCount(kind="heading",before=2,after=1),DedupCount(kind="paragraph",before=2,after=1),
            DedupCount(kind="sentence",before=4,after=2),DedupCount(kind="bibtex",before=2,after=1)],
        export_ready=True)
