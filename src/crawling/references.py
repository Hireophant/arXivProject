"""Nguyên: lấy references.json từ Semantic Scholar cho từng bài chính.

Ngày gửi của các bài được dẫn được bổ sung qua DateLookup của Khánh.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import DateLookup, HttpPolicy, ReferenceResult

_API = "https://api.semanticscholar.org/graph/v1/paper"
_FIELDS = (
    "citedPaper.title,citedPaper.authors,citedPaper.externalIds,"
    "citedPaper.publicationDate"
)
_PAGE_SIZE = 100


def _request_s2(
    arxiv_id: str, *, offset: int, policy: HttpPolicy,
    _with_attempts: bool = False,
) -> dict[str, Any] | tuple[dict[str, Any], int]:
    """Lấy một trang references, retry lỗi tạm thời theo HttpPolicy."""
    url = f"{_API}/ARXIV:{arxiv_id}/references"
    headers = {"User-Agent": policy["user_agent"]}
    if api_key := os.getenv("S2_API_KEY"):
        headers["x-api-key"] = api_key

    last_error: Exception | None = None
    for attempt in range(1, policy["max_attempts"] + 1):
        time.sleep(policy["s2_delay_seconds"])
        try:
            response = requests.get(
                url,
                params={"fields": _FIELDS, "offset": offset, "limit": _PAGE_SIZE},
                headers=headers,
                timeout=policy["timeout_seconds"],
            )
            response.raise_for_status()
            payload = response.json()
            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("data"), list)
                or any(not isinstance(row, dict) for row in payload["data"])
            ):
                raise ValueError("Semantic Scholar returned an invalid references page.")
            return (payload, attempt) if _with_attempts else payload
        except requests.HTTPError as exc:
            last_error = exc
            status = exc.response.status_code if exc.response is not None else None
            if status == 404 or (status is not None and status < 500 and status != 429):
                exc._attempts = attempt
                raise
            retry_after = exc.response.headers.get("Retry-After") if exc.response else None
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            retry_after = None

        if attempt < policy["max_attempts"]:
            try:
                wait = float(retry_after) if retry_after is not None else 0.0
            except ValueError:
                wait = 0.0
            wait = max(wait, min(2 ** (attempt - 1), policy["backoff_cap_seconds"]))
            time.sleep(min(wait, policy["backoff_cap_seconds"]))

    assert last_error is not None
    last_error._attempts = policy["max_attempts"]
    raise last_error


def _atomic_json(path: Path, value: Any) -> bytes:
    """Ghi JSON UTF-8 nguyên tử và trả về đúng bytes đã ghi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temp:
            temp_name = temp.name
            temp.write(content)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return content


def _cached_result(arxiv_id: str, paper_dir: Path) -> ReferenceResult | None:
    data_path = paper_dir / "references.json"
    receipt_path = paper_dir / ".references_receipt.json"
    try:
        data_bytes = data_path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or not isinstance(receipt.get("result"), dict):
            return None
        result = receipt["result"]
        references = json.loads(data_bytes)
        if (
            receipt.get("schema_version") != "1.0"
            or receipt.get("arxiv_id") != arxiv_id
            or result.get("arxiv_id") != arxiv_id
            or result.get("status") != "success"
            or receipt.get("references_sha256") != hashlib.sha256(data_bytes).hexdigest()
            or not isinstance(references, dict)
            or references != result.get("references")
            or result.get("kept_references") != len(references)
            or any(
                not isinstance(item, dict)
                or set(item) != {
                    "title", "authors", "submission_date",
                    "semantic_scholar_id", "publication_date",
                }
                or not isinstance(item.get("authors"), list)
                or any(not isinstance(author, str) for author in item["authors"])
                or (item.get("title") is not None and not isinstance(item["title"], str))
                or (item.get("submission_date") is not None and not isinstance(item["submission_date"], str))
                or (item.get("semantic_scholar_id") is not None and not isinstance(item["semantic_scholar_id"], str))
                or (item.get("publication_date") is not None and not isinstance(item["publication_date"], str))
                for item in references.values()
            )
        ):
            return None
        result = dict(result)
        result.update(attempts=0, used_cache=True, elapsed_seconds=0.0)
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _arxiv_key(arxiv_id: str) -> str:
    """Chuẩn hóa mã mới thành key có dấu gạch ngang; giữ mã archive cũ."""
    return arxiv_id if "/" in arxiv_id else arxiv_id.replace(".", "-")


