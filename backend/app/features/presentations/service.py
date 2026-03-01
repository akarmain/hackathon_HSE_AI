import re
import threading
from uuid import uuid4
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import Settings
from app.features.presentations.model_constants import (
    SCENARIO_MODEL,
    SCENARIO_NETWORK_ID,
    WORKER_MODE,
    WORKER_MODEL,
    WORKER_NETWORK_ID,
)
from app.features.uploads.service import sanitize_filename
from app.features.presentations.orchestrator import PresentationOrchestrator
from app.features.presentations.schemas import (
    CreatePresentationRequest,
    CreatePresentationResponse,
    PresentationPromptTestRequest,
    PresentationPromptTestResponse,
    PresentationSlidePreview,
    PresentationStatusResponse,
    PresentationStatus,
)
from app.features.presentations.storage import PresentationStorage


class PresentationService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._storage = PresentationStorage(settings.presentations_dir)
        self._orchestrator = PresentationOrchestrator(settings=settings, storage=self._storage)

    def create_presentation(
        self,
        payload: CreatePresentationRequest,
        *,
        start_background: bool = True,
    ) -> CreatePresentationResponse:
        normalized_files = self._normalize_file_refs(payload.files)
        presentation_id = self._storage.create_job(
            payload=payload.model_dump(),
            slides_total=payload.slideCount,
            files=normalized_files,
        )

        if start_background:
            worker = threading.Thread(
                target=self._run_job_safe,
                args=(presentation_id,),
                daemon=True,
                name=f"presentation-{presentation_id[:8]}",
            )
            worker.start()

        meta = self._storage.load_meta(presentation_id)
        return CreatePresentationResponse(
            presentationId=presentation_id,
            status=PresentationStatus(meta["status"]),
        )

    def run_job_sync(self, presentation_id: str, *, force_fail_slide_indexes: set[int] | None = None) -> None:
        self._run_job_safe(presentation_id, force_fail_slide_indexes=force_fail_slide_indexes)

    def _run_job_safe(
        self,
        presentation_id: str,
        *,
        force_fail_slide_indexes: set[int] | None = None,
    ) -> None:
        try:
            self._orchestrator.run(
                presentation_id=presentation_id,
                force_fail_slide_indexes=force_fail_slide_indexes,
            )
        except Exception as exc:  # noqa: BLE001
            try:
                self._storage.update_meta(
                    presentation_id,
                    status=PresentationStatus.failed.value,
                    errors=[f"Fatal orchestration error: {exc}"],
                )
            except Exception:  # noqa: BLE001
                pass

    def get_status(self, presentation_id: str) -> PresentationStatusResponse:
        try:
            meta = self._storage.load_meta(presentation_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Presentation not found.",
            ) from exc
        return PresentationStatusResponse(
            status=PresentationStatus(meta["status"]),
            slidesReady=meta["slidesReady"],
            slidesTotal=meta["slidesTotal"],
            slides=meta["slides"],
            scriptText=meta.get("scriptText"),
            downloadUrl=meta.get("downloadUrl"),
        )

    def test_prompt(self, payload: PresentationPromptTestRequest) -> PresentationPromptTestResponse:
        errors: list[str] = []
        normalized_files = self._normalize_file_refs(payload.files)
        file_key_to_path = {
            item["key"]: Path(item["absolutePath"])
            for item in normalized_files
            if item.get("absolutePath")
        }

        scenario = self._orchestrator._generate_scenario_with_fallback(
            prompt=payload.prompt,
            slide_count=payload.slideCount,
            work_type=payload.workType,
            show_script=payload.showScript,
            scenario_model=SCENARIO_MODEL,
            scenario_network_id=SCENARIO_NETWORK_ID,
            file_keys=[item["key"] for item in normalized_files],
            file_hints=[
                {
                    "key": item["key"],
                    "name": item.get("originalName") or item["key"],
                }
                for item in normalized_files
            ],
            errors=errors,
        )

        slides: list[PresentationSlidePreview] = []
        if payload.includeHtml:
            preview_id = f"preview_{uuid4().hex}"
            for index, slide in enumerate(scenario.get("slides", []), start=1):
                slide["index"] = index
                html = self._orchestrator.build_slide_html_preview(
                    slide_data=slide,
                    global_style=scenario.get("globalStyle", {}),
                    worker_mode=WORKER_MODE,
                    worker_model=WORKER_MODEL,
                    worker_network_id=WORKER_NETWORK_ID,
                    file_key_to_path=file_key_to_path,
                    allow_image_generation=payload.allowImageGeneration,
                    presentation_id=preview_id,
                    errors=errors,
                )
                slides.append(
                    PresentationSlidePreview(
                        index=index,
                        title=slide.get("title", f"Slide {index}"),
                        layoutHint=slide.get("layoutHint", "title_bullets"),
                        html=html,
                    )
                )
        else:
            for index, slide in enumerate(scenario.get("slides", []), start=1):
                slides.append(
                    PresentationSlidePreview(
                        index=index,
                        title=slide.get("title", f"Slide {index}"),
                        layoutHint=slide.get("layoutHint", "title_bullets"),
                        html=None,
                    )
                )

        return PresentationPromptTestResponse(
            scenario=scenario,
            slides=slides,
            errors=errors,
        )

    def get_slide_file_path(self, presentation_id: str, filename: str) -> Path:
        safe_filename = sanitize_filename(filename)
        path = self._storage.slide_file_path(presentation_id, safe_filename)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slide not found.")
        return path

    def get_download_file_path(self, presentation_id: str) -> Path:
        path = self._storage.get_download_path(presentation_id)
        if not path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Presentation result is not ready.",
            )
        return path

    def _normalize_file_refs(self, files: list) -> list[dict]:
        uploads_dir = Path(self._settings.uploads_dir)
        uploads_dir.mkdir(parents=True, exist_ok=True)

        used_keys: set[str] = set()
        normalized: list[dict] = []
        for index, item in enumerate(files, start=1):
            raw_file_id = (item.fileId or "").strip()
            base_file_id = raw_file_id.replace("\\", "/").split("/")[-1].strip()
            if base_file_id in {"", ".", ".."}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid fileId='{item.fileId}'",
                )

            # Ignore hidden OS/service files like .DS_Store to avoid blocking generation.
            if base_file_id.startswith("."):
                continue

            absolute_path = uploads_dir / base_file_id
            if not absolute_path.exists() or not absolute_path.is_file():
                # Backward compatibility: some old file ids may be stored in sanitized form.
                safe_file_id = sanitize_filename(base_file_id)
                fallback_path = uploads_dir / safe_file_id
                if fallback_path.exists() and fallback_path.is_file():
                    absolute_path = fallback_path
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File not found for fileId='{item.fileId}'",
                    )
            resolved_file_id = absolute_path.name

            base_key = self._normalize_key(item.key or item.fileId or f"file_{index}")
            unique_key = base_key
            suffix = 2
            while unique_key in used_keys:
                unique_key = f"{base_key}_{suffix}"
                suffix += 1
            used_keys.add(unique_key)

            normalized.append(
                {
                    "key": unique_key,
                    "fileId": resolved_file_id,
                    "originalName": item.originalName or resolved_file_id,
                    "mimeType": item.mimeType,
                    "absolutePath": str(absolute_path),
                }
            )
        return normalized

    def _normalize_key(self, raw_key: str) -> str:
        lowered = raw_key.strip().lower()
        # Keep unicode letters/digits so russian descriptions don't collapse to "file".
        safe = re.sub(r"[^\w-]+", "_", lowered, flags=re.UNICODE)
        safe = re.sub(r"_+", "_", safe).strip("_")
        return safe or "file"
