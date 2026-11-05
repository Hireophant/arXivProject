"""Module gather.py — Khánh / KH2.

Discovers compilation root and recursively traverses LaTeX include commands
(\\input, \\include) to produce a flattened LaTeX stream, accurate source spans,
and declared bibliography locations without modifying source files.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Literal

from .khang_lex import scan

from .contracts import (
    BibliographyLocation,
    Diagnostic,
    GatherResult,
    GatherStatus,
    SourceFile,
    SourceSpan,
    VersionInput,
)


def read_source(source_dir: Path, relative_path: str) -> tuple[str, SourceFile]:
    """Đọc bytes chỉ dưới source root, không theo symlink/đường dẫn thoát root.

    Decode UTF-8-SIG trước (loại bỏ BOM nếu có), fallback Latin-1 strict.
    Offsets tính theo chuỗi Unicode đã decode.
    """
    source_dir = Path(source_dir).resolve()
    target = (source_dir / relative_path).resolve()

    if not target.is_relative_to(source_dir):
        raise ValueError(f"Path escapes source root: {relative_path}")
    if not target.is_file():
        raise FileNotFoundError(f"Source file not found: {relative_path}")

    raw_bytes = target.read_bytes()
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        text = raw_bytes.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1")
        encoding = "latin-1"

    rel_posix = target.relative_to(source_dir).as_posix()
    return text, SourceFile(path=rel_posix, encoding=encoding, sha256=sha256_hash)


def _resolve_include_path(source_dir: Path, raw_target: str, current_file: str) -> tuple[str | None, str | None]:
    raw_clean = raw_target.strip().strip('"').strip("'")
    if "\\" in raw_clean:
        # Dynamic macro path
        return None, "UNSUPPORTED_CONTENT"

    # 1. Thử root-relative
    candidates: list[Path] = []
    if not raw_clean.endswith(".tex") and not PurePosixPath(raw_clean).suffix:
        candidates.append(source_dir / f"{raw_clean}.tex")
        candidates.append(source_dir / raw_clean)
    else:
        candidates.append(source_dir / raw_clean)

    for cand in candidates:
        cand_res = cand.resolve()
        if cand_res.is_file() and cand_res.is_relative_to(source_dir.resolve()):
            return cand_res.relative_to(source_dir.resolve()).as_posix(), None

    # 2. Fallback relative to current file
    current_dir = (source_dir / current_file).parent
    fallback_candidates: list[Path] = []
    if not raw_clean.endswith(".tex") and not PurePosixPath(raw_clean).suffix:
        fallback_candidates.append(current_dir / f"{raw_clean}.tex")
        fallback_candidates.append(current_dir / raw_clean)
    else:
        fallback_candidates.append(current_dir / raw_clean)

    for cand in fallback_candidates:
        cand_res = cand.resolve()
        if cand_res.is_file() and cand_res.is_relative_to(source_dir.resolve()):
            return cand_res.relative_to(source_dir.resolve()).as_posix(), "INCLUDE_PATH_FALLBACK"

    return None, "INCLUDE_MISSING"


def _has_active_documentclass(text: str) -> bool:
    """Recognize an active declaration, excluding literal/comment examples."""
    return any(t.kind == 'command' and t.name == 'documentclass' and t.argument is not None
               for t in scan(text))


def find_root(source_dir: Path) -> str:
    """Trả root path relative POSIX có documentclass đang có hiệu lực.

    Đọc các file .tex, bỏ qua comment/verbatim; không strip phần sau escaped percent.
    Nếu 0 hoặc nhiều hơn 1 candidate -> raise ValueError rõ ràng.
    """
    source_dir = Path(source_dir).resolve()
    if not source_dir.exists():
        raise ValueError(f"Source directory does not exist: {source_dir}")

    candidates: list[str] = []
    texts: dict[str, str] = {}
    for tex_path in sorted(source_dir.rglob("*.tex")):
        if not tex_path.is_file():
            continue
        rel_posix = tex_path.relative_to(source_dir).as_posix()
        try:
            text, _ = read_source(source_dir, rel_posix)
            texts[rel_posix] = text
            if _has_active_documentclass(text):
                candidates.append(rel_posix)
        except Exception:
            continue

    if len(candidates) == 1:
        declaration = candidates[0]
        if not any(t.kind == 'begin' and t.name == 'document' for t in scan(texts[declaration])):
            tokens = {path: list(scan(text)) for path, text in texts.items()}
            document_files = {path for path, stream in tokens.items()
                              if any(t.kind == 'begin' and t.name == 'document' for t in stream)}
            # A package fragment can own documentclass while its unique parent
            # owns the actual document. Follow active include evidence, not names.
            parents: dict[str, set[str]] = {}
            for path, stream in tokens.items():
                for token in stream:
                    if token.kind == 'command' and token.name in ('input', 'include') and token.argument:
                        target, _ = _resolve_include_path(source_dir, texts[path][slice(*token.argument)], path)
                        if target is not None: parents.setdefault(target, set()).add(path)
            owners, seen, pending = set(), set(), [declaration]
            while pending:
                path = pending.pop()
                if path in seen: continue
                seen.add(path)
                for parent in parents.get(path, ()):
                    if parent in document_files: owners.add(parent)
                    pending.append(parent)
            if owners: candidates = sorted(owners)
    if len(candidates) == 0:
        raise ValueError(f"No active \\documentclass found in {source_dir}")
    if len(candidates) > 1:
        raise ValueError(f"Multiple active \\documentclass candidates found: {candidates}")

    return candidates[0]


def _parse_braced_arg(text: str, start_idx: int) -> tuple[str, int] | None:
    """Trích xuất nội dung trong cặp ngoặc { ... } cân bằng."""
    if start_idx >= len(text) or text[start_idx] != "{":
        return None
    depth = 0
    i = start_idx
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx + 1:i], i + 1
        i += 1
    return None


def expand_includes(version: VersionInput, root_path: str) -> GatherResult:
    """Theo input/include bắc cầu theo thứ tự; include lặp hợp lệ xuất hiện lại.

    Dùng recursion stack để chặn cycle, không dùng visited-set toàn cục.
    """
    source_dir = version.source_dir
    if not source_dir or not source_dir.exists():
        raise ValueError("Cannot expand includes without valid source_dir")

    flattened_parts: list[str] = []
    source_map: list[SourceSpan] = []
    source_files_map: dict[str, SourceFile] = {}
    bib_paths: list[BibliographyLocation] = []
    diagnostics: list[Diagnostic] = list(version.diagnostics)
    current_flat_len = 0

    def traverse(rel_path: str, recursion_stack: list[str]) -> None:
        nonlocal current_flat_len
        try:
            file_text, source_file = read_source(source_dir, rel_path)
            if rel_path not in source_files_map:
                source_files_map[rel_path] = source_file
        except Exception as e:
            diagnostics.append(
                Diagnostic(
                    code="INCLUDE_MISSING",
                    severity="error",
                    message=f"Failed to read file '{rel_path}': {e}",
                    arxiv_id=version.arxiv_id,
                    version=version.version,
                    path=rel_path,
                    affected_versions=[version.version],
                )
            )
            return

        last_idx = 0
        i = 0
        in_escape = 0

        while i < len(file_text):
            ch = file_text[i]
            if ch == "\\":
                in_escape += 1
                i += 1
                continue

            if ch == "%":
                if in_escape % 2 == 0:
                    # Bắt đầu comment: bỏ qua tới cuối dòng
                    newline_idx = file_text.find("\n", i)
                    if newline_idx == -1:
                        i = len(file_text)
                    else:
                        i = newline_idx + 1
                    in_escape = 0
                    continue
                in_escape = 0
                i += 1
                continue

            in_escape = 0

            # Kiểm tra lệnh LaTeX bắt đầu bằng backslash
            if i > 0 and file_text[i - 1] == "\\":
                # Kiểm tra xem backslash đó có bị escape hay không
                # Đếm số backslash liền trước vị trí i-1
                slash_count = 1
                k = i - 2
                while k >= 0 and file_text[k] == "\\":
                    slash_count += 1
                    k -= 1
                if slash_count % 2 == 1:
                    cmd_match = re.match(r"^(input|include|bibliography|addbibresource)\b", file_text[i:])
                    if cmd_match:
                        cmd_name = cmd_match.group(1)
                        cmd_start = i - 1  # vị trí dấu '\\'
                        after_cmd = i + len(cmd_name)

                        # Tìm đối số { ... }
                        after_space = after_cmd
                        while after_space < len(file_text) and file_text[after_space] in " \t":
                            after_space += 1

                        if after_space < len(file_text) and file_text[after_space] == "{":
                            res_arg = _parse_braced_arg(file_text, after_space)
                            if res_arg:
                                arg_str, cmd_end = res_arg
                                if cmd_name in ("input", "include"):
                                    # Emit text trước lệnh include
                                    if cmd_start > last_idx:
                                        chunk = file_text[last_idx:cmd_start]
                                        span = SourceSpan(
                                            path=rel_path,
                                            start=last_idx,
                                            end=cmd_start,
                                            flat_start=current_flat_len,
                                            flat_end=current_flat_len + len(chunk),
                                        )
                                        source_map.append(span)
                                        flattened_parts.append(chunk)
                                        current_flat_len += len(chunk)

                                    # Kiểm tra xem có phải file .bbl hay không
                                    if arg_str.strip().endswith(".bbl"):
                                        bbl_clean = arg_str.strip()
                                        bbl_exists = (source_dir / bbl_clean).is_file()
                                        decl_span = SourceSpan(
                                            path=rel_path,
                                            start=cmd_start,
                                            end=cmd_end,
                                            flat_start=current_flat_len,
                                            flat_end=current_flat_len,
                                        )
                                        bib_paths.append(
                                            BibliographyLocation(
                                                path=bbl_clean,
                                                kind="bbl",
                                                declared_at=decl_span,
                                                exists=bbl_exists,
                                            )
                                        )
                                    else:
                                        # Resolve và expand include
                                        resolved, err_code = _resolve_include_path(source_dir, arg_str, rel_path)
                                        if err_code == "INCLUDE_PATH_FALLBACK" and resolved:
                                            diagnostics.append(
                                                Diagnostic(
                                                    code="INCLUDE_PATH_FALLBACK",
                                                    severity="warning",
                                                    message=f"Include path resolved via relative fallback: {arg_str} -> {resolved}",
                                                    arxiv_id=version.arxiv_id,
                                                    version=version.version,
                                                    path=rel_path,
                                                    affected_versions=[version.version],
                                                )
                                            )

                                        if not resolved:
                                            diagnostics.append(
                                                Diagnostic(
                                                    code=err_code or "INCLUDE_MISSING",
                                                    severity="error",
                                                    message=f"Could not resolve include '{arg_str}' from {rel_path}",
                                                    arxiv_id=version.arxiv_id,
                                                    version=version.version,
                                                    path=rel_path,
                                                    offset=cmd_start,
                                                    affected_versions=[version.version],
                                                )
                                            )
                                        elif resolved in recursion_stack:
                                            diagnostics.append(
                                                Diagnostic(
                                                    code="INCLUDE_CYCLE",
                                                    severity="error",
                                                    message=f"Include cycle detected: {' -> '.join(recursion_stack)} -> {resolved}",
                                                    arxiv_id=version.arxiv_id,
                                                    version=version.version,
                                                    path=rel_path,
                                                    offset=cmd_start,
                                                    affected_versions=[version.version],
                                                )
                                            )
                                        else:
                                            # Thêm newline phân cách nếu cần
                                            if flattened_parts and not flattened_parts[-1].endswith("\n"):
                                                flattened_parts.append("\n")
                                                current_flat_len += 1

                                            recursion_stack.append(resolved)
                                            traverse(resolved, recursion_stack)
                                            recursion_stack.pop()

                                            if flattened_parts and not flattened_parts[-1].endswith("\n"):
                                                flattened_parts.append("\n")
                                                current_flat_len += 1

                                    last_idx = cmd_end
                                    i = cmd_end
                                    continue

                                elif cmd_name in ("bibliography", "addbibresource"):
                                    # Ghi nhận bibliography location
                                    decl_span = SourceSpan(
                                        path=rel_path,
                                        start=cmd_start,
                                        end=cmd_end,
                                        flat_start=current_flat_len + (cmd_start - last_idx),
                                        flat_end=current_flat_len + (cmd_end - last_idx),
                                    )
                                    for bib_item in arg_str.split(","):
                                        item_clean = bib_item.strip().strip('"').strip("'")
                                        if item_clean:
                                            if not item_clean.endswith(".bib"):
                                                bib_file = f"{item_clean}.bib"
                                            else:
                                                bib_file = item_clean
                                            exists = (source_dir / bib_file).is_file()
                                            bib_paths.append(
                                                BibliographyLocation(
                                                    path=bib_file,
                                                    kind="bib",
                                                    declared_at=decl_span,
                                                    exists=exists,
                                                )
                                            )
                                    # KHÔNG bỏ qua lệnh bibliography khỏi body: tiếp tục duyệt bình thường!
            i += 1

        # Emit phần text còn lại của file
        if len(file_text) > last_idx:
            chunk = file_text[last_idx:]
            span = SourceSpan(
                path=rel_path,
                start=last_idx,
                end=len(file_text),
                flat_start=current_flat_len,
                flat_end=current_flat_len + len(chunk),
            )
            source_map.append(span)
            flattened_parts.append(chunk)
            current_flat_len += len(chunk)

    # Bắt đầu duyệt từ root
    traverse(root_path, [root_path])
    full_latex = "".join(flattened_parts)

    has_errors = any(d.severity == "error" for d in diagnostics)
    if has_errors:
        status: GatherStatus = "partial" if full_latex.strip() else "failed"
    else:
        status = "ready"

    return GatherResult(
        version_input=version,
        root_path=root_path,
        latex=full_latex,
        source_map=source_map,
        bib_paths=bib_paths,
        source_files=list(source_files_map.values()),
        status=status,
        diagnostics=diagnostics,
    )


def gather_version(version: VersionInput) -> GatherResult:
    """API chính của module gather."""
    if version.source_status == "no_tex":
        return GatherResult(
            version_input=version,
            root_path=None,
            latex="",
            source_map=[],
            bib_paths=[],
            source_files=[],
            status="empty_no_tex",
            diagnostics=list(version.diagnostics),
        )

    if version.source_status == "blocked":
        return GatherResult(
            version_input=version,
            root_path=None,
            latex="",
            source_map=[],
            bib_paths=[],
            source_files=[],
            status="blocked_input",
            diagnostics=list(version.diagnostics),
        )

    if not version.source_dir or not version.source_dir.exists():
        diag = Diagnostic(
            code="SOURCE_MISSING",
            severity="error",
            message=f"Source directory missing for {version.arxiv_id} v{version.version}",
            arxiv_id=version.arxiv_id,
            version=version.version,
            affected_versions=[version.version],
        )
        return GatherResult(
            version_input=version,
            root_path=None,
            latex="",
            source_map=[],
            bib_paths=[],
            source_files=[],
            status="failed",
            diagnostics=list(version.diagnostics) + [diag],
        )

    try:
        root = find_root(version.source_dir)
    except Exception as e:
        diag = Diagnostic(
            code="ROOT_UNRESOLVED",
            severity="error",
            message=f"Failed to find root file: {e}",
            arxiv_id=version.arxiv_id,
            version=version.version,
            affected_versions=[version.version],
        )
        return GatherResult(
            version_input=version,
            root_path=None,
            latex="",
            source_map=[],
            bib_paths=[],
            source_files=[],
            status="failed",
            diagnostics=list(version.diagnostics) + [diag],
        )

    return expand_includes(version, root)
