from fastapi import APIRouter

from app.core.config import get_settings
from app.features.genai.schemas import (
    GenAIImageRequest,
    GenAIImageResponse,
    GenAITextRequest,
    GenAITextResponse,
)
from app.features.genai.service import GenAIService

router = APIRouter(prefix="/api/genai", tags=["genai"])

_service = GenAIService(settings=get_settings())


@router.post("/text", response_model=GenAITextResponse)
def genai_text(payload: GenAITextRequest) -> GenAITextResponse:
    return _service.ask_text(payload)


@router.post("/image", response_model=GenAIImageResponse)
def genai_image(payload: GenAIImageRequest) -> GenAIImageResponse:
    return _service.generate_image(payload)
