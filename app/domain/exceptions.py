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


class DocumentNotReadyError(ApplicationError):
    """Документ ещё не подготовлен для анализа."""


class AnalysisNotFoundError(ApplicationError):
    """Карточка документа ещё не сформирована."""


class ProviderUnavailableError(ApplicationError):
    """Внешний провайдер недоступен или не настроен."""


class InvalidProviderResponseError(ApplicationError):
    """Провайдер вернул ответ, не соответствующий контракту."""
