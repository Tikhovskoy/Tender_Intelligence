import pytest
from pydantic import ValidationError

from app.config import Settings


def test_log_level_is_normalized() -> None:
    settings = Settings(log_level="warning")

    assert settings.log_level == "WARNING"


def test_unknown_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Недопустимый уровень"):
        Settings(log_level="verbose")


def test_chunk_overlap_must_be_smaller_than_chunk() -> None:
    with pytest.raises(ValidationError, match="Перекрытие фрагментов"):
        Settings(text_chunk_size_chars=300, text_chunk_overlap_chars=300)
