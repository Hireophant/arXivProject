"""Small, bounded notebook views; raw exported measurements remain numeric."""
from html import escape
from pathlib import Path, PurePosixPath
import re
import zipfile

from .backup import _sha256
from .failures import quarantined_ids
from .sessions import successful_ids, scope_ids, _read, locate_receipt, _receipt


def format_bytes(value):
    if value is None:
        return '—'
    unit, divisor = ('GiB', 1024**3) if value >= 1024**3 else ('MiB', 1024**2)
    return f'{value / divisor:,.1f} {unit}'


def format_duration(value):
    if value is None:
        return '—'
    if 0 < value < 1:
        return f'{value:.2f} s'
    minutes, seconds = divmod(round(value), 60)
    return f'{minutes:02d}:{seconds:02d}'


def compact_text(value, limit=100):
    """Legacy URL-heavy diagnostics stay in CSV; omit URLs from HTML previews."""
    text = re.sub(r'https?://\S+', '[URL]', str(value))
    return text if len(text) <= limit else text[:limit - 1] + '…'


def preview_table(frame, limit=5):
    """Format a COPY, keeping full data and numeric dtypes for figures/exports."""
    preview = frame.head(limit).copy()
    for column in preview.columns:
        if 'bytes' in column:
            preview[column] = preview[column].map(lambda x: '—' if x != x or x is None else format_bytes(x))
        elif column.endswith('_seconds'):
            preview[column] = preview[column].map(lambda x: '—' if x != x or x is None else format_duration(x))
        else:
            preview[column] = preview[column].map(lambda x: compact_text(x) if isinstance(x, str) else x)
    return preview


def preview_style(frame, limit=5):
    return (preview_table(frame, limit).style.format(na_rep='—', precision=1, escape='html')
            .set_table_attributes('style="display:block;max-width:100%;overflow-x:auto"')
            .set_properties(**{'max-width': '240px', 'overflow-wrap': 'anywhere', 'white-space': 'normal'}))


def export_issue_groups(issues, path):
    """Export every diagnostic group; callers can render the whole small table."""
    groups = (issues.groupby(['category', 'reason'], dropna=False)
              .agg(papers=('arxiv_id', 'nunique'), tasks=('task', 'size')).reset_index())
    groups.to_csv(path, index=False)
    return groups


def _drive_receipts(state_path, member, run_id, extra_receipt=None):
    paths = set()
    if state_path is not None:
        state = _read(Path(state_path), member)
        paths.update(b['receipt_path'] for b in state['backups'] if b['run_id'] == run_id)
    if extra_receipt:
        paths.add(extra_receipt)
    seen = set()
    for value in paths:
        allowed = Path(state_path).resolve().parent.parent if state_path else Path(value).resolve().parent
        receipt_file = locate_receipt(value, allowed)
        if receipt_file in seen:
            continue
        seen.add(receipt_file)
        receipt = _receipt(receipt_file, allowed)
        if receipt['run_id'] != run_id:
            raise ValueError('Drive backup belongs to a different run.')
        yield receipt_file, receipt


def verified_drive_bytes(state_path, member, run_id, extra_receipt=None):
    """Physical ZIP/receipt bytes for this run, including duplicate backups.

    Transport hashes were checked before ledger commit; check sizes here.
    """
    total = None
    for receipt_file, receipt in _drive_receipts(state_path, member, run_id, extra_receipt):
        total = total or 0
        total += receipt_file.stat().st_size
        for entry in receipt['archives'].values():
            size = (receipt_file.parent / entry['filename']).stat().st_size
            if size != entry['bytes']:
                raise OSError('Verified Drive backup size changed.')
            total += size
    return total


def verified_drive_source_files(state_path, member, run_id, extra_receipt=None):
    """Count unique source paths in hash-verified corpus ZIPs, never local files.

    Checkpoints/full backups may overlap; manifest-only report stubs add no files.
    None means no committed backup; zero means verified backups contain no source.
    """
    files = set()
    found = False
    for receipt_file, receipt in _drive_receipts(state_path, member, run_id, extra_receipt):
        entry = receipt['archives']['corpus']
        archive = receipt_file.parent / entry['filename']
        if archive.stat().st_size != entry['bytes'] or _sha256(archive) != entry['sha256']:
            raise OSError('Drive corpus ZIP failed verification.')
        with zipfile.ZipFile(archive) as zipped:
            for item in zipped.infolist():
                path = PurePosixPath(item.filename)
                if (not item.is_dir() and len(path.parts) >= 4
                        and path.parts[1] == 'sources' and re.fullmatch(r'v\d+', path.parts[2])
                        and path.suffix.lower() in {'.tex', '.bib'}):
                    files.add(path.as_posix())
        found = True
    return len(files) if found else None


def summary_dashboard(manifest, run_result, *, drive_bytes=None, invalid_ids=(),
                      drive_source_files=None, session_seconds=None, session_finished=False):
    total = len(scope_ids(manifest['scope']))
    completed = len(successful_ids(manifest, invalid_ids))
    quarantine = len(quarantined_ids(manifest, invalid_ids))
    files = sum((d.get('file_count') or 0) for p in manifest['papers'].values()
                for d in p['downloads'].values() if d and d['status'] == 'success')
    seconds = run_result['benchmark']['wall_seconds']
    cards = [
        ('Thời gian pipeline', f'{seconds / 60:.1f} phút ({format_duration(seconds)})'),
        ('Bài hoàn thành xử lý', f'{completed}/{total} ({completed / total:.1%})' if total else '0/0'),
        ('File .tex / .bib đã lưu local', f'{files:,}'),
        ('File .tex / .bib đã xác minh trên Drive',
         f'{drive_source_files:,}' if drive_source_files is not None else 'Chưa xác minh'),
        ('Drive: backup đã xác minh của phiên này', format_bytes(drive_bytes) if drive_bytes is not None else 'Chưa xác minh'),
        ('Bài còn cần retry / kiểm tra', str(total - completed - quarantine)),
        ('Bài cách ly, chưa hoàn thành', str(quarantine)),
    ]
    if session_seconds is not None:
        label = 'Tổng thời gian phiên đến backup Drive' if session_finished else 'Thời gian phiên đã trôi (chưa chốt backup)'
        cards.insert(0, (label, f'{session_seconds / 60:.1f} phút ({format_duration(session_seconds)})'))
    body = ''.join(f'<div style="padding:12px;border:1px solid #ccd5df;border-radius:8px">'
                   f'<span>{escape(label)}</span><br><strong>{escape(value)}</strong></div>' for label, value in cards)
    return ('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px">'
            + body + '</div><p>Phiên đang xem; hoàn thành xử lý gồm no_tex. '
            'File local theo pipeline; file Drive theo ZIP đã kiểm hash, không cộng trùng. '
            'Dung lượng Drive gồm ZIP/receipt của phiên, kể cả backup trùng. '
            'Pipeline không gồm báo cáo/backup cuối; tổng phiên gồm chuẩn bị, khôi phục, báo cáo, '
            'backup, xác minh và cập nhật queue, kể cả thời gian chờ giữa các cell; không gồm setup.</p>')
