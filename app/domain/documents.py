"""Основные типы документов."""

from enum import StrEnum


class DocumentStatus(StrEnum):
    """Этап обработки загруженного документа."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
