"""Локальное хранение исходных документов."""

from functools import partial
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import anyio

from app.domain.documents import AsyncFileReader, StoredDocument
from app.domain.exceptions import FileTooLargeError, InvalidDocumentError


class LocalDocumentStorage:
    """Файловое хранилище с атомарным завершением записи."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def save_pdf(
        self,
        source: AsyncFileReader,
        *,
        original_filename: str,
        content_type: str,
        max_size_bytes: int,
        chunk_size_bytes: int,
    ) -> StoredDocument:
        """Потоково проверить и сохранить PDF."""
        await anyio.to_thread.run_sync(partial(self.root.mkdir, parents=True, exist_ok=True))
        file_id = uuid4()
        stored_filename = f"{file_id}.pdf"
        final_path = self.root / stored_filename
        temporary_path = self.root / f".{file_id}.part"
        digest = sha256()
        size_bytes = 0
        first_chunk = True
        completed = False

        try:
            target = await anyio.open_file(temporary_path, "wb")
            async with target:
                while chunk := await source.read(chunk_size_bytes):
                    if first_chunk:
                        if not chunk.startswith(b"%PDF-"):
                            raise InvalidDocumentError(
                                "Файл не содержит корректную PDF-сигнатуру",
                                code="pdf_signature_invalid",
                            )
                        first_chunk = False
                    size_bytes += len(chunk)
                    if size_bytes > max_size_bytes:
                        raise FileTooLargeError(
                            "Размер PDF превышает допустимый предел",
                            code="file_too_large",
                        )
                    digest.update(chunk)
                    await target.write(chunk)

            if first_chunk:
                raise InvalidDocumentError("Загружен пустой файл", code="file_empty")

            await anyio.to_thread.run_sync(temporary_path.replace, final_path)
            completed = True
        finally:
            if not completed:
                await self._unlink(temporary_path)

        return StoredDocument(
            original_filename=original_filename,
            stored_filename=stored_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=digest.hexdigest(),
        )

    async def delete(self, stored_filename: str) -> None:
        """Безопасно удалить файл по внутреннему имени."""
        await self._unlink(self.resolve_path(stored_filename))

    def resolve_path(self, stored_filename: str) -> Path:
        """Вернуть путь, не допускающий выход за корень хранилища."""
        if Path(stored_filename).name != stored_filename:
            raise ValueError("Некорректное внутреннее имя файла")
        path = (self.root / stored_filename).resolve()
        if path.parent != self.root:
            raise ValueError("Некорректное внутреннее имя файла")
        return path

    @staticmethod
    async def _unlink(path: Path) -> None:
        await anyio.to_thread.run_sync(partial(path.unlink, missing_ok=True))
