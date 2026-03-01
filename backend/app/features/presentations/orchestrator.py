import base64
import ast
import copy
import json
import logging
import mimetypes
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from shutil import copy2

from fastapi import HTTPException

from app.core.config import Settings
from app.features.genai.schemas import GenAIImageRequest, GenAITextRequest
from app.features.genai.service import GenAIService
from app.features.presentations.model_constants import (
    SCENARIO_MODEL,
    SCENARIO_NETWORK_ID,
    SLIDE_CONCURRENCY,
    WORKER_MODE,
    WORKER_MODEL,
    WORKER_NETWORK_ID,
)
from app.features.presentations.pdf import build_pdf_from_images
from app.features.presentations.prompt_templates import (
    build_master_scenario_prompt,
    build_worker_html_prompt,
)
from app.features.presentations.renderer import SlideRenderer
from app.features.presentations.schemas import PresentationStatus, SlideStatus
from app.features.presentations.storage import PresentationStorage

_LAYOUT_ALIASES = {
    "title_only": "title_only",
    "title_bullets": "title_bullets",
    "two_columns": "two_columns",
    "full_image_caption": "full_image_caption",
    "chart_insights": "chart_insights",
}

_ALLOWED_BLOCK_TYPES = {
    "badge",
    "title",
    "subtitle",
    "main_text",
    "bullets",
    "image",
    "caption",
    "footer",
}

_ALLOWED_TEXT_ALIGN = {"left", "center", "right"}
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_COLOR_RE = re.compile(r"^(?:rgb|rgba|hsl|hsla)\([0-9.,%\s]+\)$", flags=re.IGNORECASE)

_DEFAULT_GLOBAL_STYLE = {
    "theme": "modern_gradient",
    "fontFamily": "\"Trebuchet MS\", \"Avenir Next\", \"Segoe UI\", sans-serif",
    "background": "soft_gradient",
    "palette": {
        "bg": "#0b1020",
        "surface": "#121a36",
        "primary": "#5d7cff",
        "accent": "#ff5d9a",
        "text": "#f7f9ff",
        "muted": "#c4cbe5",
        "border": "rgba(255,255,255,0.2)",
    },
}

_DEFAULT_BLOCKS_BY_LAYOUT = {
    "title_only": [
        {
            "type": "badge",
            "x": 64,
            "y": 44,
            "w": 220,
            "h": 34,
            "align": "left",
            "fontSize": 12,
            "fontWeight": 700,
            "lineHeight": 1.0,
            "padding": 10,
            "radius": 999,
            "background": "rgba(255,255,255,0.12)",
            "border": "rgba(255,255,255,0.28)",
        },
        {
            "type": "title",
            "x": 64,
            "y": 106,
            "w": 1148,
            "h": 186,
            "align": "left",
            "fontSize": 62,
            "fontWeight": 820,
            "lineHeight": 1.04,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "main_text",
            "x": 64,
            "y": 314,
            "w": 1060,
            "h": 220,
            "align": "left",
            "fontSize": 28,
            "fontWeight": 500,
            "lineHeight": 1.35,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "footer",
            "x": 64,
            "y": 646,
            "w": 1140,
            "h": 28,
            "align": "left",
            "fontSize": 16,
            "fontWeight": 500,
            "lineHeight": 1.1,
            "padding": 0,
            "radius": 0,
        },
    ],
    "title_bullets": [
        {
            "type": "badge",
            "x": 64,
            "y": 42,
            "w": 220,
            "h": 34,
            "align": "left",
            "fontSize": 12,
            "fontWeight": 700,
            "lineHeight": 1.0,
            "padding": 10,
            "radius": 999,
            "background": "rgba(255,255,255,0.12)",
            "border": "rgba(255,255,255,0.28)",
        },
        {
            "type": "title",
            "x": 64,
            "y": 90,
            "w": 740,
            "h": 112,
            "align": "left",
            "fontSize": 54,
            "fontWeight": 820,
            "lineHeight": 1.06,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "subtitle",
            "x": 64,
            "y": 208,
            "w": 730,
            "h": 40,
            "align": "left",
            "fontSize": 24,
            "fontWeight": 600,
            "lineHeight": 1.2,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "main_text",
            "x": 64,
            "y": 252,
            "w": 700,
            "h": 122,
            "align": "left",
            "fontSize": 22,
            "fontWeight": 500,
            "lineHeight": 1.34,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "bullets",
            "x": 64,
            "y": 392,
            "w": 700,
            "h": 256,
            "align": "left",
            "fontSize": 20,
            "fontWeight": 520,
            "lineHeight": 1.32,
            "padding": 16,
            "radius": 18,
            "background": "rgba(255,255,255,0.1)",
            "border": "rgba(255,255,255,0.18)",
        },
        {
            "type": "image",
            "slot": "image_primary",
            "x": 806,
            "y": 136,
            "w": 410,
            "h": 512,
            "align": "left",
            "fontSize": 16,
            "fontWeight": 500,
            "lineHeight": 1.2,
            "padding": 0,
            "radius": 22,
            "background": "rgba(255,255,255,0.08)",
            "border": "rgba(255,255,255,0.2)",
        },
    ],
    "two_columns": [
        {
            "type": "badge",
            "x": 64,
            "y": 42,
            "w": 220,
            "h": 34,
            "align": "left",
            "fontSize": 12,
            "fontWeight": 700,
            "lineHeight": 1.0,
            "padding": 10,
            "radius": 999,
            "background": "rgba(255,255,255,0.12)",
            "border": "rgba(255,255,255,0.28)",
        },
        {
            "type": "title",
            "x": 64,
            "y": 90,
            "w": 1140,
            "h": 96,
            "align": "left",
            "fontSize": 50,
            "fontWeight": 820,
            "lineHeight": 1.06,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "main_text",
            "x": 64,
            "y": 204,
            "w": 552,
            "h": 140,
            "align": "left",
            "fontSize": 22,
            "fontWeight": 500,
            "lineHeight": 1.35,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "bullets",
            "x": 64,
            "y": 356,
            "w": 552,
            "h": 292,
            "align": "left",
            "fontSize": 19,
            "fontWeight": 520,
            "lineHeight": 1.32,
            "padding": 18,
            "radius": 18,
            "background": "rgba(255,255,255,0.1)",
            "border": "rgba(255,255,255,0.18)",
        },
        {
            "type": "image",
            "slot": "image_primary",
            "x": 652,
            "y": 204,
            "w": 564,
            "h": 444,
            "align": "left",
            "fontSize": 16,
            "fontWeight": 500,
            "lineHeight": 1.2,
            "padding": 0,
            "radius": 22,
            "background": "rgba(255,255,255,0.08)",
            "border": "rgba(255,255,255,0.2)",
        },
    ],
    "full_image_caption": [
        {
            "type": "badge",
            "x": 64,
            "y": 42,
            "w": 220,
            "h": 34,
            "align": "left",
            "fontSize": 12,
            "fontWeight": 700,
            "lineHeight": 1.0,
            "padding": 10,
            "radius": 999,
            "background": "rgba(255,255,255,0.12)",
            "border": "rgba(255,255,255,0.28)",
        },
        {
            "type": "title",
            "x": 64,
            "y": 90,
            "w": 1140,
            "h": 90,
            "align": "left",
            "fontSize": 50,
            "fontWeight": 820,
            "lineHeight": 1.08,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "image",
            "slot": "image_primary",
            "x": 64,
            "y": 186,
            "w": 1152,
            "h": 378,
            "align": "left",
            "fontSize": 16,
            "fontWeight": 500,
            "lineHeight": 1.2,
            "padding": 0,
            "radius": 22,
            "background": "rgba(255,255,255,0.08)",
            "border": "rgba(255,255,255,0.2)",
        },
        {
            "type": "caption",
            "x": 64,
            "y": 580,
            "w": 760,
            "h": 86,
            "align": "left",
            "fontSize": 22,
            "fontWeight": 520,
            "lineHeight": 1.35,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "bullets",
            "x": 846,
            "y": 580,
            "w": 370,
            "h": 86,
            "align": "left",
            "fontSize": 17,
            "fontWeight": 520,
            "lineHeight": 1.28,
            "padding": 12,
            "radius": 16,
            "background": "rgba(255,255,255,0.1)",
            "border": "rgba(255,255,255,0.18)",
        },
    ],
    "chart_insights": [
        {
            "type": "badge",
            "x": 64,
            "y": 42,
            "w": 220,
            "h": 34,
            "align": "left",
            "fontSize": 12,
            "fontWeight": 700,
            "lineHeight": 1.0,
            "padding": 10,
            "radius": 999,
            "background": "rgba(255,255,255,0.12)",
            "border": "rgba(255,255,255,0.28)",
        },
        {
            "type": "title",
            "x": 64,
            "y": 90,
            "w": 1140,
            "h": 96,
            "align": "left",
            "fontSize": 50,
            "fontWeight": 820,
            "lineHeight": 1.06,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "image",
            "slot": "image_primary",
            "x": 64,
            "y": 208,
            "w": 694,
            "h": 442,
            "align": "left",
            "fontSize": 16,
            "fontWeight": 500,
            "lineHeight": 1.2,
            "padding": 0,
            "radius": 22,
            "background": "rgba(255,255,255,0.08)",
            "border": "rgba(255,255,255,0.2)",
        },
        {
            "type": "main_text",
            "x": 784,
            "y": 208,
            "w": 432,
            "h": 154,
            "align": "left",
            "fontSize": 21,
            "fontWeight": 520,
            "lineHeight": 1.35,
            "padding": 0,
            "radius": 0,
        },
        {
            "type": "bullets",
            "x": 784,
            "y": 370,
            "w": 432,
            "h": 280,
            "align": "left",
            "fontSize": 18,
            "fontWeight": 520,
            "lineHeight": 1.3,
            "padding": 16,
            "radius": 18,
            "background": "rgba(255,255,255,0.1)",
            "border": "rgba(255,255,255,0.18)",
        },
    ],
}

logger = logging.getLogger(__name__)


