"""Исключения, безопасные для отображения пользователю."""


class ApplicationError(Exception):
    """Ожидаемая ошибка сценария использования."""

    def __init__(self, message: str, *, code: str = "application_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InvalidDocumentError(ApplicationError):
    """Файл не соответствует требованиям к документу."""


class FileTooLargeError(ApplicationError):
    """Размер файла превышает допустимый предел."""


class DocumentNotFoundError(ApplicationError):
    """Документ с указанным идентификатором не найден."""


class DocumentProcessingError(ApplicationError):
    """Документ невозможно обработать."""


class DocumentTextMissingError(DocumentProcessingError):
    """В документе отсутствует извлекаемый текстовый слой."""
