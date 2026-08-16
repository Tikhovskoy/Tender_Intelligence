from itertools import pairwise

import pytest

from app.application.text_chunking import MeaningfulTextChunker
from app.domain.documents import ExtractedPage


def test_short_page_becomes_one_trimmed_chunk() -> None:
    page = ExtractedPage(page_number=3, text="  Ключевые требования к исполнителю.  ")

    chunks = MeaningfulTextChunker(max_chars=100, overlap_chars=20).split([page])

    assert len(chunks) == 1
    assert chunks[0].page_number == 3
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "Ключевые требования к исполнителю."
    assert page.text[chunks[0].char_start : chunks[0].char_end] == chunks[0].text


def test_paragraph_boundary_has_priority() -> None:
    first_paragraph = "А" * 70
    second_paragraph = "Б" * 70
    page = ExtractedPage(
        page_number=1,
        text=f"{first_paragraph}\n\n{second_paragraph}",
    )

    chunks = MeaningfulTextChunker(max_chars=100, overlap_chars=15).split([page])

    assert chunks[0].text == first_paragraph
    assert chunks[0].char_end == 70
    assert chunks[1].text == second_paragraph


def test_long_text_uses_overlap_and_exact_offsets() -> None:
    text = " ".join(f"условие-{index:02d}" for index in range(30))
    page = ExtractedPage(page_number=1, text=text)

    chunks = MeaningfulTextChunker(max_chars=90, overlap_chars=25).split([page])

    assert len(chunks) > 2
    assert all(len(chunk.text) <= 90 for chunk in chunks)
    assert all(text[chunk.char_start : chunk.char_end] == chunk.text for chunk in chunks)
    assert any(current.char_start < previous.char_end for previous, current in pairwise(chunks))


def test_chunks_never_cross_page_boundaries() -> None:
    pages = [
        ExtractedPage(page_number=2, text="Текст второй страницы"),
        ExtractedPage(page_number=5, text="Текст пятой страницы"),
        ExtractedPage(page_number=6, text="   "),
    ]

    chunks = MeaningfulTextChunker(max_chars=100, overlap_chars=10).split(pages)

    assert [chunk.page_number for chunk in chunks] == [2, 5]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1]


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars"),
    [(0, 0), (100, -1), (100, 100), (100, 101)],
)
def test_invalid_chunk_settings_are_rejected(max_chars: int, overlap_chars: int) -> None:
    with pytest.raises(ValueError):
        MeaningfulTextChunker(max_chars=max_chars, overlap_chars=overlap_chars)
