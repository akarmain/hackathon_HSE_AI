# FastAPI Counter Backend

Minimal production-style FastAPI backend scaffold using layered + feature-based architecture.

## Requirements

- Python 3.11+

## Local Run

```bash
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints:

- `GET /counter` -> increments global in-memory counter and returns `{"count": <int>}`
- `GET /health` -> `{"status": "ok"}`
- `POST /api/uploads/image` -> uploads image from `multipart/form-data` field `file`
- `GET /api/uploads/list` -> returns uploaded file names
- `GET /api/uploads/image/{filename}` -> returns uploaded image for preview
- `PATCH /api/uploads/rename` -> renames uploaded file (`filename`, `new_filename`)
- `DELETE /api/uploads/file/{filename}` -> deletes uploaded file
- `POST /api/genai/text` -> one-shot question to GenAI LLM (no context persistence)
- `POST /api/genai/image` -> one-shot image generation via GenAI, image is saved to `app/storage/genai`

Environment for GenAI:
- `GENAI_API_KEY` - required for `/api/genai/*`
- `GENAI_BASE_URL` - default `https://api.gen-api.ru/api/v1`
- `GENAI_DEFAULT_LLM_NETWORK` - default `gemini-3-flash`
- `GENAI_DEFAULT_IMAGE_NETWORK` - default `flux-2`
- `GENAI_IMAGES_DIR` - default `app/storage/genai`

## Docker Run

```bash
cd backend
docker compose up --build
```

## Tests

```bash
cd backend
pytest
```
