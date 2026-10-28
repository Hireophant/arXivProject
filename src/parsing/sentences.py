"""PROTOTYPE — Khang / KG2.

Chỉ triển khai file owner; đọc types/docstrings trong contracts.py và hướng dẫn từng hàm bên dưới.
Test độc lập dùng fixtures dựng sẵn trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa module/tests của mình; dependencies/shared schema để Danh ghép một lần, tránh conflict.
Không thay public signatures/contracts; private helpers được tự thêm trong file này.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.
"""
from __future__ import annotations




def split_sentences(text: str) -> list[str]:
    """API chính độc lập, giữ nguyên text/math/commands; không cleanup ở đây.
    Dùng scanner có trạng thái math delimiters, balanced braces, commands, escaped symbols và verbatim.
    Bảo vệ i.e., e.g., et al., Fig. 1, URL/DOI, số thập phân và dấu chấm trong command arguments.
    Chỉ tách dấu kết câu ngoài vùng bảo vệ; giữ dấu kết câu; trim whitespace hai đầu mỗi câu.
    Đoạn cuối không có dấu chấm vẫn là sentence nếu có prose; whitespace-only -> [].
    Không bắt buộc dùng NLP/model; không gọi mạng. Ghi giới hạn ngôn ngữ/thư viện nếu bổ sung.
    Test S3 bằng bảng input/expected do người đọc tự viết, gồm hai câu thật xen math/abbreviation.
    Không split theo regex dấu chấm thuần hoặc xóa math rồi chắp lại.
    """
    raise NotImplementedError("M2 prototype: sentences.split_sentences — Khang / KG2")

