"""Integrated M2 parsing package. Importing the package does not run the pipeline.

Import types từ parsing.contracts; import API từ module owner cụ thể.
Keep owner modules lazy to avoid import cycles and unnecessary runtime dependencies.
"""
from .contracts import CONTRACT_VERSION, OUTPUT_SCHEMA_VERSION

__all__ = ["CONTRACT_VERSION", "OUTPUT_SCHEMA_VERSION"]
