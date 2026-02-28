import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.features.presentations.schemas import PresentationStatus, SlideStatus


class PresentationStorage:
    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _job_dir(self, presentation_id: str) -> Path:
        return self._base_dir / presentation_id

    def job_dir(self, presentation_id: str) -> Path:
        path = self._job_dir(presentation_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _meta_path(self, presentation_id: str) -> Path:
        return self._job_dir(presentation_id) / "meta.json"

    def _scenario_path(self, presentation_id: str) -> Path:
        return self._job_dir(presentation_id) / "scenario.json"

    def _script_path(self, presentation_id: str) -> Path:
        return self._job_dir(presentation_id) / "script.txt"

    def slides_dir(self, presentation_id: str) -> Path:
        path = self._job_dir(presentation_id) / "slides"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_job(self, payload: dict, slides_total: int, files: list[dict]) -> str:
        presentation_id = uuid4().hex
        job_dir = self.job_dir(presentation_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        self.slides_dir(presentation_id)

        slides = [
            {
                "index": index,
                "imageUrl": f"/api/presentations/{presentation_id}/slides/{index:02d}.png",
                "status": SlideStatus.pending.value,
            }
            for index in range(1, slides_total + 1)
        ]
        now = datetime.now(UTC).isoformat()
        meta = {
            "presentationId": presentation_id,
            "status": PresentationStatus.queued.value,
            "slidesReady": 0,
            "slidesTotal": slides_total,
            "slides": slides,
            "scriptText": None,
            "downloadUrl": None,
            "downloadPath": None,
            "errors": [],
            "request": payload,
            "files": files,
            "createdAt": now,
            "updatedAt": now,
        }
        self.save_meta(presentation_id, meta)
        return presentation_id

    def load_meta(self, presentation_id: str) -> dict:
        meta_path = self._meta_path(presentation_id)
        if not meta_path.exists():
            raise FileNotFoundError(f"Presentation not found: {presentation_id}")
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def save_meta(self, presentation_id: str, meta: dict) -> None:
        meta["updatedAt"] = datetime.now(UTC).isoformat()
        meta_path = self._meta_path(presentation_id)
        tmp_path = meta_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(meta_path)

    def update_meta(self, presentation_id: str, **updates) -> dict:
        meta = self.load_meta(presentation_id)
        meta.update(updates)
        self.save_meta(presentation_id, meta)
        return meta

    def save_scenario(self, presentation_id: str, scenario: dict) -> None:
        path = self._scenario_path(presentation_id)
        path.write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")

    def save_script(self, presentation_id: str, text: str) -> None:
        self._script_path(presentation_id).write_text(text, encoding="utf-8")

    def get_slide_path(self, presentation_id: str, filename: str) -> Path:
        return self.slides_dir(presentation_id) / filename

    def slide_file_path(self, presentation_id: str, filename: str) -> Path:
        return self._job_dir(presentation_id) / "slides" / filename

    def get_download_path(self, presentation_id: str) -> Path | None:
        meta = self.load_meta(presentation_id)
        download_path = meta.get("downloadPath")
        if not download_path:
            return None
        path = self._job_dir(presentation_id) / download_path
        return path if path.exists() else None
