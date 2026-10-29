"""PROTOTYPE — Khang / KG2.

Prototype và docstring thuật toán là hướng tham khảo, không giới hạn ở điền thân hàm.
Đọc contracts.py, phần việc owner và tiêu chí nghiệm thu; hoàn thiện đầy đủ task/đầu ra.
Nếu có phương án tốt hơn, so sánh lợi ích/đánh đổi, dependencies, ảnh hưởng API và cách kiểm chứng;
hỏi người phụ trách task chọn hướng trước khi làm phần phụ thuộc, tiếp tục việc độc lập trong lúc chờ.
Không hỏi lại lựa chọn đã chốt hoặc từng chi tiết nhỏ. Sau khi chốt có thể thêm/thay/tổ chức lại code.
Test độc lập dùng fixtures trong tests/m2_support/fixtures.py, không chờ module người khác.
Chỉ sửa phạm vi owner đang thống nhất; mở rộng phạm vi cần phối hợp owner bị ảnh hưởng.
Ưu tiên giữ nguyên schema, kiểu dữ liệu và API; không cần đổi mà vẫn hoàn thành tốt task thì càng tốt.
Không khuyến khích đổi; chỉ đổi khi thật sự cần thiết và hạn chế sửa phần chung để tránh conflict. Phối hợp Danh/owner bị ảnh hưởng và đồng bộ consumer, fixtures, tests, notebook, tài liệu.
Không giảm yêu cầu hay acceptance cases khi đổi thiết kế.
Tất cả hàm hiện cố ý chưa triển khai; không coi import thành công là parser chạy được.

Hướng hiệu năng đã chọn (kế hoạch 10.0; chưa triển khai):
Scanner tiến dần trên mỗi prose span; không gọi model/mạng và không chạy lại parser toàn bài cho từng sentence.
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

