"""Nguyên: retain all S2 references and a separate arXiv matching pool.

Reference submission dates come from the shared OAI arXivRaw DateLookup.
API: https://api.semanticscholar.org/api-docs/graph
Full citations and field/pagination choices:
docs/milestone1/KE_HOACH_MILESTONE_1.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import requests

from . import CrawledReference, DateLookup, HttpPolicy, ReferenceResult
from .discover import METADATA_PREFIX, METADATA_SOURCE, OAI_ENDPOINT

_API = "https://api.semanticscholar.org/graph/v1/paper"
# This /references endpoint accepts flat fields. citedPaper is a response
# wrapper, so using citedPaper.* or authors.name as query fields is incorrect.
_FIELDS = (
    "title,authors,externalIds,publicationDate,year,venue"
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
        # Unauthenticated pool: at most 100 requests per five-minute window.
        minimum = 1.0 if api_key else 3.1
        time.sleep(max(minimum, policy["s2_delay_seconds"]))
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
            retry_after = exc.response.headers.get("Retry-After") if exc.response is not None else None
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            retry_after = None

        if attempt < policy["max_attempts"]:
            try:
                wait = float(retry_after) if retry_after is not None else 0.0
            except ValueError:
                try:
                    wait = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    wait = 0.0
            if not math.isfinite(wait):
                wait = 0.0
            wait = max(wait, min(2 ** (attempt - 1), policy["backoff_cap_seconds"]))
            time.sleep(wait)  # A server cooldown is never shortened by our backoff cap.

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
    all_path = paper_dir / "references_all.json"
    receipt_path = paper_dir / ".references_receipt.json"
    try:
        data_bytes = data_path.read_bytes()
        all_bytes = all_path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or not isinstance(receipt.get("result"), dict):
            return None
        result = receipt["result"]
        references = json.loads(data_bytes)
        all_references = json.loads(all_bytes)
        timestamp = datetime.fromisoformat(result['retrieved_at'].replace('Z', '+00:00'))
        if timestamp.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - timestamp).total_seconds() <= 86400:
            return None
        if (
            receipt.get("schema_version") != "3.0"
            or receipt.get('metadata_source') != METADATA_SOURCE
            or receipt.get('endpoint') != OAI_ENDPOINT
            or receipt.get('metadata_prefix') != METADATA_PREFIX
            or receipt.get("arxiv_id") != arxiv_id
            or result.get("arxiv_id") != arxiv_id
            or result.get("status") != "success"
            or receipt.get("references_sha256") != hashlib.sha256(data_bytes).hexdigest()
            or receipt.get("all_references_sha256") != hashlib.sha256(all_bytes).hexdigest()
            or not isinstance(all_references, list)
            or all_references != result.get("all_references")
            or result.get("total_references") != len(all_references)
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
        # Use the same typed/invariant checks as the manifest boundary.
        from .pipeline import _references
        _references(result, arxiv_id)
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
    """Giữ mọi references local và pool arXiv riêng; cache xác minh cả hai file."""
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-zA-Z][a-zA-Z0-9.-]*/\d{7})(?:v\d+)?", arxiv_id):
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
            # The API omits `next` on its last page, including a full last page.
            pagination_complete = True
            break
        if not isinstance(next_offset, int) or next_offset <= offset:
            error = "Semantic Scholar returned an invalid next offset."
            break
        if next_offset != offset + len(rows):
            error = "Semantic Scholar pagination skipped or overlapped results."
            break
        offset = next_offset

    raw_refs: dict[str, dict[str, Any]] = {}
    all_references: list[CrawledReference] = []
    conflicts = False
    requested_ids: dict[str, str] = {}
    for row in pages:
        cited = row.get("citedPaper")
        cited = cited if isinstance(cited, dict) else {}
        ext = cited.get("externalIds")
        ext = ext if isinstance(ext, dict) else {}
        cited_id = ext.get("ArXiv")
        cited_id = re.sub(r"v\d+$", "", cited_id.strip()) if isinstance(cited_id, str) and cited_id.strip() else None
        authors = cited.get("authors") or []
        authors = [a["name"].strip() for a in authors if isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"].strip()]
        item = {
            "title": cited.get("title") if isinstance(cited.get("title"), str) else None,
            "authors": authors,
            "semantic_scholar_id": cited.get("paperId") if isinstance(cited.get("paperId"), str) else None,
            "publication_date": cited.get("publicationDate") if isinstance(cited.get("publicationDate"), str) else None,
        }
        all_references.append(dict(
            item, arxiv_id=cited_id, submission_date=None,
            year=cited.get("year") if type(cited.get("year")) is int and cited["year"] >= 0 else None,
            venue=cited.get("venue") if isinstance(cited.get("venue"), str) else None,
            external_ids={k: v for k, v in ext.items() if isinstance(k, str) and (v is None or type(v) in (str, int))},
        ))
        if cited_id is None:
            continue
        requested_ids[cited_id] = cited_id
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
            if not isinstance(looked_up, dict) or looked_up.get('metadata_source') != METADATA_SOURCE:
                raise ValueError('Reference dates must originate from OAI-PMH arXivRaw.')
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

    for item in all_references:
        if item['arxiv_id'] is not None:
            item['submission_date'] = references[_arxiv_key(item['arxiv_id'])]['submission_date']
    incomplete_non_arxiv = sum(
        item['arxiv_id'] is None and (not item['title'] or not item['authors'] or not item['semantic_scholar_id'])
        for item in all_references
    )

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
    # An unresolved non-arXiv citation may legitimately have no authors/paperId
    # in S2. Preserve/count it as source quality, not an incomplete API harvest.
    if conflicts:
        partial_reasons.append("duplicate arXiv IDs have conflicting metadata")
    if date_errors:
        partial_reasons.append(f"date lookup failed for {len(date_errors)} IDs")
    result: ReferenceResult = {
        "arxiv_id": arxiv_id,
        "metadata_source": METADATA_SOURCE,
        "status": status,
        "references": references,
        "all_references": all_references,
        "total_references": len(pages) if pagination_complete else None,
        "kept_references": len(references),
        "missing_submission_dates": missing_dates,
        "incomplete_references": incomplete,
        "incomplete_non_arxiv_references": incomplete_non_arxiv,
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
        all_bytes = _atomic_json(paper_dir / "references_all.json", all_references)
        receipt = {
            "schema_version": "3.0",
            "metadata_source": METADATA_SOURCE,
            "endpoint": OAI_ENDPOINT,
            "metadata_prefix": METADATA_PREFIX,
            "arxiv_id": arxiv_id,
            "result": result,
            "references_sha256": hashlib.sha256(data_bytes).hexdigest(),
            "all_references_sha256": hashlib.sha256(all_bytes).hexdigest(),
        }
        _atomic_json(paper_dir / ".references_receipt.json", receipt)
    elif status == "partial":
        # Preserve any previous complete files; partial attempts remain inspectable.
        has_complete = _cached_result(arxiv_id, paper_dir) is not None
        suffix = ".partial" if has_complete else ""
        _atomic_json(paper_dir / f"references{suffix}.json", references)
        _atomic_json(paper_dir / f"references_all{suffix}.json", all_references)

    return result
