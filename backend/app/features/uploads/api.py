from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.features.uploads.schemas import (
    DeleteUploadResponse,
    RenameUploadRequest,
    UploadImageResponse,
    UploadedFileItem,
    UploadListResponse,
)
from app.features.uploads.service import UploadsService

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

_service = UploadsService(settings=get_settings())


@router.post("/image", response_model=UploadImageResponse)
async def upload_image(file: UploadFile = File(...)) -> UploadImageResponse:
    return await _service.save_image(file)


@router.get("/list", response_model=UploadListResponse)
def list_uploads() -> UploadListResponse:
    return UploadListResponse(files=_service.list_uploaded_files())


@router.get("/image/{filename:path}")
def get_uploaded_image(filename: str) -> FileResponse:
    path, content_type = _service.get_file_for_preview(filename)
    return FileResponse(path=path, media_type=content_type, filename=path.name)


@router.patch("/rename", response_model=UploadedFileItem)
def rename_upload(payload: RenameUploadRequest) -> UploadedFileItem:
    return _service.rename_uploaded_file(
        filename=payload.filename,
        new_filename=payload.new_filename,
    )


@router.delete("/file/{filename:path}", response_model=DeleteUploadResponse)
def delete_upload(filename: str) -> DeleteUploadResponse:
    return _service.delete_uploaded_file(filename)
