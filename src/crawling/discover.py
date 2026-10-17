"""Khánh: tìm bài, metadata, mọi phiên bản và ngày gửi của bài tham khảo.

Hướng triển khai đã chốt: arXiv API bằng requests + XML Atom, không dùng Kaggle
hay OAI-PMH trong module này. Endpoint: https://export.arxiv.org/api/query.
Tài liệu: https://info.arxiv.org/help/api/user-manual.html
Nhịp: https://info.arxiv.org/help/api/tou.html (>=3 giây, một kết nối).
Chỉ prototype. Không tải nguồn hay ghi metadata.json: pipeline sở hữu ghi file.
Không trả list đơn lẻ: DiscoveryResult ghi rõ quét thiếu/lỗi để không mất bài.
"""

import email.utils
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Literal

import requests

from . import (
    DateLookupResult,
    DiscoveryIssue,
    DiscoveryResult,
    HttpPolicy,
    PaperMetadata,
    PaperRecord,
    Scope,
)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_ABS_URL = "https://arxiv.org/abs/"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _format_utc_date(date_str: str) -> str:
    """Normalize an ISO 8601 date string to YYYY-MM-DD in UTC."""
    clean_str = date_str.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", clean_str):
        return clean_str
    dt = datetime.fromisoformat(clean_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _clean_arxiv_id(raw_id: str) -> tuple[str, int | None]:
    """Clean arXiv ID string, removing URL prefixes and extracting version if present.

    Returns (base_id, version_int_or_None).
    """
    clean = re.sub(r"^https?://arxiv\.org/abs/", "", raw_id.strip())
    clean = re.sub(r"^abs/", "", clean)
    v_match = re.search(r"v(\d+)$", clean)
    version = int(v_match.group(1)) if v_match else None
    base_id = re.sub(r"v\d+$", "", clean)
    return base_id, version


def _http_request_with_policy(
    url: str,
    params: dict[str, Any] | None,
    policy: HttpPolicy,
    allow_400: bool = False,
) -> requests.Response:
    """Execute an HTTP GET request observing pacing, headers, and bounded retries."""
    delay = policy.get("arxiv_delay_seconds", 3.0)
    timeout = policy.get("timeout_seconds", 30.0)
    max_attempts = max(1, policy.get("max_attempts", 3))
    backoff_cap = policy.get("backoff_cap_seconds", 60.0)
    headers = {"User-Agent": policy.get("user_agent", "ArxivCourseProject/0.1")}

    for attempt in range(1, max_attempts + 1):
        if delay > 0:
            time.sleep(delay)

        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 400 and allow_400:
                return resp
            if resp.status_code == 404:
                raise LookupError(f"HTTP 404 Not Found from {url}")
            if resp.status_code in {429, 500, 502, 503, 504}:
                if attempt >= max_attempts:
                    raise RuntimeError(
                        f"HTTP {resp.status_code} from {url} after {max_attempts} attempts: {resp.text[:200]}"
                    )
                # Compute wait time
                wait_sec: float | None = None
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_sec = float(retry_after)
                    except ValueError:
                        try:
                            parsed_dt = email.utils.parsedate_to_datetime(retry_after)
                            wait_sec = max(0.0, (parsed_dt - datetime.now(timezone.utc)).total_seconds())
                        except Exception:
                            wait_sec = None
                if wait_sec is None:
                    backoff = delay * (2 ** (attempt - 1))
                    wait_sec = min(max(backoff, delay), backoff_cap)
                else:
                    # The cap only bounds our own backoff, never the server's
                    # explicit cooldown (which may legitimately be much longer).
                    wait_sec = max(wait_sec, delay)
                time.sleep(wait_sec)
                continue

            raise LookupError(f"HTTP {resp.status_code} from {url}: {resp.text[:200]}")
        except requests.RequestException as exc:
            if attempt >= max_attempts:
                raise RuntimeError(
                    f"Network error requesting {url} after {max_attempts} attempts: {exc}"
                ) from exc
            backoff = delay * (2 ** (attempt - 1))
            wait_sec = min(max(backoff, delay), backoff_cap)
            time.sleep(wait_sec)

    raise RuntimeError(f"Request failed unexpectedly for {url}")


def _parse_atom_entry(entry: ET.Element) -> tuple[str, int | None, dict[str, Any]]:
    """Extract metadata from an Atom <entry> element."""
    id_elem = entry.find(f"{ATOM_NS}id")
    if id_elem is None or not id_elem.text:
        raise ValueError("Atom entry is missing <id> element")
    raw_id = id_elem.text.strip()

    title_elem = entry.find(f"{ATOM_NS}title")
    title_text = " ".join(title_elem.text.split()) if title_elem is not None and title_elem.text else ""

    if "errors#" in raw_id or title_text == "Error":
        raise LookupError(f"arXiv API error entry: {title_text} ({raw_id})")
    if not title_text:
        raise ValueError("Atom entry has empty title")

    base_id, version = _clean_arxiv_id(raw_id)

    authors: list[str] = []
    for a in entry.findall(f"{ATOM_NS}author"):
        name_elem = a.find(f"{ATOM_NS}name")
        if name_elem is not None and name_elem.text and name_elem.text.strip():
            authors.append(" ".join(name_elem.text.split()))
    if not authors:
        raise ValueError(f"Atom entry for {base_id} has no authors")

    pub_elem = entry.find(f"{ATOM_NS}published")
    if pub_elem is None or not pub_elem.text:
        raise ValueError(f"Atom entry for {base_id} missing <published>")
    published = _format_utc_date(pub_elem.text)

    upd_elem = entry.find(f"{ATOM_NS}updated")
    updated = _format_utc_date(upd_elem.text) if upd_elem is not None and upd_elem.text else published

    jref_elem = entry.find(f"{ARXIV_NS}journal_ref")
    venue = " ".join(jref_elem.text.split()) if jref_elem is not None and jref_elem.text and jref_elem.text.strip() else None

    return base_id, version, {
        "title": title_text,
        "authors": authors,
        "published": published,
        "updated": updated,
        "venue": venue,
    }


def _get_submission_history_from_abstract(arxiv_id: str, policy: HttpPolicy) -> dict[int, str]:
    """Inspect abstract page HTML to extract all versions and their UTC dates."""
    url = f"{ARXIV_ABS_URL}{arxiv_id}"
    resp = _http_request_with_policy(url, None, policy)
    idx = resp.text.find("Submission history")
    if idx == -1:
        found = re.findall(r"\[v(\d+)\]", resp.text)
        if not found:
            found = re.findall(rf"/abs/{re.escape(arxiv_id)}v(\d+)", resp.text)
        return {int(x): "" for x in found}

    sub_chunk = resp.text[idx : idx + 3000]
    pattern = r"\[v(\d+)\](?:</a>)?\s*</strong>\s*([A-Za-z]{3},\s*\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{2}:\d{2}:\d{2}(?:\s+[A-Z0-9]+)?)"
    matches = re.findall(pattern, sub_chunk)
    history: dict[int, str] = {}
    for v_str, d_str in matches:
        v = int(v_str)
        try:
            dt = email.utils.parsedate_to_datetime(d_str.strip())
            history[v] = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            parts = d_str.split()
            dt = datetime.strptime(f"{parts[1]} {parts[2]} {parts[3]}", "%d %b %Y")
            history[v] = dt.strftime("%Y-%m-%d")
    return history


def _expand_scope(scope: Scope) -> list[str]:
    """Validate and expand a Scope into a deduplicated list of arXiv IDs."""
    if not isinstance(scope, dict):
        raise ValueError("Scope must be a dictionary.")
    mode = scope.get("mode")
    if mode not in {"ids", "range"}:
        raise ValueError(f"Invalid scope mode: {mode}. Must be 'ids' or 'range'.")

    if mode == "ids":
        raw_ids = scope.get("ids")
        if not isinstance(raw_ids, list) or len(raw_ids) == 0:
            raise ValueError("Scope mode 'ids' requires a non-empty list in 'ids'.")
        seen: set[str] = set()
        unique_ids: list[str] = []
        for x in raw_ids:
            if not isinstance(x, str) or not x.strip():
                raise ValueError("Every ID in scope['ids'] must be a non-empty string.")
            clean_id, _ = _clean_arxiv_id(x)
            if clean_id not in seen:
                seen.add(clean_id)
                unique_ids.append(clean_id)
        return unique_ids

    # mode == "range"
    start_id = scope.get("start_id")
    end_id = scope.get("end_id")
    if not isinstance(start_id, str) or not isinstance(end_id, str):
        raise ValueError("Scope mode 'range' requires 'start_id' and 'end_id' as strings.")

    start_clean = start_id.strip()
    end_clean = end_id.strip()
    start_match = re.match(r"^(\d{4})\.(\d+)$", start_clean)
    end_match = re.match(r"^(\d{4})\.(\d+)$", end_clean)
    if not start_match or not end_match:
        raise ValueError(
            f"Range IDs must be modern arXiv IDs (YYMM.NNNNN): got start='{start_id}', end='{end_id}'"
        )

    yymm_start, num_start_str = start_match.groups()
    yymm_end, num_end_str = end_match.groups()
    if yymm_start != yymm_end:
        raise ValueError(
            f"Range IDs must share the same YYMM prefix: start='{start_id}', end='{end_id}'"
        )
    if len(num_start_str) != len(num_end_str):
        raise ValueError(
            f"Range IDs must have matching suffix digit length: start='{start_id}', end='{end_id}'"
        )

    num_start = int(num_start_str)
    num_end = int(num_end_str)
    if num_start > num_end:
        raise ValueError(
            f"Scope range is reversed (start_id > end_id): start='{start_id}', end='{end_id}'"
        )

    width = len(num_start_str)
    return [f"{yymm_start}.{i:0{width}d}" for i in range(num_start, num_end + 1)]


def discover_papers(scope: Scope, *, policy: HttpPolicy) -> DiscoveryResult:
    """Input: Scope hợp lệ + chính sách HTTP; output: DiscoveryResult.

    Cách làm: kiểm tra mode/ID/range. mode=ids: dùng ids đã cung cấp; mode=range:
    sinh các mã cùng YYMM, bao gồm hai đầu, giữ độ dài phần số. Chia batch
    id_list, gửi requests.get(endpoint, params=...), đọc Atom bằng ElementTree
    với namespace. start/max_results điều khiển phân trang; không coi mặc định
    API là trả hết. Đối chiếu ID yêu cầu với ID trả về, gọi fetch_paper để bổ
    sung lịch sử phiên bản/metadata. Ghi issues cho mã thiếu,
    lỗi mạng hoặc chưa xác minh phiên bản; không âm thầm bỏ bài. Không quét ngoài
    phạm vi. Không tìm bằng keyword tùy ý thay cho phạm vi được giao.
    elapsed_seconds gồm chờ/retry. scope_complete=False khi còn mã chưa xác minh.
    Raises ValueError nếu cấu hình sai; lỗi mạng được phản ánh trong result.
    Không ghi file và không gọi download/references.
    """
    start_time = time.perf_counter()

    unique_ids = _expand_scope(scope)
    requested_count = len(unique_ids)

    papers: list[PaperRecord] = []
    issues: list[DiscoveryIssue] = []

    for arxiv_id in unique_ids:
        try:
            record = fetch_paper(arxiv_id, policy=policy)
            papers.append(record)
        except LookupError as exc:
            issues.append({
                "arxiv_id": arxiv_id,
                "status": "not_found",
                "error": str(exc),
            })
        except Exception as exc:
            issues.append({
                "arxiv_id": arxiv_id,
                "status": "failed",
                "error": str(exc),
            })

    elapsed_seconds = round(time.perf_counter() - start_time, 4)

    has_failed = any(issue["status"] == "failed" for issue in issues)
    scope_complete = not has_failed

    if scope_complete and len(issues) == 0:
        status: Literal["success", "partial", "failed"] = "success"
    elif len(papers) == 0 and all(issue["status"] == "failed" for issue in issues) and requested_count > 0:
        status = "failed"
    else:
        status = "partial"

    return {
        "status": status,
        "scope": scope,
        "requested_count": requested_count,
        "scope_complete": scope_complete,
        "papers": papers,
        "issues": issues,
        "elapsed_seconds": elapsed_seconds,
    }


def fetch_paper(arxiv_id: str, *, policy: HttpPolicy) -> PaperRecord:
    """Input: ID gốc hợp lệ; output: PaperRecord có metadata và mọi versions.

    Cách làm: API id_list=arxiv_id lấy bản mới nhất; đọc title, author/name,
    published và arxiv:journal_ref từ Atom. API không trả một danh sách lịch sử
    đầy đủ trong một entry: xác định latest vN nếu phản hồi thể hiện rõ; khi
    chưa có N đáng tin cậy, bổ sung xác minh lịch sử trên trang abstract.
    Truy vấn id_list có hậu tố v1..vN theo batch để xác minh từng phiên bản,
    thu ngày cập nhật từng bản sửa; không lấy một updated mới nhất làm cả lịch sử.
    Kiểm tra ID/version phản hồi đúng yêu cầu; chưa xác minh đủ thì báo lỗi,
    không tự chốt [1]. Chuẩn hóa ngày
    UTC về YYYY-MM-DD, giữ tên tác giả và mã cũ; venue=None nếu không có.
    Không có bài: LookupError; mạng/API: RuntimeError; dữ liệu thiếu/sai:
    ValueError. discover_papers bắt các lỗi này để ghi DiscoveryIssue.
    Không tự điền metadata giả để trả PaperRecord trông như hoàn chỉnh.
    """
    base_id, _ = _clean_arxiv_id(arxiv_id)
    if not base_id:
        raise ValueError("arxiv_id must be a non-empty string")

    # Step 1: Query API for base ID
    resp = _http_request_with_policy(ARXIV_API_URL, {"id_list": base_id}, policy, allow_400=True)
    root = ET.fromstring(resp.text)
    entries = root.findall(f"{ATOM_NS}entry")
    if not entries:
        raise LookupError(f"Paper '{base_id}' not found on arXiv (0 entries returned).")

    _, entry_version, meta = _parse_atom_entry(entries[0])

    latest_v = entry_version
    abs_history: dict[int, str] | None = None
    if latest_v is None:
        abs_history = _get_submission_history_from_abstract(base_id, policy)
        if not abs_history:
            raise ValueError(f"Could not determine versions for {base_id}")
        latest_v = max(abs_history.keys())

    if latest_v < 1:
        raise ValueError(f"Invalid latest version {latest_v} for paper {base_id}")

    if latest_v == 1:
        versions = [1]
        submission_date = meta["published"]
        revised_dates: list[str] = []
    else:
        # Step 2: Query all versions v1..vN in a batch to verify and collect dates
        ver_ids = [f"{base_id}v{v}" for v in range(1, latest_v + 1)]
        expected_versions = list(range(1, latest_v + 1))
        version_data: dict[int, dict[str, Any]] = {}

        try:
            ver_resp = _http_request_with_policy(
                ARXIV_API_URL,
                {"id_list": ",".join(ver_ids), "start": 0, "max_results": len(ver_ids)},
                policy,
            )
            ver_root = ET.fromstring(ver_resp.text)
            ver_entries = ver_root.findall(f"{ATOM_NS}entry")
            for ve in ver_entries:
                try:
                    _, v_num, v_meta = _parse_atom_entry(ve)
                    if v_num is not None:
                        version_data[v_num] = v_meta
                except LookupError:
                    continue
        except Exception:
            pass

        # Supplement missing version dates from abstract page submission history
        if not all(v in version_data for v in expected_versions):
            if abs_history is None:
                abs_history = _get_submission_history_from_abstract(base_id, policy)
            for v in expected_versions:
                if v not in version_data and v in abs_history and abs_history[v]:
                    version_data[v] = {
                        "published": abs_history[1] if 1 in abs_history else meta["published"],
                        "updated": abs_history[v],
                    }

        for v in expected_versions:
            if v not in version_data:
                raise ValueError(
                    f"Version verification incomplete for {base_id}: version v{v} not found."
                )

        versions = expected_versions
        submission_date = version_data[1]["published"]
        revised_dates = [version_data[v]["updated"] for v in range(2, latest_v + 1)]

    paper_metadata: PaperMetadata = {
        "arxiv_id": base_id,
        "title": meta["title"],
        "authors": meta["authors"],
        "submission_date": submission_date,
        "revised_dates": revised_dates,
        "venue": meta["venue"],
    }
    return {
        "arxiv_id": base_id,
        "versions": versions,
        "metadata": paper_metadata,
    }


def _fetch_submission_dates_batch(
    batch: list[str], policy: HttpPolicy
) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch dates in a batch; split only HTTP 400 to isolate invalid IDs."""
    found_dates: dict[str, str] = {}
    errors: dict[str, str] = {}

    try:
        resp = _http_request_with_policy(
            ARXIV_API_URL,
            {"id_list": ",".join(batch), "start": 0, "max_results": len(batch)},
            policy,
            allow_400=True,
        )
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for entry in root.findall(f"{ATOM_NS}entry"):
                id_elem = entry.find(f"{ATOM_NS}id")
                raw_entry_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                title_elem = entry.find(f"{ATOM_NS}title")
                title_text = " ".join(title_elem.text.split()) if title_elem is not None and title_elem.text else ""
                if "errors#" in raw_entry_id or title_text == "Error":
                    continue
                b_id, _ = _clean_arxiv_id(raw_entry_id)
                pub_elem = entry.find(f"{ATOM_NS}published")
                if pub_elem is not None and pub_elem.text:
                    found_dates[b_id] = _format_utc_date(pub_elem.text)

            missing = [x for x in batch if x not in found_dates]
            for m in missing:
                errors[m] = "Paper ID not found in arXiv API response"
            return found_dates, errors
        elif resp.status_code == 400 and len(batch) > 1:
            for single_id in batch:
                s_dates, s_errs = _fetch_submission_dates_batch([single_id], policy)
                found_dates.update(s_dates)
                errors.update(s_errs)
            return found_dates, errors
        elif resp.status_code == 400 and len(batch) == 1:
            errors[batch[0]] = f"arXiv API error: malformed or invalid ID '{batch[0]}'"
            return found_dates, errors
    except Exception as exc:
        # Requests already exhausted the bounded retry policy. Splitting a
        # throttled/timed-out batch into N requests amplifies load on the same
        # service. Preserve missing dates and let a later resume retry them.
        for identifier in batch:
            if identifier not in found_dates:
                errors[identifier] = f"Lookup request failed: {exc}"
        return found_dates, errors

    return found_dates, errors


def fetch_submission_dates(ids: list[str], *, policy: HttpPolicy) -> DateLookupResult:
    """Input: ID gốc có thể trùng; output: dates chứa mọi ID duy nhất input.

    Cách làm: API id_list ghép các mã bằng dấu phẩy, chia batch/phân trang;
    đọc entry/published của bài, không đọc feed/updated. Đọc ngày published lần
    đầu, không dùng updated. Missing=None và errors[id] giải thích; không làm
    mất các ID đã lấy được khi một batch lỗi. ids=[] -> dates={}, errors={}.
    Dùng lại pacing arXiv; pipeline chạy tuần tự để tránh hai module gọi dồn.
    Nguyên nhận hàm đã gắn policy qua functools.partial làm DateLookup.
    """
    if not ids:
        return {"dates": {}, "errors": {}}

    unique_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in ids:
        clean, _ = _clean_arxiv_id(raw_id)
        if clean and clean not in seen:
            seen.add(clean)
            unique_ids.append(clean)

    dates: dict[str, str | None] = {}
    errors: dict[str, str] = {}

    batch_size = 50
    for i in range(0, len(unique_ids), batch_size):
        batch = unique_ids[i : i + batch_size]
        f_dates, f_errs = _fetch_submission_dates_batch(batch, policy)
        for b_id in batch:
            if b_id in f_dates:
                dates[b_id] = f_dates[b_id]
            else:
                dates[b_id] = None
                errors[b_id] = f_errs.get(b_id, "Date lookup failed")

    return {"dates": dates, "errors": errors}
