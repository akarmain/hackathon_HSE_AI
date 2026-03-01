import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.features.presentations.orchestrator import PresentationOrchestrator
from app.features.presentations.schemas import CreatePresentationRequest, PresentationFileRef
from app.features.presentations.service import PresentationService
from app.features.presentations.storage import PresentationStorage
from app.main import create_app


def test_create_presentation_validates_slide_count() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/presentations",
        json={
            "prompt": "My deck",
            "slideCount": 1,
            "workType": "school",
            "showScript": True,
            "files": [],
        },
    )
    assert response.status_code == 422


def test_create_presentation_and_status_endpoint() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/presentations",
        json={
            "prompt": "Hackathon demo",
            "slideCount": 5,
            "workType": "student",
            "showScript": True,
            "files": [],
        },
    )
    assert created.status_code == 200
    data = created.json()
    assert "presentationId" in data

    status_response = client.get(f"/api/presentations/{data['presentationId']}/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["slidesTotal"] == 5
    assert len(status_data["slides"]) == 5


def test_service_saves_meta_and_scenario_and_handles_partial_errors(tmp_path: Path) -> None:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    settings = Settings(
        uploads_dir=str(uploads_dir),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    service = PresentationService(settings=settings)
    payload = CreatePresentationRequest(
        prompt="Test fallback scenario",
        slideCount=5,
        workType="school",
        showScript=True,
        files=[
            PresentationFileRef(key="logo", fileId="sample.png"),
            PresentationFileRef(key="logo", fileId="sample.png"),
        ],
    )

    created = service.create_presentation(payload, start_background=False)
    service.run_job_sync(created.presentationId, force_fail_slide_indexes={2})

    status = service.get_status(created.presentationId)
    assert status.status == "completed_with_errors"
    assert status.slidesReady >= 1
    assert len(status.slides) == 5

    job_dir = Path(settings.presentations_dir) / created.presentationId
    meta = json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    scenario = json.loads((job_dir / "scenario.json").read_text(encoding="utf-8"))

    assert meta["status"] == "completed_with_errors"
    assert (job_dir / "result.pdf").exists() or (job_dir / "result.zip").exists()
    assert len(scenario["slides"]) == 5
    assert meta["files"][0]["key"] == "logo"
    assert meta["files"][1]["key"] == "logo_2"


def test_service_ignores_hidden_file_refs_like_ds_store(tmp_path: Path) -> None:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (uploads_dir / ".DS_Store").write_bytes(b"meta")

    settings = Settings(
        uploads_dir=str(uploads_dir),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    service = PresentationService(settings=settings)
    payload = CreatePresentationRequest(
        prompt="Test hidden file filtering",
        slideCount=5,
        workType="school",
        showScript=False,
        files=[
            PresentationFileRef(key="img", fileId="sample.png"),
            PresentationFileRef(key="trash", fileId=".DS_Store"),
        ],
    )

    created = service.create_presentation(payload, start_background=False)
    meta = service._storage.load_meta(created.presentationId)
    file_ids = [item["fileId"] for item in meta["files"]]
    assert "sample.png" in file_ids
    assert ".DS_Store" not in file_ids


def test_service_keeps_unicode_file_key_descriptions(tmp_path: Path) -> None:
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "cat.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    settings = Settings(
        uploads_dir=str(uploads_dir),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    service = PresentationService(settings=settings)
    payload = CreatePresentationRequest(
        prompt="Тест ключей файлов",
        slideCount=5,
        workType="student",
        showScript=False,
        files=[PresentationFileRef(key="мой котик на улице", fileId="cat.png")],
    )

    created = service.create_presentation(payload, start_background=False)
    meta = service._storage.load_meta(created.presentationId)
    assert meta["files"][0]["key"] == "мой_котик_на_улице"


def test_fallback_scenario_builds_topic_specific_slides(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    scenario = orchestrator._fallback_scenario(
        prompt=(
            "Так напиши проект про город Мытищи в стиле ночных разбитых дорог "
            "и добавь фото котика в начало, а мое фото в финал."
        ),
        slide_count=8,
        work_type="student",
        show_script=True,
        file_keys=[],
        file_hints=[],
    )

    assert len(scenario["slides"]) == 8
    first_slide = scenario["slides"][0]
    assert "мытищ" in first_slide["mainText"].lower()
    assert first_slide["title"].lower() not in {"контекст и цель"}
    assert "формулируем цель презентации" not in first_slide["mainText"].lower()


def test_fallback_scenario_respects_slide_topic_directive(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    scenario = orchestrator._fallback_scenario(
        prompt="презентация про животных где 2 слайд про котиков",
        slide_count=5,
        work_type="student",
        show_script=False,
        file_keys=[],
        file_hints=[],
    )

    assert len(scenario["slides"]) == 5
    second = scenario["slides"][1]
    combined = f"{second['title']} {second['mainText']} {' '.join(second['bullets'])}".lower()
    assert "котик" in combined or "кот" in combined
    assert "рабочему решению" not in second["mainText"].lower()


def test_quality_gate_rejects_instructional_scenario(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    scenario = {
        "slides": [
            {
                "title": "Контекст и цель",
                "mainText": "Разбираем тему: Python. Формулируем цель презентации и ожидаемый результат.",
                "bullets": [
                    "Что нужно донести аудитории",
                    "Почему тема важна сейчас",
                    "Какой итог считаем успешным",
                ],
            }
            for _ in range(6)
        ]
    }
    assert orchestrator._scenario_looks_low_quality(scenario, "Презентация про Python") is True


def test_extract_html_document_from_wrapped_provider_payload(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    wrapped = (
        "{'status': 'success', 'result': [{'choices': [{'message': {'content': "
        "'<!doctype html><html><body><div>ok</div></body></html>'}}]}]}"
    )
    html = orchestrator._extract_html_document(wrapped)
    assert html is not None
    assert html.lower().startswith("<!doctype html>")
    assert "<div>ok</div>" in html


def test_extract_json_from_wrapped_python_dict_payload(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    wrapped = (
        "{'status': 'success', 'result': [{'choices': [{'message': {'content': "
        "'{\"slides\": [{\"title\": \"Тема\", \"mainText\": \"Текст\", \"bullets\": [\"a\", \"b\", \"c\"]}]}'"
        "}}]}]}"
    )
    parsed = orchestrator._extract_json(wrapped)
    assert "slides" in parsed
    assert isinstance(parsed["slides"], list)
    assert parsed["slides"][0]["title"] == "Тема"


def test_normalize_scenario_rewrites_meta_slide_content(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    scenario = {
        "slides": [
            {
                "title": "Контекст и цель",
                "mainText": "Разбираем тему: сервис презентаций. Формулируем цель презентации.",
                "bullets": [
                    "Что нужно донести аудитории",
                    "Почему тема важна сейчас",
                    "Какой итог считаем успешным",
                ],
                "kicker": "context",
            }
        ]
    }
    normalized = orchestrator._normalize_scenario(
        scenario=scenario,
        slide_count=1,
        prompt="Сделай презентацию про сервис генерации презентаций",
        work_type="student",
        show_script=False,
        file_keys=[],
    )

    slide = normalized["slides"][0]
    assert "формулируем цель презентации" not in slide["mainText"].lower()
    assert slide["title"].lower() != "контекст и цель"
    assert all("что нужно донести аудитории" not in item.lower() for item in slide["bullets"])


def test_inject_image_slots_rewrites_data_uri_placeholder_text(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    html = (
        "<html><head></head><body>"
        "<div class='image-placeholder'>{{image_primary}}</div>"
        "</body></html>"
    )
    hydrated = orchestrator._inject_image_slots(
        html,
        {"image_primary": "data:image/png;base64,AAAA"},
    )
    assert "{{image_primary}}" not in hydrated
    assert "image-placeholder'>data:image" not in hydrated
    assert "<img src='data:image/png;base64,AAAA'" in hydrated


def test_inject_image_slots_fills_plain_placeholder_when_image_available(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    html = (
        "<html><head></head><body>"
        "<div class='image-placeholder'>No image</div>"
        "</body></html>"
    )
    hydrated = orchestrator._inject_image_slots(
        html,
        {"image_primary": "data:image/jpeg;base64,BBBB"},
    )
    assert "<img src='data:image/jpeg;base64,BBBB'" in hydrated
    assert "No image</div>" not in hydrated


def test_enforce_worker_font_family_injects_override_style(tmp_path: Path) -> None:
    settings = Settings(
        uploads_dir=str(tmp_path / "uploads"),
        presentations_dir=str(tmp_path / "presentations"),
        genai_images_dir=str(tmp_path / "genai"),
        genai_api_key="",
    )
    storage = PresentationStorage(settings.presentations_dir)
    orchestrator = PresentationOrchestrator(settings=settings, storage=storage)

    html = "<!doctype html><html><head></head><body><div>ok</div></body></html>"
    updated = orchestrator._enforce_worker_font_family(
        html,
        "\"Trebuchet MS\", \"Avenir Next\", \"Segoe UI\", sans-serif",
    )
    assert "worker-font-override" in updated
    assert "Trebuchet MS" in updated
