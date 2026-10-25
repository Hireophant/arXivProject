"""Shared retry decisions and compact diagnostics; no network or UI dependencies.

Permanent means excluded from automatic retries, not proof an upstream resource
can never appear later. Preserve the evidence for a deliberate future review.
"""
import re


def classify_failure(task, status, error=None):
    """Conservative classification, including diagnostics from legacy manifests."""
    text = str(error or '')
    http = re.search(r'\bHTTP\s+(\d{3})\b', text, re.I)
    code = int(http[1]) if http else None
    service = 'S2' if task == 'references' else 'Source' if task.startswith('source') else 'OAI'
    if status == 'no_tex':
        return 'permanent', 'no_tex', 'Nguồn đã xác minh không có TeX'
    if status == 'not_found' and service == 'OAI':
        return 'permanent', 'oai_not_found', 'OAI: không có bản ghi cho ID'
    if status == 'not_found' or (code in (404, 410) and service != 'OAI'):
        label = f'{service} HTTP {code or 404}'
        # A source 404 alone does not establish that the author submitted PDF only.
        return 'permanent', f'{service.lower()}_{code or 404}', label + ' (không tìm thấy)'
    if re.search(r'\binvalid (?:base )?arxiv id\b|\binvalid identifier\b', text, re.I):
        return 'permanent', 'invalid_id', 'ID không hợp lệ'
    if status == 'pending':
        return 'pending', 'pending', 'Chưa xử lý'
    if code == 429:
        return 'transient', f'{service.lower()}_429', f'{service} HTTP 429 (giới hạn API)'
    if code == 408 or (code is not None and 500 <= code <= 599):
        return 'transient', f'{service.lower()}_{code}', f'{service} HTTP {code} (tạm thời)'
    if code is not None:
        return 'review', f'{service.lower()}_{code}', f'{service} HTTP {code} (cần kiểm tra)'
    if re.search(r'timeout|timed out|transport|connection|request failed|network', text, re.I):
        return 'transient', 'transport', f'{service}: mạng / timeout'
    return 'review', 'other', f'{service}: {status} (cần kiểm tra)'


def failure_rows(manifest):
    rows = []
    def add(identifier, task, result):
        status = result['status'] if result else 'pending'
        if status == 'success':
            return
        error = result.get('error') if result else None
        category, code, label = classify_failure(task, status, error)
        rows.append(dict(arxiv_id=identifier, task=task, status=status, category=category,
                         code=code, reason=label, error=error))
    for issue in (manifest.get('discovery') or {}).get('issues', []):
        add(issue['arxiv_id'], 'discovery', issue)
    for identifier, paper in manifest['papers'].items():
        for version in paper['record']['versions']:
            add(identifier, f'source v{version}', paper['downloads'].get(str(version)))
        add(identifier, 'references', paper.get('references'))
    return rows


def quarantined_ids(manifest, invalid_ids=()):
    """Quarantine only when every unresolved task is permanent.

    no_tex is a verified, resolved source outcome. A mixed 404/429 paper stays
    pending so its recoverable task can finish, reusing the permanent decision.
    An integrity failure must always stay pending for repair.
    """
    unresolved = {}
    invalid = set(invalid_ids)
    for row in failure_rows(manifest):
        if row['status'] != 'no_tex':
            unresolved.setdefault(row['arxiv_id'], []).append(row)
    return {i for i, rows in unresolved.items() if i not in invalid
            and all(r['category'] == 'permanent' for r in rows)}


def permanent_tasks(manifest):
    """Failed task results safe to reuse without a request; no_tex uses receipts."""
    result = {}
    for identifier, paper in manifest['papers'].items():
        downloads = {v: d for v, d in paper['downloads'].items()
                     if d and d['status'] == 'failed'
                     and classify_failure('source', d['status'], d.get('error'))[0] == 'permanent'}
        refs = paper.get('references')
        if not refs or refs['status'] == 'success' or classify_failure('references', refs['status'], refs.get('error'))[0] != 'permanent':
            refs = None
        if downloads or refs:
            result[identifier] = dict(downloads=downloads, references=refs)
    return result
