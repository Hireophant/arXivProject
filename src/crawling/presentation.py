"""Small, bounded notebook views; raw exported measurements remain numeric."""
from html import escape
from pathlib import Path
import re

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


def verified_drive_bytes(state_path, member, run_id, extra_receipt=None):
    """Physical bytes of verified backup files for THIS run, including duplicates.

    Uses the committed ledger and actual file sizes; not local corpus size or
    Drive account quota. Hash verification already happened before ledger commit.
    Missing files fail visibly. A historical analysis should not call this unless
    its backup tree is actually mounted.
    """
    paths = set()
    if state_path is not None:
        state = _read(Path(state_path), member)
        paths.update(b['receipt_path'] for b in state['backups'] if b['run_id'] == run_id)
    if extra_receipt:
        paths.add(extra_receipt)
    if not paths:
        return None
    total = 0
    for value in paths:
        allowed = Path(state_path).resolve().parent.parent if state_path else Path(value).resolve().parent
        receipt_file = locate_receipt(value, allowed)
        receipt = _receipt(receipt_file, allowed)
        total += receipt_file.stat().st_size
        for entry in receipt['archives'].values():
            size = (receipt_file.parent / entry['filename']).stat().st_size
            if size != entry['bytes']:
                raise OSError('Verified Drive backup size changed.')
            total += size
    return total


def summary_dashboard(manifest, run_result, *, drive_bytes=None, invalid_ids=()):
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
        ('Drive: backup đã xác minh của phiên này', format_bytes(drive_bytes) if drive_bytes is not None else 'Chưa xác minh'),
        ('Bài còn cần retry / kiểm tra', str(total - completed - quarantine)),
        ('Bài cách ly, chưa hoàn thành', str(quarantine)),
    ]
    body = ''.join(f'<div style="padding:12px;border:1px solid #ccd5df;border-radius:8px">'
                   f'<span>{escape(label)}</span><br><strong>{escape(value)}</strong></div>' for label, value in cards)
    return ('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px">'
            + body + '</div><p>Phạm vi: phiên đang xem. Hoàn thành xử lý chấp nhận no_tex đã xác minh; '
            'không đồng nghĩa mọi bài có TeX. Số file local theo kết quả pipeline; xem integrity audit để xác nhận. '
            'Drive tính ZIP và receipt đã lưu, gồm các bản checkpoint trùng dữ liệu; không phải dung lượng toàn tài khoản. '
            'Thời gian trên gồm checkpoint trong pipeline, chưa gồm xuất báo cáo và backup cuối notebook.</p>')
