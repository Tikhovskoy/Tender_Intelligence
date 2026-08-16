import pytest
from pydantic import ValidationError

from app.config import Settings


def test_log_level_is_normalized() -> None:
    settings = Settings(log_level="warning")

    assert settings.log_level == "WARNING"


def test_unknown_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Недопустимый уровень"):
        Settings(log_level="verbose")
