from pathlib import Path
from time import time

from fastapi import HTTPException, status

from app.core.config import Settings
from app.features.genai.client import GenAPIClient
from app.features.genai.schemas import (
    GenAIImageRequest,
    GenAIImageResponse,
    GenAITextRequest,
    GenAITextResponse,
)


class GenAIService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._images_dir = Path(settings.genai_images_dir)
        self._images_dir.mkdir(parents=True, exist_ok=True)
        if not settings.genai_api_key:
            self._client = None
        else:
            self._client = GenAPIClient(
                api_key=settings.genai_api_key,
                base_url=settings.genai_base_url,
            )

    def _require_client(self) -> GenAPIClient:
        if not self._client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="GENAI_API_KEY is not configured.",
            )
        return self._client

    def ask_text(self, payload: GenAITextRequest) -> GenAITextResponse:
        client = self._require_client()
        network_id = payload.network_id or self._settings.genai_default_llm_network

        messages: list[dict[str, str]] = []
        if payload.system:
            messages.append({"role": "system", "content": payload.system})
        messages.append({"role": "user", "content": payload.question})

        request_payload = {
            "model": payload.model or network_id,
            "messages": messages,
        }
        request_id = client.submit_generation(network_id=network_id, payload=request_payload)
        result = client.poll_until_done(request_id=request_id, max_wait_seconds=120)
        answer = client.extract_text(result)
        return GenAITextResponse(answer=answer, raw=result)

    def generate_image(self, payload: GenAIImageRequest) -> GenAIImageResponse:
        client = self._require_client()
        network_id = payload.network_id or self._settings.genai_default_image_network

        request_payload = {
            "model": payload.model,
            "prompt": payload.prompt,
            "width": payload.width,
            "height": payload.height,
        }
        request_id = client.submit_generation(network_id=network_id, payload=request_payload)
        result = client.poll_until_done(request_id=request_id, max_wait_seconds=180)
        content, source_url = client.extract_image_file_content(result)
        extension = client.infer_extension_from_url(source_url)
        filename = f"genai_{int(time() * 1000)}{extension}"
        target = self._images_dir / filename
        target.write_bytes(content)
        return GenAIImageResponse(
            filename=filename,
            stored_path=str(Path("storage/genai") / filename),
            source_url=source_url,
            raw=result,
        )
