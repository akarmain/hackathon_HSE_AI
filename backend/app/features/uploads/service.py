import re
from pathlib import Path
import mimetypes

from fastapi import HTTPException, UploadFile, status

from app.core.config import Settings
from app.features.uploads.schemas import DeleteUploadResponse, UploadedFileItem, UploadImageResponse

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}

_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
_UNDERSCORE_REPEAT_PATTERN = re.compile(r"_+")
_EXTENSION_PATTERN = re.compile(r"^\.[A-Za-z0-9_-]+$")


def sanitize_filename(filename: str) -> str:
    normalized = filename.replace("\\", "/")
    base_name = normalized.split("/")[-1]
    sanitized = _SANITIZE_PATTERN.sub("_", base_name)
    sanitized = _UNDERSCORE_REPEAT_PATTERN.sub("_", sanitized)

    if sanitized in {"", ".", ".."}:
        return "file"

    path = Path(sanitized)
    stem = path.stem.strip("._-")
    suffix = path.suffix if _EXTENSION_PATTERN.match(path.suffix) else ""

    if stem == "":
        stem = "file"
    return f"{stem}{suffix}"


class UploadsService:
    def __init__(self, settings: Settings) -> None:
        self._max_size_bytes = settings.uploads_max_size_mb * 1024 * 1024
        self._uploads_dir = Path(settings.uploads_dir)
        self._uploads_dir.mkdir(parents=True, exist_ok=True)

    def _build_unique_filename(self, filename: str) -> str:
        candidate = filename
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        index = 1

        while (self._uploads_dir / candidate).exists():
            candidate = f"{stem}-{index}{suffix}"
            index += 1
        return candidate

    def _resolve_existing_file(self, filename: str) -> Path:
        safe_name = sanitize_filename(filename)
        path = self._uploads_dir / safe_name
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
        return path

    async def save_image(self, file: UploadFile) -> UploadImageResponse:
        content_type = file.content_type or ""
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only png, jpeg, webp, gif images are allowed.",
            )

        original_name = file.filename or "file"
        safe_name = sanitize_filename(original_name)
        unique_name = self._build_unique_filename(safe_name)
        target_path = self._uploads_dir / unique_name

        size = 0
        try:
            with target_path.open("wb") as output:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self._max_size_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File is too large. Max size is {self._max_size_bytes} bytes.",
                        )
                    output.write(chunk)
        except HTTPException:
            target_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

        return UploadImageResponse(
            filename=unique_name,
            stored_path=str(Path("storage/uploads") / unique_name),
            content_type=content_type,
            size=size,
        )

    def list_uploaded_files(self) -> list[UploadedFileItem]:
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        files: list[UploadedFileItem] = []

        for path in sorted(self._uploads_dir.iterdir()):
            if path.name.startswith("."):
                continue
            if path.is_file():
                files.append(
                    UploadedFileItem(
                        filename=path.name,
                        stored_path=str(Path("storage/uploads") / path.name),
                    )
                )
        return files

    def get_file_for_preview(self, filename: str) -> tuple[Path, str]:
        path = self._resolve_existing_file(filename)
        content_type, _ = mimetypes.guess_type(path.name)
        return path, content_type or "application/octet-stream"

    def rename_uploaded_file(self, filename: str, new_filename: str) -> UploadedFileItem:
        source_path = self._resolve_existing_file(filename)
        target_sanitized = sanitize_filename(new_filename)
        if Path(target_sanitized).suffix == "":
            target_sanitized = f"{target_sanitized}{source_path.suffix}"
        target_name = self._build_unique_filename(target_sanitized)
        target_path = self._uploads_dir / target_name
        source_path.rename(target_path)
        return UploadedFileItem(
            filename=target_name,
            stored_path=str(Path("storage/uploads") / target_name),
        )

    def delete_uploaded_file(self, filename: str) -> DeleteUploadResponse:
        path = self._resolve_existing_file(filename)
        path.unlink()
        return DeleteUploadResponse(filename=path.name, deleted=True)
