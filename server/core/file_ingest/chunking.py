from dataclasses import dataclass
import re

try:
    from llm.agen_matchbox.estimate_tokens import estimate_tokens
except ImportError:
    try:
        from server.llm.agen_matchbox.estimate_tokens import estimate_tokens
    except ImportError:
        def estimate_tokens(text, model=None):
            return len(text)


@dataclass(slots=True)
class TokenChunk:
    text: str
    index: int
    total: int
    char_count: int
    estimated_tokens: int
    previous_tail: str = ""


class TokenTextSplitter:
    SENTENCE_ENDINGS = re.compile(r'[。！？.!?]["\'」』）\)]*')
    PARAGRAPH_BOUNDARY = re.compile(r'\n\s*\n+')
    HEADING_BOUNDARY = re.compile(
        r'(?m)^(?:\s*(?:第\s*[0-9零〇一二三四五六七八九十百千万两]+\s*[章节卷部篇回集]|chapter\s+\d+|prologue|epilogue|序章|终章|番外|楔子|后记)[^\n]*|\s{0,3}#{1,6}\s+[^\n]+)$',
        re.IGNORECASE,
    )
    TAIL_CHARS = 100

    def __init__(
        self,
        chunk_tokens: int = 30000,
        min_tokens: int = 1000,
        max_tokens: int = 120000,
        tail_merge_threshold_ratio: float = 0.2,
        tail_merge_cap_ratio: float = 1.15,
        estimate_model: str | None = None,
    ):
        """Token 驱动的文本分块器。

        尾部合并策略：当切出的最后一片 < ``chunk_tokens * tail_merge_threshold_ratio``
        且与倍数第二片合并后仍 <= ``chunk_tokens * tail_merge_cap_ratio`` 时，
        合并二者，避免产生“小尾巴”分片。

        默认 0.2 / 1.15 保持保守，适用于风格分析以及 low-context 模型。
        聊天附件场景可传 0.5 / 1.5，避免“64.1K 切成 64K + 0.1K” 这类尴尬。
        """
        self.chunk_tokens = max(min_tokens, min(chunk_tokens, max_tokens))
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.tail_merge_threshold_ratio = max(0.0, min(float(tail_merge_threshold_ratio), 0.95))
        self.tail_merge_cap_ratio = max(1.0, float(tail_merge_cap_ratio))
        normalized_model = str(estimate_model).strip() if estimate_model is not None else ""
        self.estimate_model = normalized_model or None

    def estimate(self, text: str) -> int:
        return estimate_tokens(text, model=self.estimate_model)

    def split(self, text: str) -> list[TokenChunk]:
        normalized = self._normalize_text(text)
        if not normalized:
            return []

        # 估算口径必须全程一致：total 走 pack 路径（逐 unit 累加），不走整体
        # 一次性估算。否则整体估算与 pack 累加出现模型相关的系统性偏差时，
        # 会出现“total 说只有 1 片、pack 却装了 2 片 81K”的超窗单片
        # （见 longread 七堇年 e2e：qwen 口径整体 77K、pack 累加 136K）。
        units = self._build_units(normalized)
        if not units:
            return []
        raw_chunks = self._pack_units(units)
        return self._build_chunks(raw_chunks or [normalized])

    def split_with_info(self, text: str) -> tuple[list[TokenChunk], dict]:
        chunks = self.split(text)
        # total 取各片累加（pack 口径），不取整体一次性估算：两者在部分
        # tokenizer 下存在系统性偏差，累加口径才是各窗口真实成本之和。
        return chunks, {
            "total_chars": len(text or ""),
            "total_tokens_estimated": sum(
                chunk.estimated_tokens for chunk in chunks
            ) if chunks else 0,
            "chunk_count": len(chunks),
            "chunk_tokens_target": self.chunk_tokens,
            "chunks_info": [
                {
                    "index": chunk.index,
                    "chars": chunk.char_count,
                    "tokens_est": chunk.estimated_tokens,
                }
                for chunk in chunks
            ],
        }

    def _normalize_text(self, text: str) -> str:
        return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()

    def _build_units(self, text: str) -> list[str]:
        heading_parts = self._split_keep_markers(text, self.HEADING_BOUNDARY)
        units: list[str] = []
        for heading_part in heading_parts:
            paragraph_parts = self._split_keep_markers(heading_part, self.PARAGRAPH_BOUNDARY)
            for paragraph_part in paragraph_parts:
                paragraph_part = paragraph_part.strip()
                if not paragraph_part:
                    continue
                units.extend(self._split_sentence_units(paragraph_part))
        return [unit for unit in units if unit.strip()]

    # "\n\n" 连接符在常见 tokenizer 下估算为 1 个 token，用固定常数避免重复编码
    _JOIN_TOKENS = 1

    def _pack_units(self, units: list[str]) -> list[str]:
        if not units:
            return []

        chunks: list[tuple[str, int]] = []
        current_parts: list[str] = []
        current_tokens = 0

        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            unit_tokens = self.estimate(unit)

            if current_parts:
                projected = current_tokens + self._JOIN_TOKENS + unit_tokens
                if projected > self.chunk_tokens:
                    chunks.append(("\n\n".join(current_parts).strip(), current_tokens))
                    if unit_tokens > self.chunk_tokens:
                        for sub in self._force_split_large_unit(unit):
                            sub_tokens = self.estimate(sub)
                            chunks.append((sub.strip(), sub_tokens))
                        current_parts = []
                        current_tokens = 0
                    else:
                        current_parts = [unit]
                        current_tokens = unit_tokens
                    continue
                current_parts.append(unit)
                current_tokens = projected
            else:
                if unit_tokens > self.chunk_tokens:
                    for sub in self._force_split_large_unit(unit):
                        sub_tokens = self.estimate(sub)
                        chunks.append((sub.strip(), sub_tokens))
                    continue
                current_parts = [unit]
                current_tokens = unit_tokens

        if current_parts:
            chunks.append(("\n\n".join(current_parts).strip(), current_tokens))

        # 尾部合并：若最后一块 < threshold_ratio 目标 tokens，且合并后不超过 cap_ratio，合回倒数第二块
        if len(chunks) > 1:
            tail_text, tail_tokens = chunks[-1]
            threshold = max(1, int(self.chunk_tokens * self.tail_merge_threshold_ratio))
            cap = int(self.chunk_tokens * self.tail_merge_cap_ratio)
            if tail_tokens < threshold:
                prev_text, prev_tokens = chunks[-2]
                merged_tokens = prev_tokens + self._JOIN_TOKENS + tail_tokens
                if merged_tokens <= cap:
                    chunks[-2] = (f"{prev_text}\n\n{tail_text}".strip(), merged_tokens)
                    chunks.pop()

        return [text for text, _tokens in chunks]

    def _build_chunks(self, raw_chunks: list[str]) -> list[TokenChunk]:
        total = len(raw_chunks)
        chunks: list[TokenChunk] = []
        for index, chunk_text in enumerate(raw_chunks):
            previous_tail = ""
            if index > 0:
                prev_text = raw_chunks[index - 1]
                previous_tail = prev_text[-self.TAIL_CHARS:] if len(prev_text) > self.TAIL_CHARS else prev_text
            chunks.append(
                TokenChunk(
                    text=chunk_text,
                    index=index,
                    total=total,
                    char_count=len(chunk_text),
                    estimated_tokens=self.estimate(chunk_text),
                    previous_tail=previous_tail,
                )
            )
        return chunks

    def _split_sentence_units(self, text: str) -> list[str]:
        boundaries = [match.end() for match in self.SENTENCE_ENDINGS.finditer(text)]
        if not boundaries:
            return [text]
        units: list[str] = []
        start = 0
        for boundary in boundaries:
            piece = text[start:boundary].strip()
            if piece:
                units.append(piece)
            start = boundary
        tail = text[start:].strip()
        if tail:
            units.append(tail)
        return units or [text]

    def _split_keep_markers(self, text: str, pattern: re.Pattern[str]) -> list[str]:
        matches = list(pattern.finditer(text))
        if not matches:
            return [text]
        parts: list[str] = []
        cursor = 0
        for match in matches:
            start = match.start()
            if start > cursor:
                segment = text[cursor:start].strip()
                if segment:
                    parts.append(segment)
            cursor = start
        tail = text[cursor:].strip()
        if tail:
            parts.append(tail)
        return parts or [text]

    def _force_split_large_unit(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) <= 1:
            return self._force_split_by_chars(text)

        # 与 _pack_units 同思路：按 line 做增量 token 累加，避免对越滚越长的 candidate 反复 estimate
        _JOIN = 1  # "\n" 的近似 token 开销
        chunks: list[tuple[str, int]] = []
        current_parts: list[str] = []
        current_tokens = 0

        for line in lines:
            line_tokens = self.estimate(line)

            if current_parts:
                projected = current_tokens + _JOIN + line_tokens
                if projected > self.chunk_tokens:
                    chunks.append(("\n".join(current_parts).strip(), current_tokens))
                    current_parts = [line]
                    current_tokens = line_tokens
                    continue
                current_parts.append(line)
                current_tokens = projected
            else:
                current_parts = [line]
                current_tokens = line_tokens

        if current_parts:
            chunks.append(("\n".join(current_parts).strip(), current_tokens))

        flattened: list[str] = []
        for chunk_text, chunk_tokens in chunks:
            if chunk_tokens > self.chunk_tokens:
                flattened.extend(self._force_split_by_chars(chunk_text))
            else:
                flattened.append(chunk_text)
        return flattened

    def _force_split_by_chars(self, text: str) -> list[str]:
        approx_size = max(2000, int(len(text) * (self.chunk_tokens / max(self.estimate(text), 1))))
        parts: list[str] = []
        start = 0
        length = len(text)
        while start < length:
            end = min(length, start + approx_size)
            piece = text[start:end].strip()
            if piece:
                parts.append(piece)
            start = end
        return parts


def split_text_by_tokens(
    text: str,
    chunk_tokens: int = 30000,
    tail_merge_threshold_ratio: float = 0.2,
    tail_merge_cap_ratio: float = 1.15,
    estimate_model: str | None = None,
) -> list[TokenChunk]:
    return TokenTextSplitter(
        chunk_tokens=chunk_tokens,
        tail_merge_threshold_ratio=tail_merge_threshold_ratio,
        tail_merge_cap_ratio=tail_merge_cap_ratio,
        estimate_model=estimate_model,
    ).split(text)
