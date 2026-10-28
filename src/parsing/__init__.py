"""Khung M2 chưa triển khai nghiệp vụ. Import package không chạy pipeline.

Import types từ parsing.contracts; import API từ module owner cụ thể.
Không import eager các module owner ở đây để mỗi người làm độc lập.
"""
from .contracts import CONTRACT_VERSION, OUTPUT_SCHEMA_VERSION

__all__ = ["CONTRACT_VERSION", "OUTPUT_SCHEMA_VERSION"]
