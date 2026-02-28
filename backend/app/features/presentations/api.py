from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.features.presentations.schemas import (
    CreatePresentationRequest,
    CreatePresentationResponse,
    PresentationPromptTestRequest,
    PresentationPromptTestResponse,
    PresentationStatusResponse,
)
from app.features.presentations.service import PresentationService

router = APIRouter(prefix="/api/presentations", tags=["presentations"])

_service = PresentationService(settings=get_settings())


@router.post("", response_model=CreatePresentationResponse)
def create_presentation(payload: CreatePresentationRequest) -> CreatePresentationResponse:
    return _service.create_presentation(payload)


@router.get("/{presentation_id}/status", response_model=PresentationStatusResponse)
def get_presentation_status(presentation_id: str) -> PresentationStatusResponse:
    return _service.get_status(presentation_id)


@router.post("/test", response_model=PresentationPromptTestResponse)
def test_presentation_prompt(payload: PresentationPromptTestRequest) -> PresentationPromptTestResponse:
    return _service.test_prompt(payload)


@router.get("/{presentation_id}/slides/{filename:path}")
def get_presentation_slide(presentation_id: str, filename: str) -> FileResponse:
    path = _service.get_slide_file_path(presentation_id, filename)
    return FileResponse(path=path, media_type="image/png", filename=path.name)


@router.get("/{presentation_id}/download")
def download_presentation(presentation_id: str) -> FileResponse:
    path = _service.get_download_file_path(presentation_id)
    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "application/zip"
    return FileResponse(path=path, media_type=media_type, filename=path.name)