class PresentationOrchestrator:
    def __init__(self, settings: Settings, storage: PresentationStorage) -> None:
        self._settings = settings
        self._storage = storage
        self._renderer = SlideRenderer()
        self._genai = GenAIService(settings=settings)

    def run(self, presentation_id: str, force_fail_slide_indexes: set[int] | None = None) -> None:
        meta = self._storage.load_meta(presentation_id)
        request = meta["request"]
        force_fail_slide_indexes = force_fail_slide_indexes or set()
        errors: list[str] = list(meta.get("errors", []))

        self._storage.update_meta(presentation_id, status=PresentationStatus.running.value)

        scenario = self._generate_scenario_with_fallback(
            prompt=request["prompt"],
            slide_count=request["slideCount"],
            work_type=request["workType"],
            show_script=request["showScript"],
            scenario_model=SCENARIO_MODEL,
            scenario_network_id=SCENARIO_NETWORK_ID,
            file_keys=[item["key"] for item in meta.get("files", [])],
            file_hints=[
                {
                    "key": item["key"],
                    "name": item.get("originalName") or item["key"],
                }
                for item in meta.get("files", [])
                if item.get("key")
            ],
            errors=errors,
        )
        logger.info("Presentation %s scenario: %s", presentation_id, json.dumps(scenario, ensure_ascii=False))
        self._storage.save_scenario(presentation_id, scenario)
        script_text: str | None = None
        if request["showScript"]:
            script_text = self._build_script_text_from_scenario(scenario["slides"])
            if script_text:
                self._storage.save_script(presentation_id, script_text)
                # Expose script as soon as scenario is ready instead of waiting for all slides.
                self._storage.update_meta(presentation_id, scriptText=script_text)

        file_key_to_path = {
            item["key"]: Path(item["absolutePath"])
            for item in meta.get("files", [])
            if item.get("absolutePath")
        }

        slides = meta["slides"]
        ready_slide_paths_by_index: dict[int, Path] = {}
        slides_ready = 0
        global_style = scenario.get("globalStyle", {})
        max_workers = max(1, min(int(SLIDE_CONCURRENCY), len(scenario["slides"])))

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"slide-{presentation_id[:6]}") as executor:
            future_to_index = {}
            for index, slide_data in enumerate(scenario["slides"], start=1):
                future = executor.submit(
                    self._generate_single_slide,
                    presentation_id=presentation_id,
                    slide_index=index,
                    slide_data=slide_data,
                    global_style=global_style,
                    worker_mode=WORKER_MODE,
                    worker_model=WORKER_MODEL,
                    worker_network_id=WORKER_NETWORK_ID,
                    file_key_to_path=file_key_to_path,
                    force_fail=index in force_fail_slide_indexes,
                )
                future_to_index[future] = index

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = {
                        "status": SlideStatus.failed.value,
                        "errors": [f"Slide {index}: {exc}"],
                        "pngPath": None,
                    }

                if result["status"] == SlideStatus.ready.value:
                    slides[index - 1]["status"] = SlideStatus.ready.value
                    slides_ready += 1
                    png_path_raw = result.get("pngPath")
                    if isinstance(png_path_raw, str) and png_path_raw:
                        ready_slide_paths_by_index[index] = Path(png_path_raw)
                else:
                    slides[index - 1]["status"] = SlideStatus.failed.value

                for message in result.get("errors", []):
                    if isinstance(message, str) and message.strip():
                        errors.append(message.strip())

                self._storage.update_meta(
                    presentation_id,
                    status=PresentationStatus.running.value,
                    slides=slides,
                    slidesReady=slides_ready,
                    errors=errors,
                )

        download_path: str | None = None
        download_url: str | None = None

        ready_slide_paths = [
            ready_slide_paths_by_index[index]
            for index in sorted(ready_slide_paths_by_index.keys())
        ]

        if ready_slide_paths:
            try:
                pdf_path = self._storage.job_dir(presentation_id) / "result.pdf"
                build_pdf_from_images(ready_slide_paths, pdf_path)
                download_path = "result.pdf"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"PDF build failed: {exc}")
                zip_path = self._storage.job_dir(presentation_id) / "result.zip"
                self._build_zip(ready_slide_paths, zip_path)
                download_path = "result.zip"

            download_url = f"/api/presentations/{presentation_id}/download"

        final_status = self._resolve_final_status(slides_ready, request["slideCount"], errors)
        self._storage.update_meta(
            presentation_id,
            status=final_status.value,
            slides=slides,
            slidesReady=slides_ready,
            scriptText=script_text,
            downloadPath=download_path,
            downloadUrl=download_url,
            errors=errors,
        )

    def _build_script_text_from_scenario(self, slides: list[dict]) -> str | None:
        script_lines: list[str] = []
        for index, slide_data in enumerate(slides, start=1):
            notes = str(slide_data.get("speakerNotes") or "").strip()
            if notes:
                script_lines.append(f"[Slide {index}] {notes}")
                continue

            title = str(slide_data.get("title") or "").strip()
            main_text = str(slide_data.get("mainText") or "").strip()
            bullets = [
                str(item).strip()
                for item in (slide_data.get("bullets") or [])
                if str(item).strip()
            ]
            fragments: list[str] = []
            if title:
                fragments.append(title)
            if main_text:
                fragments.append(main_text)
            if bullets:
                fragments.append(f"Ключевые пункты: {'; '.join(bullets[:3])}.")
            if fragments:
                script_lines.append(f"[Slide {index}] {' '.join(fragments)}")

        if not script_lines:
            return None
        return "\n\n".join(script_lines)

    def _generate_single_slide(
        self,
        *,
        presentation_id: str,
        slide_index: int,
        slide_data: dict,
        global_style: dict,
        worker_mode: str,
        worker_model: str | None,
        worker_network_id: str | None,
        file_key_to_path: dict[str, Path],
        force_fail: bool,
    ) -> dict:
        slide_errors: list[str] = []
        png_path: Path | None = None
        status = SlideStatus.failed.value

        try:
            if force_fail:
                raise RuntimeError("Forced slide failure for testing.")

            html, _ = self._build_slide_html_and_assets(
                presentation_id=presentation_id,
                slide_index=slide_index,
                slide_data=slide_data,
                global_style=global_style,
                worker_mode=worker_mode,
                worker_model=worker_model,
                worker_network_id=worker_network_id,
                file_key_to_path=file_key_to_path,
                errors=slide_errors,
            )
            html_path = self._storage.slides_dir(presentation_id) / f"{slide_index:02d}.html"
            html_path.write_text(html, encoding="utf-8")

            png_path = self._storage.get_slide_path(presentation_id, f"{slide_index:02d}.png")
            self._renderer.render(
                output_path=png_path,
                html=html,
                fallback_title=slide_data.get("title") or f"Slide {slide_index}",
                fallback_text=slide_data.get("mainText") or "",
            )
            status = SlideStatus.ready.value
        except Exception as exc:  # noqa: BLE001
            slide_errors.append(str(exc))
            status = SlideStatus.failed.value

        prefixed_errors: list[str] = []
        for err in slide_errors:
            clean = str(err).strip()
            if not clean:
                continue
            if clean.lower().startswith(f"slide {slide_index}:"):
                prefixed_errors.append(clean)
            else:
                prefixed_errors.append(f"Slide {slide_index}: {clean}")

        return {
            "status": status,
            "errors": prefixed_errors,
            "pngPath": str(png_path) if png_path else None,
        }

    def _build_zip(self, slide_paths: list[Path], output_path: Path) -> None:
        with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for slide_path in slide_paths:
                archive.write(slide_path, arcname=slide_path.name)

    def _resolve_final_status(
        self,
        slides_ready: int,
        slides_total: int,
        errors: list[str],
    ) -> PresentationStatus:
        if slides_ready == 0:
            return PresentationStatus.failed
        if errors or slides_ready < slides_total:
            return PresentationStatus.completed_with_errors
        return PresentationStatus.completed

    def _build_slide_html_and_assets(
        self,
        presentation_id: str,
        slide_index: int,
        slide_data: dict,
        global_style: dict,
        worker_mode: str,
        worker_model: str | None,
        worker_network_id: str | None,
        file_key_to_path: dict[str, Path],
        errors: list[str],
    ) -> tuple[str, list[Path]]:
        image_paths, slot_to_path = self._resolve_slide_assets(
            presentation_id=presentation_id,
            slide_index=slide_index,
            slide_data=slide_data,
            file_key_to_path=file_key_to_path,
            allow_image_generation=True,
            errors=errors,
            error_prefix=f"Slide {slide_index}",
        )

        image_data_by_slot = self._build_image_slot_data_map(slot_to_path)
        html = self._generate_slide_html_with_fallback(
            slide_data=slide_data,
            global_style=global_style,
            image_data_by_slot=image_data_by_slot,
            slide_index=slide_index,
            worker_mode=worker_mode,
            worker_model=worker_model,
            worker_network_id=worker_network_id,
            errors=errors,
        )
        return html, image_paths

    def _resolve_slide_assets(
        self,
        presentation_id: str,
        slide_index: int,
        slide_data: dict,
        file_key_to_path: dict[str, Path],
        allow_image_generation: bool,
        errors: list[str],
        error_prefix: str,
    ) -> tuple[list[Path], dict[str, Path]]:
        slot_to_path: dict[str, Path] = {}
        ordered_paths: list[Path] = []
        seen_paths: set[Path] = set()

        def add_asset(slot: str, path: Path) -> None:
            slot_to_path[slot] = path
            if path not in seen_paths:
                ordered_paths.append(path)
                seen_paths.add(path)

        use_files = slide_data.get("assets", {}).get("useFiles", [])
        for asset_index, ref in enumerate(use_files, start=1):
            key = ref.get("key") if isinstance(ref, dict) else None
            if not isinstance(key, str) or not key:
                continue
            slot = self._normalize_slot_name(
                ref.get("slot") if isinstance(ref, dict) else "",
                fallback=f"image_{asset_index}",
            )
            path = file_key_to_path.get(key)
            if path and path.exists() and path.is_file():
                add_asset(slot, path)
            else:
                errors.append(f"{error_prefix}: file key '{key}' not found.")

        if allow_image_generation:
            generate_images = slide_data.get("assets", {}).get("generateImages", [])
            for asset_index, image_request in enumerate(generate_images, start=1):
                prompt = (image_request.get("prompt") or "").strip() if isinstance(image_request, dict) else ""
                if not prompt:
                    continue
                slot = self._normalize_slot_name(
                    image_request.get("slot") if isinstance(image_request, dict) else "",
                    fallback=f"image_gen_{asset_index}",
                )
                generated = self._generate_support_image(
                    presentation_id=presentation_id,
                    slide_index=slide_index,
                    asset_index=asset_index,
                    prompt=prompt,
                )
                if generated:
                    add_asset(slot, generated)
                else:
                    errors.append(
                        f"{error_prefix}: generated image failed for prompt '{prompt[:80]}'."
                    )

        return ordered_paths, slot_to_path

    def _generate_support_image(
        self,
        presentation_id: str,
        slide_index: int,
        asset_index: int,
        prompt: str,
    ) -> Path | None:
        try:
            result = self._genai.generate_image(
                GenAIImageRequest(prompt=prompt, width=1024, height=576)
            )
        except HTTPException:
            return None
        except Exception:  # noqa: BLE001
            return None

        source = Path(self._settings.genai_images_dir) / result.filename
        if not source.exists():
            return None

        target_dir = self._storage.job_dir(presentation_id) / "generated"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"slide_{slide_index:02d}_{asset_index:02d}{source.suffix or '.png'}"
        copy2(source, target)
        return target

    def _generate_slide_html_with_fallback(
        self,
        slide_data: dict,
        global_style: dict,
        image_data_by_slot: dict[str, str],
        slide_index: int,
        worker_mode: str,
        worker_model: str | None,
        worker_network_id: str | None,
        errors: list[str],
    ) -> str:
        try:
            worker_payload = self._build_worker_payload(
                slide_data=slide_data,
                global_style=global_style,
                image_data_by_slot=image_data_by_slot,
                slide_index=slide_index,
            )
            if str(worker_mode).lower() == "llm":
                html = self._generate_worker_html_llm(
                    worker_payload=worker_payload,
                    worker_model=worker_model,
                    worker_network_id=worker_network_id,
                )
                hydrated = self._inject_image_slots(html, image_data_by_slot)
                return self._enforce_worker_font_family(
                    hydrated,
                    worker_payload["theme"]["fontFamily"],
                )
            return self._render_worker_html(worker_payload)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Worker HTML build failed: {exc}")
            return self._build_slide_html_fallback(
                title=slide_data.get("title") or "Slide",
                main_text=slide_data.get("mainText") or "",
                bullets=slide_data.get("bullets") or [],
                layout=slide_data.get("layoutHint") or "title_bullets",
                image_data_by_slot=image_data_by_slot,
            )

    def _build_worker_payload(
        self,
        slide_data: dict,
        global_style: dict,
        image_data_by_slot: dict[str, str],
        slide_index: int,
    ) -> dict:
        normalized_global = self._normalize_global_style(global_style)
        slide_style = self._normalize_slide_style(
            slide_data.get("style") if isinstance(slide_data.get("style"), dict) else {},
            slide_data.get("visual") if isinstance(slide_data.get("visual"), dict) else {},
            normalized_global,
            slide_index,
        )
        layout = self._normalize_layout(slide_data.get("layoutHint") or "")
        composition = self._normalize_composition(slide_data.get("composition"), layout, slide_index)

        return {
            "layout": layout,
            "canvas": {"width": 1280, "height": 720},
            "theme": {
                "background": slide_style["background"],
                "fontFamily": slide_style["fontFamily"],
                "palette": slide_style["palette"],
            },
            "content": {
                "kicker": str(slide_data.get("kicker") or ""),
                "title": str(slide_data.get("title") or ""),
                "subtitle": str(slide_data.get("subtitle") or ""),
                "mainText": str(slide_data.get("mainText") or ""),
                "bullets": [str(item) for item in (slide_data.get("bullets") or [])][:8],
                "footer": str(slide_data.get("footer") or ""),
            },
            "blocks": composition["blocks"],
            "images": image_data_by_slot,
        }

    def _render_worker_html(self, worker_payload: dict) -> str:
        palette = worker_payload["theme"]["palette"]
        font_family = self._sanitize_font_family(worker_payload["theme"]["fontFamily"])
        primary_glow = self._color_with_alpha(palette["primary"], 0.34, "rgba(93,124,255,0.34)")
        accent_glow = self._color_with_alpha(palette["accent"], 0.3, "rgba(255,93,154,0.3)")

        blocks_html = "".join(
            self._render_worker_block(
                block=block,
                content=worker_payload["content"],
                images=worker_payload["images"],
                palette=palette,
                layout=worker_payload["layout"],
            )
            for block in worker_payload["blocks"]
        )

        return f"""<!doctype html>
<html lang=\"ru\">
  <head>
    <meta charset=\"UTF-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <style>
      * {{ box-sizing: border-box; }}
      html, body {{ margin: 0; width: 100%; height: 100%; overflow: hidden; }}
      body {{
        font-family: {font_family};
        color: {palette['text']};
        background:
          radial-gradient(860px 420px at 14% -8%, {primary_glow}, rgba(0, 0, 0, 0) 62%),
          radial-gradient(720px 380px at 88% 0%, {accent_glow}, rgba(0, 0, 0, 0) 60%),
          linear-gradient(135deg, {palette['bg']} 0%, {palette['surface']} 54%, {palette['bg']} 100%);
      }}
      .slide {{
        width: 1280px;
        height: 720px;
        position: relative;
        overflow: hidden;
      }}
      .block {{ position: absolute; overflow: hidden; }}
      .block-title {{ letter-spacing: -0.02em; }}
      .block-badge {{ text-transform: uppercase; letter-spacing: 0.08em; }}
      .block-bullets ul {{ margin: 0; padding-left: 1.2em; }}
      .block-bullets li {{ margin-bottom: 0.45em; }}
      .block-image img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
      .image-placeholder {{
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: {palette['muted']};
        border: 1px dashed {palette['border']};
        background: rgba(255, 255, 255, 0.04);
      }}
    </style>
  </head>
  <body>
    <div class=\"slide\">{blocks_html}</div>
  </body>
</html>"""

    def _generate_worker_html_llm(
        self,
        worker_payload: dict,
        worker_model: str | None,
        worker_network_id: str | None,
    ) -> str:
        prompt = build_worker_html_prompt(worker_payload=worker_payload)
        answer = self._genai.ask_text(
            GenAITextRequest(
                question=prompt,
                model=worker_model,
                network_id=worker_network_id,
            )
        ).answer
        cleaned = self._strip_markdown_fences(answer).strip()
        html_document = self._extract_html_document(cleaned)
        if not html_document:
            raise ValueError("Worker model did not return a full HTML document.")
        return html_document

    def _inject_image_slots(self, html: str, image_data_by_slot: dict[str, str]) -> str:
        hydrated = html
        for slot, data_uri in image_data_by_slot.items():
            token = f"{{{{{slot}}}}}"
            hydrated = hydrated.replace(token, data_uri)
        hydrated = self._normalize_image_placeholders(hydrated, image_data_by_slot)
        return hydrated

    def _normalize_image_placeholders(self, html: str, image_data_by_slot: dict[str, str]) -> str:
        normalized = html

        # Case 1: model put the data URI text inside placeholder block instead of img src.
        data_uri_text_pattern = re.compile(
            r"(<(?P<tag>[a-zA-Z0-9]+)[^>]*class=(?P<q>[\"'])[^\"']*image-placeholder[^\"']*(?P=q)[^>]*>)"
            r"\s*(?P<data_uri>data:image/[^<]+?)\s*(</(?P=tag)>)",
            flags=re.IGNORECASE | re.DOTALL,
        )

        def replace_data_uri_text(match: re.Match[str]) -> str:
            opening = match.group(1)
            closing = match.group(5)
            data_uri = match.group("data_uri").strip()
            escaped_src = self._escape_html(data_uri)
            return (
                f"{opening}<img src='{escaped_src}' alt='slide image' "
                "style='width:100%;height:100%;object-fit:cover;display:block;' />"
                f"{closing}"
            )

        normalized = data_uri_text_pattern.sub(replace_data_uri_text, normalized)

        # Case 2: model rendered a placeholder without token despite available image data.
        has_data_image = bool(re.search(r"<img[^>]+src=['\"]data:image", normalized, flags=re.IGNORECASE))
        if not has_data_image and image_data_by_slot:
            first_data_uri = next(iter(image_data_by_slot.values()))
            escaped_src = self._escape_html(first_data_uri)
            plain_placeholder_pattern = re.compile(
                r"(<(?P<tag>[a-zA-Z0-9]+)[^>]*class=(?P<q>[\"'])[^\"']*image-placeholder[^\"']*(?P=q)[^>]*>)"
                r"(?P<inner>[\s\S]*?)(</(?P=tag)>)",
                flags=re.IGNORECASE,
            )

            def replace_plain_placeholder(match: re.Match[str]) -> str:
                opening = match.group(1)
                inner = match.group("inner")
                closing = match.group(5)
                if "<img" in inner.lower():
                    return match.group(0)
                return (
                    f"{opening}<img src='{escaped_src}' alt='slide image' "
                    "style='width:100%;height:100%;object-fit:cover;display:block;' />"
                    f"{closing}"
                )

            normalized = plain_placeholder_pattern.sub(replace_plain_placeholder, normalized, count=1)

        return normalized

    def _enforce_worker_font_family(self, html: str, font_family: str) -> str:
        preferred = self._sanitize_font_family(font_family)
        if "worker-font-override" in html:
            return html

        style = (
            "<style id='worker-font-override'>"
            f"html, body, body * {{ font-family: {preferred} !important; }}"
            "</style>"
        )
        match = re.search(r"</head>", html, flags=re.IGNORECASE)
        if match:
            return f"{html[:match.start()]}{style}{html[match.start():]}"
        return f"{style}{html}"

    def _extract_html_document(self, raw_text: str) -> str | None:
        html = self._extract_html_fragment(raw_text)
        if html:
            return html

        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw_text)
            except Exception:  # noqa: BLE001
                continue

            nested_text = self._find_string_with_html(parsed)
            if not nested_text:
                continue
            html = self._extract_html_fragment(nested_text)
            if html:
                return html

        return None

    def _find_string_with_html(self, node: object) -> str | None:
        if isinstance(node, str):
            candidate = node.strip()
            lowered = candidate.lower()
            if "<html" in lowered or "<!doctype html" in lowered:
                return candidate
            return None

        if isinstance(node, list):
            for item in node:
                candidate = self._find_string_with_html(item)
                if candidate:
                    return candidate
            return None

        if not isinstance(node, dict):
            return None

        # Most likely text containers in model responses.
        for key in ("content", "text", "answer", "output", "response"):
            if key in node:
                candidate = self._find_string_with_html(node.get(key))
                if candidate:
                    return candidate

        for key in ("message", "delta", "choices", "result", "results", "data", "full_response", "items", "value"):
            if key in node:
                candidate = self._find_string_with_html(node.get(key))
                if candidate:
                    return candidate

        return None

    def _extract_html_fragment(self, text: str) -> str | None:
        if not isinstance(text, str) or not text.strip():
            return None
        doctype_match = re.search(r"<!doctype\s+html[^>]*>[\s\S]*?</html>", text, flags=re.IGNORECASE)
        if doctype_match:
            return doctype_match.group(0).strip()
        html_match = re.search(r"<html\b[^>]*>[\s\S]*?</html>", text, flags=re.IGNORECASE)
        if html_match:
            return html_match.group(0).strip()
        return None

    def _render_worker_block(
        self,
        block: dict,
        content: dict,
        images: dict[str, str],
        palette: dict,
        layout: str,
    ) -> str:
        block_type = block["type"]
        if block_type == "image":
            return self._render_image_block(block, content, images)
        if block_type == "bullets":
            return self._render_bullets_block(block, content, palette)
        return self._render_text_block(block, content, palette, layout)

    def _render_text_block(self, block: dict, content: dict, palette: dict, layout: str) -> str:
        text_map = {
            "badge": content.get("kicker") or layout.replace("_", " "),
            "title": content.get("title", ""),
            "subtitle": content.get("subtitle", ""),
            "main_text": content.get("mainText", ""),
            "caption": content.get("mainText", ""),
            "footer": content.get("footer", ""),
        }
        text = str(text_map.get(block["type"], "") or "")
        if not text and block["type"] not in {"title", "main_text", "badge"}:
            return ""

        rendered_text = self._escape_html(text).replace("\n", "<br />")
        color = block.get("color") or (palette["muted"] if block["type"] in {"subtitle", "footer"} else palette["text"])
        style = self._block_base_style(block)
        style += f"text-align:{block['align']};"
        style += f"font-size:{block['fontSize']}px;"
        style += f"font-weight:{block['fontWeight']};"
        style += f"line-height:{block['lineHeight']};"
        style += f"color:{color};"
        if block["type"] in {"badge", "footer"}:
            style += "display:flex;align-items:center;"
        class_name = f"block block-{block['type']}"
        return f"<div class='{class_name}' style='{style}'>{rendered_text}</div>"

    def _render_bullets_block(self, block: dict, content: dict, palette: dict) -> str:
        bullets = [str(item) for item in (content.get("bullets") or [])][:8]
        if not bullets:
            main_text = str(content.get("mainText") or "").strip()
            bullets = [main_text] if main_text else []
        if not bullets:
            return ""

        bullets_html = "".join(f"<li>{self._escape_html(item)}</li>" for item in bullets)
        color = block.get("color") or palette["text"]
        style = self._block_base_style(block)
        style += f"text-align:{block['align']};"
        style += f"font-size:{block['fontSize']}px;"
        style += f"font-weight:{block['fontWeight']};"
        style += f"line-height:{block['lineHeight']};"
        style += f"color:{color};"
        return f"<div class='block block-bullets' style='{style}'><ul>{bullets_html}</ul></div>"

    def _render_image_block(self, block: dict, content: dict, images: dict[str, str]) -> str:
        style = self._block_base_style(block)
        slot = block.get("slot") or "image_primary"
        image_src = images.get(slot) or images.get("image_primary")
        if not image_src and images:
            image_src = next(iter(images.values()))

        if not image_src:
            return (
                f"<div class='block block-image' style='{style}'>"
                "<div class='image-placeholder'>No image</div>"
                "</div>"
            )

        title = self._escape_html(str(content.get("title") or "slide image"))
        escaped_src = self._escape_html(image_src)
        return (
            f"<div class='block block-image' style='{style}'>"
            f"<img src='{escaped_src}' alt='{title}' />"
            "</div>"
        )

    def _block_base_style(self, block: dict) -> str:
        style = (
            f"left:{block['x']}px;"
            f"top:{block['y']}px;"
            f"width:{block['w']}px;"
            f"height:{block['h']}px;"
            f"padding:{block['padding']}px;"
            f"border-radius:{block['radius']}px;"
        )
        background = block.get("background")
        border = block.get("border")
        if background:
            style += f"background:{background};"
        if border:
            style += f"border:1px solid {border};"
        return style

    def _build_slide_html_fallback(
        self,
        title: str,
        main_text: str,
        bullets: list[str],
        layout: str,
        image_data_by_slot: dict[str, str],
    ) -> str:
        bullets_html = "".join(f"<li>{self._escape_html(item)}</li>" for item in bullets[:8])
        image_src = image_data_by_slot.get("image_primary")
        if not image_src and image_data_by_slot:
            image_src = next(iter(image_data_by_slot.values()))
        image_html = (
            f"<img src='{self._escape_html(image_src)}' style='max-width:100%;max-height:100%;border-radius:18px;'/>"
            if image_src
            else "<div style='height:100%;display:flex;align-items:center;justify-content:center;border:1px dashed rgba(255,255,255,.35);border-radius:18px;color:#d9defe;'>No image</div>"
        )
        grid_columns = "1fr 1fr" if layout in {"two_columns", "chart_insights"} else "1fr"
        if layout == "full_image_caption":
            grid_columns = "1fr"

        right_block = image_html if layout != "title_only" else "<div></div>"

        return f"""<!doctype html>
<html lang=\"ru\">
  <head>
    <meta charset=\"UTF-8\">
    <style>
      * {{ box-sizing: border-box; }}
      html, body {{ margin:0; padding:0; width:100%; height:100%; font-family: \"Trebuchet MS\", \"Avenir Next\", \"Segoe UI\", sans-serif; }}
      body {{ background: #0b1020; color: #ffffff; overflow: hidden; }}
      .slide {{
        width: 1280px;
        height: 720px;
        position: relative;
        padding: 58px 64px;
        background:
          radial-gradient(900px 420px at 15% 10%, rgba(93,124,255,.55), rgba(93,124,255,0) 60%),
          radial-gradient(900px 420px at 85% 0%, rgba(255,93,154,.45), rgba(255,93,154,0) 55%),
          linear-gradient(135deg, #0b1020 0%, #0a1636 50%, #0b1020 100%);
      }}
      .kicker {{
        display:inline-block;
        padding:8px 12px;
        border-radius:999px;
        border:1px solid rgba(255,255,255,.24);
        background:rgba(255,255,255,.08);
        font-size:12px;
        letter-spacing:.08em;
        text-transform:uppercase;
      }}
      .title {{ margin:14px 0 10px; font-size:52px; line-height:1.05; letter-spacing:-0.02em; font-weight:900; }}
      .main {{ font-size:18px; line-height:1.58; opacity:.95; max-width:1080px; }}
      .content {{
        margin-top: 18px;
        display:grid;
        grid-template-columns: {grid_columns};
        gap: 22px;
        height: 460px;
      }}
      .card {{
        border-radius:18px;
        border:1px solid rgba(255,255,255,.18);
        background:rgba(255,255,255,.08);
        padding:18px 20px;
      }}
      li {{ margin-bottom:8px; }}
      .image-wrap {{ border-radius:18px; overflow:hidden; height:100%; }}
    </style>
  </head>
  <body>
    <div class=\"slide\">
      <span class=\"kicker\">{self._escape_html(layout)}</span>
      <h1 class=\"title\">{self._escape_html(title)}</h1>
      <div class=\"main\">{self._escape_html(main_text)}</div>
      <div class=\"content\">
        <div class=\"card\">
          <ul>{bullets_html}</ul>
        </div>
        <div class=\"image-wrap\">{right_block}</div>
      </div>
    </div>
  </body>
</html>"""

    def _normalize_layout(self, layout_hint: str) -> str:
        lowered = str(layout_hint).strip().lower().replace(" ", "_").replace("+", "_")
        if lowered in _LAYOUT_ALIASES:
            return _LAYOUT_ALIASES[lowered]
        if "two" in lowered and "column" in lowered:
            return "two_columns"
        if "chart" in lowered:
            return "chart_insights"
        if "image" in lowered:
            return "full_image_caption"
        if "title" in lowered and "only" in lowered:
            return "title_only"
        return "title_bullets"

    def _generate_scenario_with_fallback(
        self,
        prompt: str,
        slide_count: int,
        work_type: str,
        show_script: bool,
        scenario_model: str | None,
        scenario_network_id: str | None,
        file_keys: list[str],
        file_hints: list[dict],
        errors: list[str],
    ) -> dict:
        for attempt in range(1, 4):
            try:
                scenario = self._generate_scenario_llm(
                    prompt=prompt,
                    slide_count=slide_count,
                    work_type=work_type,
                    show_script=show_script,
                    scenario_model=scenario_model,
                    scenario_network_id=scenario_network_id,
                    file_keys=file_keys,
                    file_hints=file_hints,
                )
                normalized = self._normalize_scenario(
                    scenario=scenario,
                    slide_count=slide_count,
                    prompt=prompt,
                    work_type=work_type,
                    show_script=show_script,
                    file_keys=file_keys,
                )
                self._apply_prompt_asset_directives(
                    scenario=normalized,
                    prompt=prompt,
                    file_keys=file_keys,
                    file_hints=file_hints,
                )
                if self._scenario_looks_low_quality(normalized, prompt):
                    errors.append(f"Scenario attempt {attempt} rejected by quality gate.")
                    continue
                return normalized
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Scenario attempt {attempt} failed: {exc}")

        return self._fallback_scenario(prompt, slide_count, work_type, show_script, file_keys, file_hints)

    def build_slide_html_preview(
        self,
        slide_data: dict,
        *,
        global_style: dict,
        worker_mode: str,
        worker_model: str | None,
        worker_network_id: str | None,
        file_key_to_path: dict[str, Path],
        allow_image_generation: bool,
        presentation_id: str,
        errors: list[str],
    ) -> str:
        image_paths, slot_to_path = self._resolve_slide_assets(
            presentation_id=presentation_id,
            slide_index=slide_data.get("index", 0) or 0,
            slide_data=slide_data,
            file_key_to_path=file_key_to_path,
            allow_image_generation=allow_image_generation,
            errors=errors,
            error_prefix="Preview",
        )
        _ = image_paths
        image_data_by_slot = self._build_image_slot_data_map(slot_to_path)
        return self._generate_slide_html_with_fallback(
            slide_data=slide_data,
            global_style=global_style,
            image_data_by_slot=image_data_by_slot,
            slide_index=slide_data.get("index", 0) or 0,
            worker_mode=worker_mode,
            worker_model=worker_model,
            worker_network_id=worker_network_id,
            errors=errors,
        )

    def _generate_scenario_llm(
        self,
        prompt: str,
        slide_count: int,
        work_type: str,
        show_script: bool,
        scenario_model: str | None,
        scenario_network_id: str | None,
        file_keys: list[str],
        file_hints: list[dict],
    ) -> dict:
        instruction = build_master_scenario_prompt(
            prompt=prompt,
            slide_count=slide_count,
            work_type=work_type,
            show_script=show_script,
            file_keys=file_keys,
            file_hints=file_hints,
        )
        answer = self._genai.ask_text(
            GenAITextRequest(
                question=instruction,
                model=scenario_model,
                network_id=scenario_network_id,
            )
        ).answer
        return self._extract_json(answer)

    def _extract_json(self, text: str) -> dict:
        stripped = self._strip_markdown_fences(text).strip()
        if not stripped:
            raise ValueError("Empty model response.")

        direct = self._parse_dict_like_json(stripped)
        if direct is not None:
            return direct

        match = re.search(r"\{[\s\S]*\}", stripped, flags=re.DOTALL)
        if match:
            candidate = match.group(0).strip()
            parsed_match = self._parse_dict_like_json(candidate)
            if parsed_match is not None:
                return parsed_match

        raise ValueError("JSON object not found in model response.")

    def _parse_dict_like_json(self, text: str) -> dict | None:
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except Exception:  # noqa: BLE001
                continue

            candidate = self._find_scenario_dict(parsed)
            if candidate is not None:
                return candidate
        return None

    def _find_scenario_dict(self, node: object) -> dict | None:
        if isinstance(node, dict):
            if isinstance(node.get("slides"), list):
                return node

            for key in ("content", "text", "answer", "output", "response"):
                if key in node and isinstance(node.get(key), str):
                    parsed = self._parse_dict_like_json(str(node.get(key)))
                    if parsed is not None:
                        return parsed

            for value in node.values():
                found = self._find_scenario_dict(value)
                if found is not None:
                    return found
            return None

        if isinstance(node, list):
            for item in node:
                found = self._find_scenario_dict(item)
                if found is not None:
                    return found
            return None

        if isinstance(node, str) and "{" in node and "}" in node and "slides" in node.lower():
            return self._parse_dict_like_json(node)
        return None

    def _normalize_scenario(
        self,
        scenario: dict,
        slide_count: int,
        prompt: str,
        work_type: str,
        show_script: bool,
        file_keys: list[str],
    ) -> dict:
        slides = scenario.get("slides")
        if not isinstance(slides, list):
            slides = []

        global_style = self._normalize_global_style(scenario.get("globalStyle", {}), work_type)
        topic = self._extract_topic_label(prompt)
        content_mode = self._infer_content_mode(prompt)
        slide_topic_directives = self._extract_slide_topic_directives(prompt)
        requested_titles = {title.strip().lower() for title in self._extract_requested_slide_titles(prompt)}
        focus_points = self._extract_focus_points(prompt)

        normalized: list[dict] = []
        seen_signatures: set[str] = set()
        for index in range(slide_count):
            raw = slides[index] if index < len(slides) and isinstance(slides[index], dict) else {}
            raw_layout = raw.get("layoutHint") or raw.get("layout")
            if raw_layout:
                layout = self._normalize_layout(raw_layout)
            else:
                layout_cycle = ["title_bullets", "two_columns", "chart_insights", "full_image_caption"]
                layout = layout_cycle[index % len(layout_cycle)]

            normalized_content = self._normalize_slide_content(
                raw=raw,
                prompt=prompt,
                topic=topic,
                requested_titles=requested_titles,
                focus_points=focus_points,
                slide_index=index + 1,
                slide_count=slide_count,
                content_mode=content_mode,
                slide_topic=slide_topic_directives.get(index + 1),
            )
            title = normalized_content["title"]
            subtitle = normalized_content["subtitle"]
            main_text = normalized_content["mainText"]
            bullets = normalized_content["bullets"]
            kicker = normalized_content["kicker"]

            signature = "|".join([title.strip().lower(), main_text.strip().lower(), "||".join(bullets)])
            if signature in seen_signatures:
                kind = self._classify_phase_kind(
                    title=title,
                    slide_index=index + 1,
                    slide_count=slide_count,
                    mode=content_mode,
                )
                fallback_phase = self._build_fallback_phase(
                    topic=topic,
                    title=f"{title} — часть {index + 1}",
                    kind=kind,
                    slide_index=index + 1,
                    slide_count=slide_count,
                    style_hint=self._extract_style_hint(prompt),
                    focus_points=focus_points,
                    mode=content_mode,
                    slide_topic=slide_topic_directives.get(index + 1),
                )
                title = fallback_phase["title"]
                main_text = fallback_phase["main_text"]
                bullets = fallback_phase["bullets"]
                kicker = fallback_phase["kicker"]
                signature = "|".join([title.strip().lower(), main_text.strip().lower(), "||".join(bullets)])

            seen_signatures.add(signature)
            speaker_notes = ""
            if show_script:
                speaker_notes = self._normalize_speaker_notes(
                    raw_notes=str(raw.get("speakerNotes") or ""),
                    title=title,
                    main_text=main_text,
                    bullets=bullets,
                    slide_index=index + 1,
                )

            normalized.append(
                {
                    "title": title,
                    "subtitle": subtitle,
                    "mainText": main_text,
                    "bullets": bullets,
                    "kicker": kicker,
                    "layoutHint": layout,
                    "style": self._normalize_slide_style(
                        raw.get("style") if isinstance(raw.get("style"), dict) else {},
                        raw.get("visual") if isinstance(raw.get("visual"), dict) else {},
                        global_style,
                        index,
                    ),
                    "composition": self._normalize_composition(raw.get("composition"), layout, index),
                    "assets": self._normalize_assets(raw.get("assets"), file_keys),
                    "speakerNotes": speaker_notes,
                }
            )

        return {
            "architectureVersion": "master_worker_v2",
            "globalStyle": global_style,
            "slides": normalized,
        }

    def _normalize_slide_content(
        self,
        *,
        raw: dict,
        prompt: str,
        topic: str,
        requested_titles: set[str],
        focus_points: list[str],
        slide_index: int,
        slide_count: int,
        content_mode: str,
        slide_topic: str | None,
    ) -> dict:
        raw_title = self._truncate_text(str(raw.get("title") or "").strip(), 96)
        raw_subtitle = self._truncate_text(str(raw.get("subtitle") or "").strip(), 140)
        raw_main_text = self._truncate_text(str(raw.get("mainText") or raw.get("text") or "").strip(), 460)
        raw_bullets = [
            self._truncate_text(str(item).strip(), 140)
            for item in (raw.get("bullets") or [])
            if str(item).strip()
        ][:8]
        raw_kicker = self._truncate_text(str(raw.get("kicker") or "").strip().lower(), 40)

        default_titles = self._default_phase_titles(
            mode=content_mode,
            topic=topic,
            slide_count=slide_count,
            slide_topic_directives={slide_index: slide_topic} if slide_topic else {},
        )
        default_title = default_titles[(slide_index - 1) % len(default_titles)]
        title_for_kind = raw_title or default_title
        if raw_title and self._looks_like_meta_instruction(raw_title) and raw_title.lower() not in requested_titles:
            title_for_kind = default_title
        kind = self._classify_phase_kind(
            title=title_for_kind,
            slide_index=slide_index,
            slide_count=slide_count,
            mode=content_mode,
        )
        fallback_phase = self._build_fallback_phase(
            topic=topic,
            title=title_for_kind,
            kind=kind,
            slide_index=slide_index,
            slide_count=slide_count,
            style_hint=self._extract_style_hint(prompt),
            focus_points=focus_points,
            mode=content_mode,
            slide_topic=slide_topic,
        )

        title_lower = raw_title.lower()
        is_requested_title = title_lower in requested_titles
        title = raw_title
        if not title or (self._looks_like_meta_instruction(raw_title) and not is_requested_title):
            title = fallback_phase["title"]

        subtitle = raw_subtitle
        if subtitle and self._looks_like_meta_instruction(subtitle):
            subtitle = ""

        main_text = raw_main_text
        if (
            not main_text
            or self._looks_like_meta_instruction(main_text)
            or self._looks_like_prompt_dump(main_text)
            or len(main_text) < 45
        ):
            main_text = fallback_phase["main_text"]

        bullets = [
            bullet for bullet in raw_bullets
            if not self._looks_like_meta_instruction(bullet) and not self._looks_like_prompt_dump(bullet)
        ]
        if len(bullets) < 3:
            bullets = fallback_phase["bullets"]

        kicker = raw_kicker
        if not kicker or self._looks_like_meta_instruction(kicker):
            kicker = fallback_phase["kicker"]

        return {
            "title": title,
            "subtitle": subtitle,
            "mainText": self._truncate_text(main_text, 360),
            "bullets": [self._truncate_text(item, 120) for item in bullets[:6]],
            "kicker": kicker,
        }

    def _looks_like_meta_instruction(self, text: str) -> bool:
        lowered = text.strip().lower()
        if not lowered:
            return False

        markers = [
            "контекст и цель",
            "что нужно донести аудитории",
            "почему тема важна сейчас",
            "какой итог считаем успешным",
            "разбираем тему",
            "формулируем цель презентации",
            "инструкция",
            "как сделать презентацию",
            "как сделать слайд",
            "show_script",
            "speaker notes",
            "объясни структуру презентации",
        ]
        return any(marker in lowered for marker in markers)

    def _looks_like_prompt_dump(self, text: str) -> bool:
        lowered = text.strip().lower()
        if not lowered:
            return False
        markers = [
            "контекст проекта",
            "требования к изображениям",
            "слайды (минимум)",
            "дополнительно",
            "монорепозиторий",
            "backend (fastapi)",
            "frontend (nuxt)",
            "пользователь вводит тему",
        ]
        too_long_for_slide = len(lowered) > 320 and any(marker in lowered for marker in markers)
        return any(marker in lowered for marker in markers) or too_long_for_slide

    def _apply_palette_variation(self, style: dict, slide_index: int) -> dict:
        variants = [
            {"primary": "#5d7cff", "accent": "#ff5d9a", "surface": "#121a36"},
            {"primary": "#22c55e", "accent": "#f59e0b", "surface": "#142433"},
            {"primary": "#06b6d4", "accent": "#f97316", "surface": "#12293a"},
            {"primary": "#a855f7", "accent": "#38bdf8", "surface": "#231636"},
        ]
        variant = variants[slide_index % len(variants)]
        updated = dict(style)
        palette = dict(style.get("palette", {}))
        for key, value in variant.items():
            palette.setdefault(key, value)
        # If model did not customize colors (still default), rotate them by slide index.
        if slide_index > 0 and palette.get("primary") == _DEFAULT_GLOBAL_STYLE["palette"]["primary"]:
            palette["primary"] = variant["primary"]
        if slide_index > 0 and palette.get("accent") == _DEFAULT_GLOBAL_STYLE["palette"]["accent"]:
            palette["accent"] = variant["accent"]
        if slide_index > 0 and palette.get("surface") == _DEFAULT_GLOBAL_STYLE["palette"]["surface"]:
            palette["surface"] = variant["surface"]
        updated["palette"] = palette
        return updated

    def _vary_blocks(self, blocks: list[dict], slide_index: int) -> list[dict]:
        if slide_index <= 0:
            return blocks
        x_shift_cycle = [0, 8, -10, 14, -6]
        radius_cycle = [0, 2, 6, 10, 14]
        x_shift = x_shift_cycle[slide_index % len(x_shift_cycle)]
        radius_bonus = radius_cycle[slide_index % len(radius_cycle)]

        varied: list[dict] = []
        for block in blocks:
            updated = dict(block)
            if updated.get("type") in {"image", "bullets", "caption"}:
                updated["radius"] = self._clamp(self._safe_int(updated.get("radius"), 0) + radius_bonus, 0, 60)
            if updated.get("type") not in {"title", "badge"}:
                updated["x"] = self._clamp(self._safe_int(updated.get("x"), 0) + x_shift, 0, 1278)
            varied.append(updated)
        return varied

    def _normalize_global_style(self, raw_style: object, work_type: str = "student") -> dict:
        style = copy.deepcopy(_DEFAULT_GLOBAL_STYLE)
        style["theme"] = f"{work_type}_deck"

        if isinstance(raw_style, dict):
            if isinstance(raw_style.get("theme"), str) and raw_style.get("theme").strip():
                style["theme"] = raw_style["theme"].strip()
            style["fontFamily"] = self._sanitize_font_family(
                raw_style.get("fontFamily") or raw_style.get("font") or style["fontFamily"]
            )
            if isinstance(raw_style.get("background"), str) and raw_style["background"].strip():
                style["background"] = raw_style["background"].strip()
            style["palette"] = self._normalize_palette(raw_style.get("palette"), style["palette"])

        return style

    def _normalize_slide_style(
        self,
        raw_style: dict,
        visual_style: dict,
        global_style: dict,
        slide_index: int = 0,
    ) -> dict:
        normalized = {
            "background": global_style["background"],
            "fontFamily": global_style["fontFamily"],
            "palette": dict(global_style["palette"]),
        }

        for source in (visual_style, raw_style):
            if not isinstance(source, dict):
                continue
            if isinstance(source.get("background"), str) and source["background"].strip():
                normalized["background"] = source["background"].strip()
            if isinstance(source.get("fontFamily"), str) and source["fontFamily"].strip():
                normalized["fontFamily"] = self._sanitize_font_family(source["fontFamily"])

            palette_override = source.get("paletteOverride")
            if palette_override is None:
                palette_override = source.get("palette")
            if palette_override is not None:
                normalized["palette"] = self._normalize_palette(palette_override, normalized["palette"])

        # Ensure visual variation across slides even when model omits per-slide styling.
        normalized = self._apply_palette_variation(normalized, slide_index)
        return normalized

    def _normalize_palette(self, raw_palette: object, fallback: dict) -> dict:
        palette = dict(fallback)

        if isinstance(raw_palette, list):
            keys_by_index = ["bg", "text", "primary", "accent", "surface", "muted", "border"]
            for index, value in enumerate(raw_palette[: len(keys_by_index)]):
                key = keys_by_index[index]
                palette[key] = self._safe_color(value, palette[key])
            return palette

        if not isinstance(raw_palette, dict):
            return palette

        mapping = {
            "bg": ["bg", "background"],
            "surface": ["surface", "card"],
            "primary": ["primary", "main"],
            "accent": ["accent", "secondary"],
            "text": ["text", "foreground"],
            "muted": ["muted", "subtle"],
            "border": ["border"],
        }

        for target, candidates in mapping.items():
            for candidate in candidates:
                if candidate in raw_palette:
                    palette[target] = self._safe_color(raw_palette.get(candidate), palette[target])
                    break

        return palette

    def _normalize_assets(self, raw_assets: object, file_keys: list[str]) -> dict:
        assets = raw_assets if isinstance(raw_assets, dict) else {}

        use_files_raw = assets.get("useFiles") if isinstance(assets.get("useFiles"), list) else []
        use_files: list[dict] = []
        for index, ref in enumerate(use_files_raw, start=1):
            if not isinstance(ref, dict):
                continue
            key = ref.get("key")
            if isinstance(key, str) and key in file_keys:
                use_files.append(
                    {
                        "key": key,
                        "slot": self._normalize_slot_name(ref.get("slot") or ref.get("usage"), f"image_{index}"),
                        "usage": str(ref.get("usage") or ""),
                    }
                )

        generate_raw = assets.get("generateImages") if isinstance(assets.get("generateImages"), list) else []
        generate_images: list[dict] = []
        for index, ref in enumerate(generate_raw[:2], start=1):
            if not isinstance(ref, dict):
                continue
            prompt = str(ref.get("prompt") or "").strip()
            if not prompt:
                continue
            generate_images.append(
                {
                    "prompt": prompt,
                    "slot": self._normalize_slot_name(
                        ref.get("slot") or ref.get("placement"),
                        f"image_gen_{index}",
                    ),
                    "purpose": str(ref.get("purpose") or ""),
                }
            )

        return {
            "useFiles": use_files,
            "generateImages": generate_images,
        }

    def _normalize_composition(self, raw_composition: object, layout: str, slide_index: int = 0) -> dict:
        blocks_raw: list[object] = []
        if isinstance(raw_composition, dict) and isinstance(raw_composition.get("blocks"), list):
            blocks_raw = raw_composition["blocks"]

        normalized_blocks: list[dict] = []
        for block in blocks_raw[:12]:
            normalized = self._normalize_block(block)
            if normalized:
                normalized_blocks.append(normalized)

        has_title = any(block["type"] == "title" for block in normalized_blocks)
        if not normalized_blocks or not has_title:
            normalized_blocks = self._default_blocks_for_layout(layout, slide_index)
        else:
            normalized_blocks = self._vary_blocks(normalized_blocks, slide_index)

        return {"blocks": normalized_blocks}

    def _normalize_block(self, raw_block: object) -> dict | None:
        if not isinstance(raw_block, dict):
            return None

        block_type = str(raw_block.get("type") or raw_block.get("kind") or "").strip().lower()
        if block_type not in _ALLOWED_BLOCK_TYPES:
            return None

        x = self._clamp(self._safe_int(raw_block.get("x"), 64), 0, 1278)
        y = self._clamp(self._safe_int(raw_block.get("y"), 48), 0, 718)

        max_w = max(40, 1280 - x)
        max_h = max(40, 720 - y)

        block = {
            "type": block_type,
            "x": x,
            "y": y,
            "w": self._clamp(self._safe_int(raw_block.get("w"), max_w), 40, max_w),
            "h": self._clamp(self._safe_int(raw_block.get("h"), max_h), 40, max_h),
            "align": (
                raw_block.get("align")
                if isinstance(raw_block.get("align"), str) and raw_block.get("align") in _ALLOWED_TEXT_ALIGN
                else "left"
            ),
            "fontSize": self._clamp(self._safe_int(raw_block.get("fontSize"), 22), 10, 92),
            "fontWeight": self._clamp(self._safe_int(raw_block.get("fontWeight"), 520), 300, 900),
            "lineHeight": self._clamp_float(self._safe_float(raw_block.get("lineHeight"), 1.3), 1.0, 1.8),
            "padding": self._clamp(self._safe_int(raw_block.get("padding"), 0), 0, 48),
            "radius": self._clamp(self._safe_int(raw_block.get("radius"), 0), 0, 60),
            "slot": self._normalize_slot_name(raw_block.get("slot") or raw_block.get("imageSlot"), "image_primary"),
        }

        bg = self._safe_color(raw_block.get("background"), "")
        border = self._safe_color(raw_block.get("border"), "")
        color = self._safe_color(raw_block.get("color"), "")

        if bg:
            block["background"] = bg
        if border:
            block["border"] = border
        if color:
            block["color"] = color

        return block

    def _default_blocks_for_layout(self, layout: str, slide_index: int = 0) -> list[dict]:
        template = _DEFAULT_BLOCKS_BY_LAYOUT.get(layout) or _DEFAULT_BLOCKS_BY_LAYOUT["title_bullets"]
        return self._vary_blocks([dict(block) for block in template], slide_index)

    def _fallback_scenario(
        self,
        prompt: str,
        slide_count: int,
        work_type: str,
        show_script: bool,
        file_keys: list[str],
        file_hints: list[dict],
    ) -> dict:
        global_style = self._normalize_global_style({}, work_type)
        slides: list[dict] = []
        phase_pool = self._build_fallback_phase_pool(prompt=prompt, slide_count=slide_count)
        file_descriptor_map = self._build_file_descriptor_map(file_keys=file_keys, file_hints=file_hints)

        for index in range(1, slide_count + 1):
            layout = "two_columns" if index % 2 == 0 else "title_bullets"
            use_files: list[dict] = []
            generate_images: list[dict] = []
            phase = phase_pool[index - 1] if index - 1 < len(phase_pool) else {
                "kicker": "analysis",
                "title": f"Раздел {index}: практическая детализация",
                "main_text": (
                    f"Уточняем, как тема «{self._extract_topic_label(prompt)}» реализуется на практике "
                    "и какие действия дают измеримый эффект."
                ),
                "bullets": [
                    "Приоритетные действия на текущем этапе",
                    "Риски и способы контроля качества",
                    "Метрики, по которым оцениваем прогресс",
                ],
            }

            slide_context = " ".join([phase["title"], phase["main_text"], " ".join(phase["bullets"])])
            selected_key = self._choose_file_key_for_text(
                text=slide_context,
                file_descriptor_map=file_descriptor_map,
            )
            if selected_key:
                use_files.append({"key": selected_key, "slot": "image_primary", "usage": "illustration"})
            else:
                generate_images.append(
                    {
                        "prompt": f"{prompt}. {phase['title']}. Clean, clear illustration for presentation slide.",
                        "slot": "image_primary",
                        "purpose": "supporting visual",
                    }
                )

            slides.append(
                {
                    "title": phase["title"],
                    "subtitle": "",
                    "mainText": phase["main_text"],
                    "bullets": phase["bullets"],
                    "kicker": phase["kicker"],
                    "layoutHint": layout,
                    "style": {
                        "background": global_style["background"],
                        "fontFamily": global_style["fontFamily"],
                        "palette": dict(global_style["palette"]),
                    },
                    "composition": {"blocks": self._default_blocks_for_layout(layout, index - 1)},
                    "assets": {
                        "useFiles": use_files,
                        "generateImages": generate_images,
                    },
                    "speakerNotes": self._build_contextual_speaker_notes(
                        title=phase["title"],
                        main_text=phase["main_text"],
                        bullets=phase["bullets"],
                        slide_index=index,
                    ) if show_script else "",
                }
            )

        scenario = {
            "architectureVersion": "master_worker_v2",
            "globalStyle": global_style,
            "slides": slides,
        }
        self._apply_prompt_asset_directives(
            scenario=scenario,
            prompt=prompt,
            file_keys=file_keys,
            file_hints=file_hints,
        )
        return scenario

    def _build_fallback_phase_pool(self, *, prompt: str, slide_count: int) -> list[dict]:
        topic = self._extract_topic_label(prompt)
        content_mode = self._infer_content_mode(prompt)
        slide_topic_directives = self._extract_slide_topic_directives(prompt)
        requested_titles = self._extract_requested_slide_titles(prompt)
        style_hint = self._extract_style_hint(prompt)
        focus_points = self._extract_focus_points(prompt)

        if requested_titles:
            titles = requested_titles[:slide_count]
            default_titles = self._default_phase_titles(
                mode=content_mode,
                topic=topic,
                slide_count=slide_count,
                slide_topic_directives=slide_topic_directives,
            )
            cursor = 0
            while len(titles) < slide_count:
                candidate = default_titles[cursor % len(default_titles)]
                cursor += 1
                if candidate not in titles:
                    titles.append(candidate)
        else:
            base_titles = self._default_phase_titles(
                mode=content_mode,
                topic=topic,
                slide_count=slide_count,
                slide_topic_directives=slide_topic_directives,
            )
            titles = base_titles[:slide_count]
            while len(titles) < slide_count:
                extra_title = f"Практический блок {len(titles) + 1}"
                titles.append(extra_title)

        phases: list[dict] = []
        for index, title in enumerate(titles, start=1):
            kind = self._classify_phase_kind(
                title=title,
                slide_index=index,
                slide_count=slide_count,
                mode=content_mode,
            )
            phases.append(
                self._build_fallback_phase(
                    topic=topic,
                    title=title,
                    kind=kind,
                    slide_index=index,
                    slide_count=slide_count,
                    style_hint=style_hint,
                    focus_points=focus_points,
                    mode=content_mode,
                    slide_topic=slide_topic_directives.get(index),
                )
            )
        return phases

    def _extract_topic_label(self, prompt: str) -> str:
        normalized = re.sub(r"\s+", " ", prompt).strip()
        if not normalized:
            return "заданная тема"

        explicit_topic = re.search(
            r"(?:тема|topic)\s*[:\-]\s*([^.!?\n]{4,140})",
            prompt,
            flags=re.IGNORECASE,
        )
        if explicit_topic:
            return explicit_topic.group(1).strip(" -:;,.")

        about_match = re.search(
            r"(?:про|about)\s+([^.!?\n]{4,140})",
            prompt,
            flags=re.IGNORECASE,
        )
        if about_match:
            candidate = about_match.group(1)
            candidate = re.split(
                r"\b(?:контекст|требования|слайды|дополнительно|style|requirements)\b",
                candidate,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            candidate = candidate.strip(" -:;,.")
            if candidate:
                return candidate

        first_line = next((line.strip() for line in prompt.splitlines() if line.strip()), "")
        first_line = re.sub(
            r"^(?:сделай|напиши|подготовь|создай)\s+презентац(?:ию|ия|иям)?\s*",
            "",
            first_line,
            flags=re.IGNORECASE,
        ).strip()
        if first_line:
            return self._truncate_text(first_line, 90)
        return self._truncate_text(normalized, 90)

    def _extract_requested_slide_titles(self, prompt: str) -> list[str]:
        numbered_matches = re.finditer(
            r"(?m)^\s*\d{1,2}[)\.]\s*(.+?)\s*$",
            prompt,
        )
        titles: list[str] = []
        for match in numbered_matches:
            raw = match.group(1).strip()
            cleaned = re.sub(r"\s*[—-]\s*использовать.+$", "", raw, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*\(([^)]*)\)\s*$", "", cleaned).strip(" -:;,.")
            if cleaned:
                titles.append(cleaned)

        if len(titles) >= 2:
            return titles
        return []

    def _extract_style_hint(self, prompt: str) -> str:
        lowered = prompt.lower()
        style_markers = [
            "минималист",
            "ночн",
            "темн",
            "неон",
            "фиолет",
            "брутальн",
            "кибер",
            "retro",
            "futur",
        ]
        for marker in style_markers:
            if marker in lowered:
                return marker
        return ""

    def _extract_focus_points(self, prompt: str) -> list[str]:
        points: list[str] = []
        seen: set[str] = set()
        for line in prompt.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            cleaned = cleaned.lstrip("-•* ").strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if re.match(r"^\d{1,2}[)\.]", cleaned):
                continue
            if any(
                marker in lowered
                for marker in [
                    "контекст проекта",
                    "требования к изображениям",
                    "слайды (минимум)",
                    "дополнительно",
                    "формулируем цель презентации",
                ]
            ):
                continue
            if len(cleaned) < 18:
                continue
            normalized = self._truncate_text(cleaned.strip(" ;."), 120)
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            points.append(normalized)
            if len(points) >= 5:
                break
        return points

    def _infer_content_mode(self, prompt: str) -> str:
        lowered = prompt.lower()
        project_markers = [
            "проект",
            "сервис",
            "продукт",
            "стартап",
            "архитектур",
            "pipeline",
            "пайплайн",
            "roadmap",
            "хакатон",
            "бизнес",
            "метрик",
            "внедрен",
        ]
        if any(marker in lowered for marker in project_markers):
            return "project"
        return "subject"

    def _extract_slide_topic_directives(self, prompt: str) -> dict[int, str]:
        directives: dict[int, str] = {}
        patterns = [
            re.compile(
                r"(?P<idx>\d{1,2})\s*(?:-?й|-?ый|-?ая|-?ое)?\s*слайд[еа]?\s*(?:про|о)\s+(?P<topic>[^\n,.;:!?]{2,90})",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"(?:на|для)\s*(?P<idx>\d{1,2})\s*(?:-?й|-?ый|-?ая|-?ое)?\s*слайд[еа]?\s*(?P<topic>[^\n,.;:!?]{2,90})",
                flags=re.IGNORECASE,
            ),
            re.compile(
                r"slide\s*(?P<idx>\d{1,2})\s*(?:about|on)\s*(?P<topic>[^\n,.;:!?]{2,90})",
                flags=re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            for match in pattern.finditer(prompt):
                try:
                    idx = int(match.group("idx"))
                except Exception:  # noqa: BLE001
                    continue
                if idx < 1 or idx > 20:
                    continue
                topic = self._truncate_text(match.group("topic").strip(" -:;,.").strip(), 90)
                if topic:
                    directives[idx] = topic
        return directives

    def _default_phase_titles(
        self,
        *,
        mode: str,
        topic: str,
        slide_count: int,
        slide_topic_directives: dict[int, str],
    ) -> list[str]:
        if mode == "project":
            titles = [
                "Титульный слайд",
                "Проблема и контекст",
                "Ключевая идея",
                "Как это работает",
                "Архитектура решения",
                "План внедрения",
                "Демонстрация",
                "Ценность и эффект",
                "Риски и ограничения",
                "Итоги и следующие шаги",
            ]
        else:
            titles = [
                f"{topic}: вводная часть",
                "Ключевые характеристики темы",
                "Классификация и основные виды",
                "Глубокий разбор важного аспекта",
                "Примеры и наблюдения",
                "Значение темы в реальной жизни",
                "Сравнение подходов и точек зрения",
                "Проблемы и спорные вопросы",
                "Текущие тренды и развитие",
                "Итоги и выводы",
            ]

        for index, directive_topic in slide_topic_directives.items():
            if 1 <= index <= len(titles):
                if mode == "project":
                    titles[index - 1] = f"Фокус: {directive_topic}"
                else:
                    titles[index - 1] = f"{directive_topic}: ключевые факты"

        return titles[: max(1, slide_count)]

    def _classify_phase_kind(self, *, title: str, slide_index: int, slide_count: int, mode: str = "project") -> str:
        lowered = title.lower()
        if slide_index == 1 or any(token in lowered for token in ["титул", "title", "обзор", "введение"]):
            return "title"
        if slide_index == slide_count or any(token in lowered for token in ["итог", "финал", "спасибо", "заключ"]):
            return "final"
        if mode != "project":
            if any(token in lowered for token in ["классиф", "вид", "тип"]):
                return "taxonomy"
            if any(token in lowered for token in ["пример", "наблюден", "кейс", "сравнен"]):
                return "examples"
            if any(token in lowered for token in ["значени", "роль", "влияни"]):
                return "impact"
            if any(token in lowered for token in ["проблем", "спорн", "огранич", "риск"]):
                return "challenges"
            if any(token in lowered for token in ["тренд", "развит", "перспектив"]):
                return "trends"
            if slide_index == 2:
                return "fundamentals"
            if slide_index == 3:
                return "taxonomy"
            if slide_index == 4:
                return "deep_dive"
            if slide_index == 5:
                return "examples"
            return "analysis"

        if any(token in lowered for token in ["проблем", "боль", "огранич"]):
            return "problem"
        if any(token in lowered for token in ["идея", "решени", "подход"]):
            return "solution"
        if any(token in lowered for token in ["архитект", "структур", "схем"]):
            return "architecture"
        if any(token in lowered for token in ["демо", "демонстрац", "пример", "кейс"]):
            return "demo"
        if any(token in lowered for token in ["план", "roadmap", "этап", "внедрен"]):
            return "roadmap"
        if any(token in lowered for token in ["ценност", "эффект", "метрик", "результ"]):
            return "value"
        if any(token in lowered for token in ["риск", "огранич", "сложност"]):
            return "risks"
        if any(token in lowered for token in ["как это работает", "пайплайн", "pipeline", "процесс"]):
            return "pipeline"
        return "analysis"

    def _build_fallback_phase(
        self,
        *,
        topic: str,
        title: str,
        kind: str,
        slide_index: int,
        slide_count: int,
        style_hint: str,
        focus_points: list[str],
        mode: str,
        slide_topic: str | None = None,
    ) -> dict:
        focus_primary = focus_points[0] if focus_points else f"Практический фокус по теме «{topic}»"
        focus_secondary = focus_points[1] if len(focus_points) > 1 else "Ключевые критерии качества результата"
        style_note = ""
        if style_hint:
            style_note = (
                " Визуальный тон слайда должен поддерживать выбранную стилистику, "
                "чтобы текст и образ работали как единое сообщение."
            )

        if mode == "project":
            templates = {
                "title": {
                    "kicker": "overview",
                    "main": (
                        f"Презентация раскрывает тему «{topic}»: какую задачу мы решаем, "
                        "почему это важно и каким должен быть итоговый результат."
                    ),
                    "bullets": [
                        f"Фокус выступления: {focus_primary}",
                        "Логика: от проблемы к рабочему решению",
                        "Финальный результат и план действий",
                    ],
                },
                "problem": {
                    "kicker": "problem",
                    "main": (
                        f"По теме «{topic}» есть конкретные проблемы, которые тормозят результат: "
                        "нестабильный процесс, лишние затраты времени и высокий риск ошибок."
                    ),
                    "bullets": [
                        "Что работает медленно или непредсказуемо",
                        "Где чаще всего теряется качество",
                        "Почему проблему нужно решать сейчас",
                    ],
                },
                "solution": {
                    "kicker": "solution",
                    "main": (
                        f"Предлагаемый подход по теме «{topic}» строится вокруг прозрачного процесса: "
                        "четкие входные данные, проверяемые шаги и измеримый выход."
                    ),
                    "bullets": [
                        "Описываем целевую модель работы",
                        "Выделяем ключевые компоненты решения",
                        "Фиксируем критерии готовности",
                    ],
                },
                "architecture": {
                    "kicker": "architecture",
                    "main": (
                        f"Архитектура решения для «{topic}» показывает, как связаны данные, "
                        "логика принятия решений и визуальный результат на каждом шаге."
                    ),
                    "bullets": [
                        "Основные модули и их роль",
                        "Поток данных между этапами",
                        "Точки контроля качества",
                    ],
                },
                "pipeline": {
                    "kicker": "pipeline",
                    "main": (
                        f"Рабочий пайплайн по теме «{topic}» проходит путь от запроса к финальному результату "
                        "через предсказуемые этапы обработки."
                    ),
                    "bullets": [
                        "Подготовка и уточнение входного запроса",
                        "Генерация структуры и контента слайдов",
                        "Проверка качества и выпуск результата",
                    ],
                },
                "demo": {
                    "kicker": "demo",
                    "main": (
                        f"На демонстрации показываем, как тема «{topic}» работает на реальном примере: "
                        "с чем стартуем, что меняем и какой результат получаем на выходе."
                    ),
                    "bullets": [
                        "Входные данные и условия кейса",
                        "Промежуточные шаги реализации",
                        "Итог и наблюдаемый эффект",
                    ],
                },
                "roadmap": {
                    "kicker": "roadmap",
                    "main": (
                        f"Для развития решения по теме «{topic}» фиксируем план с четкими этапами, "
                        "приоритетами и контрольными точками."
                    ),
                    "bullets": [
                        "Ближайшие задачи на 2-4 недели",
                        "Среднесрочные улучшения и масштабирование",
                        "Метрики выполнения плана",
                    ],
                },
                "value": {
                    "kicker": "value",
                    "main": (
                        f"Ценность подхода в теме «{topic}» измеряется не абстрактно, "
                        "а через скорость, качество и предсказуемость итогового результата."
                    ),
                    "bullets": [
                        "Какие затраты сокращаются",
                        "Где снижается вероятность ошибок",
                        "Какие показатели улучшаются",
                    ],
                },
                "risks": {
                    "kicker": "risks",
                    "main": (
                        f"Риски в теме «{topic}» связаны с качеством входных данных, "
                        "пограничными кейсами и отсутствием единых стандартов контроля."
                    ),
                    "bullets": [
                        "Пределы применимости подхода",
                        "Критичные зависимости и ограничения",
                        "План снижения рисков",
                    ],
                },
                "final": {
                    "kicker": "final",
                    "main": (
                        f"Итог по теме «{topic}»: мы получили структурный план работы, определили ключевые метрики "
                        "и зафиксировали следующий практический шаг."
                    ),
                    "bullets": [
                        "Ключевой вывод презентации",
                        f"Главный акцент: {focus_secondary}",
                        "Следующее действие после защиты",
                    ],
                },
                "analysis": {
                    "kicker": "analysis",
                    "main": (
                        f"Раздел «{title}» уточняет предметные детали темы «{topic}» "
                        "и переводит обсуждение в набор конкретных решений."
                    ),
                    "bullets": [
                        "Что важно учесть в этом разделе",
                        f"Практический фокус: {focus_primary}",
                        "Как проверяем результат на практике",
                    ],
                },
            }
        else:
            templates = {
                "title": {
                    "kicker": "overview",
                    "main": (
                        f"Открываем тему «{topic}»: определяем, что именно изучаем, "
                        "какие вопросы ключевые и почему тема важна сегодня."
                    ),
                    "bullets": [
                        "Короткое определение и границы темы",
                        "Какие аспекты разберем по ходу презентации",
                        "Какой вывод должен остаться у аудитории",
                    ],
                },
                "fundamentals": {
                    "kicker": "facts",
                    "main": (
                        f"Фиксируем базовые характеристики темы «{topic}», "
                        "чтобы аудитория понимала фундамент и терминологию."
                    ),
                    "bullets": [
                        "Ключевые признаки и свойства",
                        "Что считается нормой и почему",
                        "Какие заблуждения встречаются чаще всего",
                    ],
                },
                "taxonomy": {
                    "kicker": "structure",
                    "main": (
                        f"Разбираем, как тема «{topic}» делится на виды и категории, "
                        "и чем они отличаются друг от друга."
                    ),
                    "bullets": [
                        "Основные группы и критерии разделения",
                        "Краткие отличия между группами",
                        "Когда используется каждый вариант",
                    ],
                },
                "deep_dive": {
                    "kicker": "deep-dive",
                    "main": (
                        f"Делаем углубленный разбор по теме «{topic}»: "
                        "смотрим важные детали, которые влияют на понимание предмета."
                    ),
                    "bullets": [
                        "Ключевые механизмы или процессы",
                        "Что влияет на результат сильнее всего",
                        "Типичные ошибки интерпретации",
                    ],
                },
                "examples": {
                    "kicker": "examples",
                    "main": (
                        f"Показываем тему «{topic}» через конкретные примеры, "
                        "чтобы теория стала понятной и прикладной."
                    ),
                    "bullets": [
                        "Реальный или типовой пример",
                        "Что видно на практике",
                        "Какой вывод можно применить сразу",
                    ],
                },
                "impact": {
                    "kicker": "impact",
                    "main": (
                        f"Оцениваем влияние темы «{topic}» на людей, среду и решения, "
                        "которые принимаются в реальной жизни."
                    ),
                    "bullets": [
                        "Почему тема важна для общества",
                        "Где тема влияет на повседневные решения",
                        "Какие эффекты заметны в долгую",
                    ],
                },
                "challenges": {
                    "kicker": "challenges",
                    "main": (
                        f"Отмечаем спорные и сложные моменты в теме «{topic}», "
                        "чтобы показать ограничения и точки для дальнейшего изучения."
                    ),
                    "bullets": [
                        "Какие вопросы остаются открытыми",
                        "Где есть противоречивые оценки",
                        "Что требует дополнительной проверки",
                    ],
                },
                "trends": {
                    "kicker": "trends",
                    "main": (
                        f"Показываем, как тема «{topic}» меняется со временем, "
                        "и какие направления развития сейчас наиболее заметны."
                    ),
                    "bullets": [
                        "Текущие тренды и новые подходы",
                        "Что может измениться в ближайшие годы",
                        "На что стоит обращать внимание дальше",
                    ],
                },
                "final": {
                    "kicker": "final",
                    "main": (
                        f"Подводим итог по теме «{topic}»: закрепляем ключевые идеи "
                        "и формулируем практический вывод для аудитории."
                    ),
                    "bullets": [
                        "Главный вывод презентации",
                        f"Что важно запомнить: {focus_secondary}",
                        "Какие вопросы стоит изучить дальше",
                    ],
                },
                "analysis": {
                    "kicker": "analysis",
                    "main": (
                        f"Слайд «{title}» дополняет картину по теме «{topic}» "
                        "и помогает связать факты в цельное понимание."
                    ),
                    "bullets": [
                        "Ключевой факт этого раздела",
                        "Почему это важно для общей картины",
                        "К какому выводу нас это приводит",
                    ],
                },
            }

        if slide_topic:
            normalized_topic = self._truncate_text(slide_topic, 80)
            topic_focus_template = {
                "kicker": templates.get(kind, templates["analysis"])["kicker"],
                "main": (
                    f"Фокус слайда: «{normalized_topic}» в контексте темы «{topic}». "
                    "Разбираем ключевые особенности, значимые факты и практические выводы."
                ),
                "bullets": [
                    f"Что важно знать про «{normalized_topic}»",
                    "Какие характеристики выделяют этот аспект",
                    "Как этот фокус связан с общей темой",
                ],
            }
            template = topic_focus_template
        else:
            template = templates.get(kind, templates["analysis"])
        main_text = f"{template['main']}{style_note}"
        bullets = [self._truncate_text(item, 120) for item in template["bullets"]]

        return {
            "kicker": template["kicker"],
            "title": title,
            "main_text": self._truncate_text(main_text, 360),
            "bullets": bullets,
        }

    def _normalize_speaker_notes(
        self,
        *,
        raw_notes: str,
        title: str,
        main_text: str,
        bullets: list[str],
        slide_index: int,
    ) -> str:
        notes = raw_notes.strip()
        if notes and not self._is_placeholder_speaker_notes(notes):
            return notes
        return self._build_contextual_speaker_notes(
            title=title,
            main_text=main_text,
            bullets=bullets,
            slide_index=slide_index,
        )

    def _is_placeholder_speaker_notes(self, notes: str) -> bool:
        lowered = notes.strip().lower()
        placeholder_patterns = [
            "balanced detail and practical examples",
            "discuss slide",
            "simple explanation, fewer terms",
            "formal tone with deeper analysis",
            "slide 1",
            "slide 2",
            "slide 3",
            "slide 4",
            "slide 5",
        ]
        return any(pattern in lowered for pattern in placeholder_patterns)

    def _build_contextual_speaker_notes(
        self,
        *,
        title: str,
        main_text: str,
        bullets: list[str],
        slide_index: int,
    ) -> str:
        safe_title = title.strip() or f"Слайд {slide_index}"
        safe_main = main_text.strip()
        top_bullets = [item.strip() for item in bullets if item.strip()][:2]

        lines: list[str] = [f"На слайде {slide_index} раскройте тему: «{safe_title}»."]
        if safe_main:
            lines.append(f"Ключевой тезис: {self._truncate_text(safe_main, 180)}")
        if top_bullets:
            lines.append(f"Сделайте акцент на пунктах: {', '.join(top_bullets)}.")
        else:
            lines.append("Завершите слайд коротким практическим выводом.")
        return " ".join(lines)

    def _truncate_text(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return f"{text[: max_length - 1].rstrip()}…"

    def _scenario_looks_low_quality(self, scenario: dict, prompt: str) -> bool:
        slides = scenario.get("slides")
        if not isinstance(slides, list) or not slides:
            return True

        titles: list[str] = []
        signatures: list[str] = []
        prompt_tokens = self._extract_prompt_tokens(prompt)
        prompt_hits = 0
        meaningful_main_text = 0
        instructional_hits = 0
        prompt_dump_hits = 0
        very_long_main_text_hits = 0

        for slide in slides:
            if not isinstance(slide, dict):
                return True
            title = str(slide.get("title") or "").strip()
            main_text = str(slide.get("mainText") or "").strip()
            bullets = [str(item).strip() for item in (slide.get("bullets") or []) if str(item).strip()]
            combined = f"{title} {main_text} {' '.join(bullets)}".strip().lower()
            signatures.append(combined)
            titles.append(title.lower())
            if len(main_text) >= 35:
                meaningful_main_text += 1
            if prompt_tokens and any(token in combined for token in prompt_tokens):
                prompt_hits += 1
            if len(main_text) > 360:
                very_long_main_text_hits += 1
            if self._looks_like_meta_instruction(combined):
                instructional_hits += 1
            if self._looks_like_prompt_dump(combined):
                prompt_dump_hits += 1

        unique_titles = len({item for item in titles if item})
        duplicate_ratio = 1 - (len(set(signatures)) / max(1, len(signatures)))
        too_many_duplicates = duplicate_ratio > 0.35
        poor_topic_alignment = bool(prompt_tokens) and prompt_hits < max(1, len(slides) // 4)
        weak_main_text = meaningful_main_text < max(2, len(slides) // 2)
        repeated_titles = unique_titles < max(2, len(slides) // 2)
        instructional_content = instructional_hits >= max(1, len(slides) // 4)
        prompt_dumped_to_slides = prompt_dump_hits >= 1 or very_long_main_text_hits >= max(1, len(slides) // 3)

        return (
            too_many_duplicates
            or poor_topic_alignment
            or weak_main_text
            or repeated_titles
            or instructional_content
            or prompt_dumped_to_slides
        )

    def _extract_prompt_tokens(self, prompt: str) -> list[str]:
        stop_words = {
            "и", "или", "для", "как", "что", "это", "про", "под", "без", "над", "при",
            "with", "from", "this", "that", "into", "about", "have", "will", "your",
        }
        tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]{4,}", prompt.lower())
        unique = []
        seen = set()
        for token in tokens:
            if token in stop_words:
                continue
            if token not in seen:
                seen.add(token)
                unique.append(token)
        return unique[:12]

    def _build_file_descriptor_map(
        self,
        *,
        file_keys: list[str],
        file_hints: list[dict],
    ) -> dict[str, str]:
        descriptor_map: dict[str, str] = {}
        hint_by_key: dict[str, str] = {}
        for hint in file_hints:
            if not isinstance(hint, dict):
                continue
            key = hint.get("key")
            name = hint.get("name")
            if isinstance(key, str) and key and isinstance(name, str):
                hint_by_key[key] = name

        for key in file_keys:
            descriptor_map[key] = f"{key} {hint_by_key.get(key, key)}".lower()

        return descriptor_map

    def _choose_file_key_for_text(self, *, text: str, file_descriptor_map: dict[str, str]) -> str | None:
        slide_tokens = set(self._extract_prompt_tokens(text))
        if not slide_tokens:
            return None

        best_key: str | None = None
        best_score = 0

        for key, descriptor in file_descriptor_map.items():
            descriptor_tokens = set(self._extract_prompt_tokens(descriptor))
            score = len(slide_tokens & descriptor_tokens)
            if score > best_score:
                best_score = score
                best_key = key

        return best_key if best_score > 0 else None

    def _apply_prompt_asset_directives(
        self,
        *,
        scenario: dict,
        prompt: str,
        file_keys: list[str],
        file_hints: list[dict],
    ) -> None:
        slides = scenario.get("slides")
        if not isinstance(slides, list) or not slides or not file_keys:
            return

        prompt_lower = prompt.lower()
        wants_first = any(word in prompt_lower for word in ["перв", "титул", "начал", "cover", "title slide", "first slide"])
        wants_last = any(word in prompt_lower for word in ["послед", "финал", "заключ", "end slide", "final slide", "last slide"])

        file_descriptor_map = self._build_file_descriptor_map(file_keys=file_keys, file_hints=file_hints)

        # Explicit key mention in prompt.
        for key in file_keys:
            if key.lower() not in prompt_lower:
                continue
            if wants_first:
                self._ensure_slide_has_file_key(slides[0], key)
            if wants_last:
                self._ensure_slide_has_file_key(slides[-1], key)

        # Semantic directives like "котик в начало", "меня на последний".
        cat_like = any(word in prompt_lower for word in ["кот", "котик", "cat"])
        person_like = any(word in prompt_lower for word in ["меня", "мое фото", "мою фотограф", "my photo", "me "])
        thanks_like = any(word in prompt_lower for word in ["спасибо за внимание", "thanks for attention"])

        if cat_like and wants_first:
            key = self._choose_file_key_for_text(
                text="кот котик cat animal",
                file_descriptor_map=file_descriptor_map,
            )
            if key:
                self._ensure_slide_has_file_key(slides[0], key)

        if person_like and wants_last:
            key = self._choose_file_key_for_text(
                text="person portrait selfie me моя фотография",
                file_descriptor_map=file_descriptor_map,
            )
            if not key and file_keys:
                key = file_keys[-1]
            if key:
                self._ensure_slide_has_file_key(slides[-1], key)

        if thanks_like:
            last_slide = slides[-1]
            last_slide["title"] = str(last_slide.get("title") or "Спасибо за внимание")
            if "спасибо" not in last_slide["title"].lower():
                last_slide["title"] = "Спасибо за внимание"
            if not str(last_slide.get("mainText") or "").strip():
                last_slide["mainText"] = "Спасибо за внимание!"

    def _ensure_slide_has_file_key(self, slide_data: dict, key: str) -> None:
        assets = slide_data.setdefault("assets", {})
        use_files = assets.setdefault("useFiles", [])
        if not isinstance(use_files, list):
            use_files = []
            assets["useFiles"] = use_files

        for item in use_files:
            if isinstance(item, dict) and item.get("key") == key:
                return

        use_files.append(
            {
                "key": key,
                "slot": "image_primary",
                "usage": "requested by prompt",
            }
        )

    def _strip_markdown_fences(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
            stripped = re.sub(r"\n?```$", "", stripped)
        return stripped

    def _build_image_slot_data_map(self, slot_to_path: dict[str, Path], limit: int = 4) -> dict[str, str]:
        image_data: dict[str, str] = {}
        first_data_uri: str | None = None

        for index, (slot, path) in enumerate(slot_to_path.items(), start=1):
            if index > limit:
                break
            data_uri = self._path_to_data_uri(path)
            if not data_uri:
                continue
            image_data[slot] = data_uri
            image_data.setdefault(f"image_{index}", data_uri)
            if first_data_uri is None:
                first_data_uri = data_uri

        if first_data_uri and "image_primary" not in image_data:
            image_data["image_primary"] = first_data_uri

        return image_data

    def _path_to_data_uri(self, path: Path) -> str | None:
        if not path.exists() or not path.is_file():
            return None
        content = path.read_bytes()
        if not content:
            return None
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def _normalize_slot_name(self, raw: object, fallback: str) -> str:
        if isinstance(raw, str):
            normalized = re.sub(r"[^a-z0-9_]+", "_", raw.strip().lower())
            normalized = re.sub(r"_+", "_", normalized).strip("_")
            if normalized:
                return normalized
        return fallback

    def _safe_int(self, value: object, default: int) -> int:
        try:
            return int(value)
        except Exception:  # noqa: BLE001
            return default

    def _safe_float(self, value: object, default: float) -> float:
        try:
            return float(value)
        except Exception:  # noqa: BLE001
            return default

    def _clamp(self, value: int, min_value: int, max_value: int) -> int:
        if min_value > max_value:
            return min_value
        return max(min_value, min(value, max_value))

    def _clamp_float(self, value: float, min_value: float, max_value: float) -> float:
        if min_value > max_value:
            return min_value
        return max(min_value, min(value, max_value))

    def _safe_color(self, value: object, fallback: str) -> str:
        if not isinstance(value, str):
            return fallback
        candidate = value.strip()
        if not candidate:
            return fallback
        if _HEX_COLOR_RE.match(candidate):
            return candidate
        if _RGB_COLOR_RE.match(candidate):
            return candidate
        return fallback

    def _color_with_alpha(self, color: str, alpha: float, fallback: str) -> str:
        if not isinstance(color, str):
            return fallback
        match = _HEX_COLOR_RE.match(color.strip())
        if not match:
            return fallback

        hex_color = color.strip().lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(ch * 2 for ch in hex_color)
        if len(hex_color) == 8:
            hex_color = hex_color[:6]
        if len(hex_color) != 6:
            return fallback

        red = int(hex_color[0:2], 16)
        green = int(hex_color[2:4], 16)
        blue = int(hex_color[4:6], 16)
        return f"rgba({red}, {green}, {blue}, {alpha})"

    def _sanitize_font_family(self, value: object) -> str:
        fallback = _DEFAULT_GLOBAL_STYLE["fontFamily"]
        if not isinstance(value, str):
            return fallback
        cleaned = re.sub(r"[^a-zA-Z0-9,\s\"'_-]", "", value).strip()
        return cleaned or fallback

    def _escape_html(self, value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
