# hackathon_HSE_AI

Монорепозиторий FastAPI + Nuxt для MVP генерации презентаций:
- загрузка пользовательских файлов (изображения),
- генерация сценария и слайдов по текстовому запросу,
- поэтапная готовность слайдов с polling,
- скачивание итогового результата (PDF/ZIP),
- тестовые GenAI one-shot endpoints (text/image).

## Запуск

Backend:
```bash
cd backend
uv sync --extra dev
uv run playwright install chromium
uv run uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Открыть:
- `http://localhost:3000/gen`
