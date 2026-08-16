"""Разбиение текста на фрагменты для последующего поиска."""

from collections.abc import Sequence

from app.domain.documents import ExtractedPage, TextChunk


class MeaningfulTextChunker:
    """Разбиение по границам абзацев, строк, предложений и слов."""

    _BREAK_MARKERS = (
        ("\n\n",),
        ("\n",),
        (". ", "! ", "? ", "… "),
        ("; ", ": "),
        (" ",),
    )

    def __init__(self, *, max_chars: int, overlap_chars: int) -> None:
        if max_chars <= 0:
            raise ValueError("Размер фрагмента должен быть положительным")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("Некорректное перекрытие фрагментов")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def split(self, pages: Sequence[ExtractedPage]) -> Sequence[TextChunk]:
        """Разбить страницы, никогда не объединяя текст разных страниц."""
        chunks: list[TextChunk] = []
        for page in pages:
            for char_start, char_end in self._split_page(page.text):
                chunks.append(
                    TextChunk(
                        page_number=page.page_number,
                        chunk_index=len(chunks),
                        text=page.text[char_start:char_end],
                        char_start=char_start,
                        char_end=char_end,
                    )
                )
        return chunks

    def _split_page(self, text: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        start = 0
        text_length = len(text)

        while start < text_length:
            hard_end = min(start + self.max_chars, text_length)
            raw_end = self._select_end(text, start, hard_end)
            char_start, char_end = self._trim_span(text, start, raw_end)
            if char_start < char_end:
                spans.append((char_start, char_end))
            if raw_end >= text_length:
                break

            next_start = max(raw_end - self.overlap_chars, start + 1)
            start = self._advance_to_word_boundary(text, next_start, raw_end)
            if start >= raw_end:
                start = raw_end

        return spans

    def _select_end(self, text: str, start: int, hard_end: int) -> int:
        if hard_end >= len(text):
            return hard_end
        search_start = start + max(1, int(self.max_chars * 0.55))
        if search_start >= hard_end:
            return hard_end

        for markers in self._BREAK_MARKERS:
            positions = [text.rfind(marker, search_start, hard_end) for marker in markers]
            best_position = max(positions)
            if best_position >= 0:
                marker = max(
                    (
                        item
                        for item in markers
                        if text.rfind(item, search_start, hard_end) == best_position
                    ),
                    key=len,
                )
                return best_position + len(marker)
        return hard_end

    @staticmethod
    def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    @staticmethod
    def _advance_to_word_boundary(text: str, start: int, limit: int) -> int:
        if start > 0 and start < limit and not text[start - 1].isspace():
            while start < limit and not text[start].isspace():
                start += 1
        while start < limit and text[start].isspace():
            start += 1
        return start
