"""
风格分析专用文本切分器

切分逻辑统一收口在 core.file_ingest.chunking.TokenTextSplitter，
本文件仅保留兼容旧调用点的重导出。
"""

from core.file_ingest.chunking import TokenChunk as TextChunk
from core.file_ingest.chunking import TokenTextSplitter as StyleTextSplitter
from core.file_ingest.chunking import split_text_by_tokens as split_text_for_style_analysis

