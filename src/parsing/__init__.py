"""Khung M2 chưa triển khai nghiệp vụ. Import package không chạy pipeline.

Prototype/docstring thuật toán là tham khảo; xem quy tắc chọn hướng trong phân công M2 mục 14–15.
Có hướng tốt hơn thì trao đổi người phụ trách trước; vẫn hoàn thiện đủ task và nghiệm thu.
Import types từ parsing.contracts; import API từ module owner cụ thể.
Không import eager các module owner ở đây để mỗi người làm độc lập.
"""
from .contracts import CONTRACT_VERSION, OUTPUT_SCHEMA_VERSION

__all__ = ["CONTRACT_VERSION", "OUTPUT_SCHEMA_VERSION"]
