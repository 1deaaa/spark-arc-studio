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

    def __init__(self, chunk_tokens: int = 30000, min_tokens: int = 1000, max_tokens: int = 120000):
        self.chunk_tokens = max(min_tokens, min(chunk_tokens, max_tokens))
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens

    def estimate(self, text: str) -> int:
        return estimate_tokens(text, model=None)

    def split(self, text: str) -> list[TokenChunk]:
        normalized = self._normalize_text(text)
        if not normalized:
            return []

        total_tokens = self.estimate(normalized)
        if total_tokens <= self.chunk_tokens:
            return [
                TokenChunk(
                    text=normalized,
                    index=0,
                    total=1,
                    char_count=len(normalized),
                    estimated_tokens=total_tokens,
                    previous_tail="",
                )
            ]

        units = self._build_units(normalized)
        raw_chunks = self._pack_units(units)
        return self._build_chunks(raw_chunks)

    def split_with_info(self, text: str) -> tuple[list[TokenChunk], dict]:
        chunks = self.split(text)
        return chunks, {
            "total_chars": len(text or ""),
            "total_tokens_estimated": self.estimate(self._normalize_text(text)),
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

    def _pack_units(self, units: list[str]) -> list[str]:
        if not units:
            return []

        chunks: list[str] = []
        current = ""
        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            candidate = f"{current}\n\n{unit}".strip() if current else unit
            if current and self.estimate(candidate) > self.chunk_tokens:
                chunks.append(current.strip())
                if self.estimate(unit) > self.chunk_tokens:
                    chunks.extend(self._force_split_large_unit(unit))
                    current = ""
                else:
                    current = unit
                continue
            current = candidate

        if current.strip():
            chunks.append(current.strip())

        if len(chunks) > 1:
            tail = chunks[-1]
            if self.estimate(tail) < max(1, int(self.chunk_tokens * 0.2)):
                merged = f"{chunks[-2]}\n\n{tail}".strip()
                if self.estimate(merged) <= int(self.chunk_tokens * 1.15):
                    chunks[-2] = merged
                    chunks.pop()

        return chunks

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

        chunks: list[str] = []
        current = ""
        for line in lines:
            candidate = f"{current}\n{line}".strip() if current else line
            if current and self.estimate(candidate) > self.chunk_tokens:
                chunks.append(current.strip())
                current = line
            else:
                current = candidate
        if current.strip():
            chunks.append(current.strip())

        flattened: list[str] = []
        for chunk in chunks:
            if self.estimate(chunk) > self.chunk_tokens:
                flattened.extend(self._force_split_by_chars(chunk))
            else:
                flattened.append(chunk)
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


def split_text_by_tokens(text: str, chunk_tokens: int = 30000) -> list[TokenChunk]:
    return TokenTextSplitter(chunk_tokens=chunk_tokens).split(text)