def collect_references(
    arxiv_id: str, paper_dir: Path, date_lookup: DateLookup, *,
    policy: HttpPolicy, use_cache: bool = True,
) -> ReferenceResult:
    """Lấy tất cả trang references, giữ bài arXiv và lưu kết quả có receipt."""
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", arxiv_id):
        raise ValueError(f"Invalid arXiv ID: {arxiv_id!r}")
    if (
        policy["timeout_seconds"] <= 0 or policy["max_attempts"] < 1
        or policy["s2_delay_seconds"] < 0 or policy["backoff_cap_seconds"] < 0
    ):
        raise ValueError("Invalid HTTP policy.")

    started = time.monotonic()
    paper_dir = Path(paper_dir)
    if use_cache and (cached := _cached_result(arxiv_id, paper_dir)) is not None:
        cached["elapsed_seconds"] = time.monotonic() - started
        return cached

    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    pages: list[dict[str, Any]] = []
    attempts = 0
    offset = 0
    pagination_complete = False
    error: str | None = None
    not_found = False

    while True:
        try:
            page, page_attempts = _request_s2(
                arxiv_id, offset=offset, policy=policy, _with_attempts=True
            )
            assert isinstance(page, dict)
            attempts += page_attempts
        except requests.HTTPError as exc:
            attempts += getattr(exc, "_attempts", 1)
            status_code = exc.response.status_code if exc.response is not None else None
            not_found = status_code == 404 and not pages
            error = f"Semantic Scholar HTTP {status_code or 'error'}: {exc}"
            break
        except (requests.RequestException, ValueError) as exc:
            attempts += getattr(exc, "_attempts", policy["max_attempts"])
            error = f"Semantic Scholar request failed: {exc}"
            break

        rows = page["data"]
        response_offset = page.get("offset")
        if response_offset is not None and response_offset != offset:
            error = "Semantic Scholar returned a page for the wrong offset."
            break
        pages.extend(rows)
        next_offset = page.get("next")
        if next_offset is None:
            # A short page is the API's end-of-results signal when `next` is omitted.
            pagination_complete = len(rows) < _PAGE_SIZE
            if not pagination_complete:
                error = "Pagination is incomplete: full page returned without a next offset."
            break
        if not isinstance(next_offset, int) or next_offset <= offset:
            error = "Semantic Scholar returned an invalid next offset."
            break
        if next_offset != offset + len(rows):
            error = "Semantic Scholar pagination skipped or overlapped results."
            break
        offset = next_offset

    raw_refs: dict[str, dict[str, Any]] = {}
    conflicts = False
    requested_ids: dict[str, str] = {}
    for row in pages:
        cited = row.get("citedPaper")
        if not isinstance(cited, dict):
            continue
        ext = cited.get("externalIds")
        if not isinstance(ext, dict):
            continue
        cited_id = ext.get("ArXiv")
        if not isinstance(cited_id, str) or not cited_id.strip():
            continue
        cited_id = cited_id.strip()
        requested_ids[cited_id] = cited_id
        authors = cited.get("authors") or []
        authors = [a["name"].strip() for a in authors if isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"].strip()]
        item = {
            "title": cited.get("title") if isinstance(cited.get("title"), str) else None,
            "authors": authors,
            "semantic_scholar_id": cited.get("paperId") if isinstance(cited.get("paperId"), str) else None,
            "publication_date": cited.get("publicationDate") if isinstance(cited.get("publicationDate"), str) else None,
        }
        key = _arxiv_key(cited_id)
        previous = raw_refs.get(key)
        if previous is None:
            raw_refs[key] = item
        else:
            for field, value in item.items():
                old = previous[field]
                if old in (None, []) and value not in (None, []):
                    previous[field] = value
                elif value not in (None, []) and old != value:
                    conflicts = True

    dates: dict[str, str | None] = {}
    date_errors: dict[str, str] = {}
    if requested_ids:
        try:
            looked_up = date_lookup(list(requested_ids))
            dates = looked_up.get("dates", {}) if isinstance(looked_up, dict) else {}
            date_errors = looked_up.get("errors", {}) if isinstance(looked_up, dict) else {}
            if not isinstance(dates, dict):
                dates = {}
            if not isinstance(date_errors, dict):
                date_errors = {}
        except Exception as exc:
            date_errors = {paper_id: str(exc) for paper_id in requested_ids}

    references: dict[str, dict[str, Any]] = {}
    missing_dates = 0
    incomplete = 0
    for key, item in raw_refs.items():
        cited_id = next(original for original in requested_ids if _arxiv_key(original) == key)
        submission_date = dates.get(cited_id)
        if submission_date is not None:
            try:
                datetime.strptime(submission_date, "%Y-%m-%d")
            except (TypeError, ValueError):
                date_errors[cited_id] = "DateLookup returned a non-ISO submission date."
                submission_date = None
        if not submission_date and cited_id not in date_errors:
            date_errors[cited_id] = "DateLookup did not return a submission date."
        item["submission_date"] = submission_date
        references[key] = item
        if not submission_date:
            missing_dates += 1
        if not item["title"] or not item["authors"] or not item["semantic_scholar_id"] or not submission_date:
            incomplete += 1

    if not pages and error:
        status = "not_found" if not_found else "failed"
    elif not pagination_complete or error or incomplete or conflicts or date_errors:
        status = "partial"
    else:
        status = "success"

    partial_reasons = []
    if not pagination_complete and pages:
        partial_reasons.append("references pagination is incomplete")
    if incomplete:
        partial_reasons.append(f"{incomplete} references have missing required metadata")
    if conflicts:
        partial_reasons.append("duplicate arXiv IDs have conflicting metadata")
    if date_errors:
        partial_reasons.append(f"date lookup failed for {len(date_errors)} IDs")
    result: ReferenceResult = {
        "arxiv_id": arxiv_id,
        "status": status,
        "references": references,
        "total_references": len(pages) if pagination_complete else None,
        "kept_references": len(references),
        "missing_submission_dates": missing_dates,
        "incomplete_references": incomplete,
        "pagination_complete": pagination_complete,
        "retrieved_at": retrieved_at,
        "elapsed_seconds": time.monotonic() - started,
        "attempts": attempts,
        "used_cache": False,
        "error": error or ("; ".join(partial_reasons) if partial_reasons else None),
    }

    # Only a complete success can replace prior data and become a cache entry.
    if status == "success":
        data_bytes = _atomic_json(paper_dir / "references.json", references)
        receipt = {
            "schema_version": "1.0",
            "arxiv_id": arxiv_id,
            "result": result,
            "references_sha256": hashlib.sha256(data_bytes).hexdigest(),
        }
        _atomic_json(paper_dir / ".references_receipt.json", receipt)
    elif status == "partial" and not (paper_dir / "references.json").exists():
        _atomic_json(paper_dir / "references.json", references)

    return result
