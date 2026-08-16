"""Исключения, безопасные для отображения пользователю."""


class ApplicationError(Exception):
    """Ожидаемая ошибка сценария использования."""

    def __init__(self, message: str, *, code: str = "application_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code
