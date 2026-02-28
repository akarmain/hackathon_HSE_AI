# AI_2.md — Полная карта проекта `hackathon_HSE_AI`

## 1) Что это за проект

Монорепозиторий с двумя приложениями:
- `backend/` — API на FastAPI
- `frontend/` — UI на Nuxt 4 (Vue 3)

Текущий фокус проекта:
- загрузка и менеджмент изображений (upload / rename / delete / preview),
- тестовый модуль интеграции с GenAI:
  - one-shot вопрос к LLM,
  - one-shot генерация изображения с сохранением на сервер,
- простой backend-счетчик (`/counter`).

---

## 2) Технологический стек

Backend:
- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic Settings
- requests (для GenAI HTTP-вызовов)
- pytest

Frontend:
- Nuxt 4
- Vue 3 + TypeScript
- Tailwind CSS
- shadcn-nuxt / Reka UI

---

## 3) Архитектура и структура

### 3.1 Backend архитектура

Feature-based (вертикальная) структура:
- `features/counter` — счетчик
- `features/uploads` — загрузка/список/rename/delete/preview файлов
- `features/genai` — интеграция с внешним GenAI API

Поток:
- `app/main.py` создает FastAPI app и CORS
- `app/api/router.py` подключает feature routers
- каждая feature содержит `api.py` + `service.py` + `schemas.py`

### 3.2 Frontend архитектура

- `app/pages/*.vue` — страницы (`/`, `/gen`)
- `nuxt.config.ts` — runtime config (пути API)
- `app/components/ui/*` — UI-обвязка
- `app/plugins/*`, `app/composables/*` — клиентская инфраструктура

---

## 4) Эндпойнты backend

## Health
- `GET /health`
- Назначение: healthcheck
- Ответ: `{ "status": "ok" }`

## Counter
- `GET /counter`
- Назначение: глобальный in-memory инкремент
- Ответ: `{ "count": <int> }`

## Uploads
- `POST /api/uploads/image`
  - `multipart/form-data`, поле: `file`
  - Разрешенные типы: `image/png`, `image/jpeg`, `image/webp`, `image/gif`
  - Лимит размера: `UPLOADS_MAX_SIZE_MB` (по умолчанию 10MB)
  - Сохранение: `UPLOADS_DIR` (по умолчанию `app/storage/uploads`)
  - Имя файла:
    - sanitize (path traversal блокируется),
    - замена недопустимых символов,
    - уникализация `-1`, `-2`, ... при коллизиях
  - Ответ: `filename`, `stored_path`, `content_type`, `size`

- `GET /api/uploads/list`
  - Ответ: список файлов `files[]` с `filename`, `stored_path`

- `GET /api/uploads/image/{filename}`
  - Возвращает файл для превью

- `PATCH /api/uploads/rename`
  - Тело: `{ "filename": "...", "new_filename": "..." }`
  - Переименовывает файл на диске с sanitize + уникализацией
  - Если у нового имени нет расширения, используется расширение исходного файла

- `DELETE /api/uploads/file/{filename}`
  - Удаляет файл на диске
  - Ответ: `{ "filename": "...", "deleted": true }`

## GenAI
- `POST /api/genai/text`
  - One-shot вопрос к LLM без памяти диалога
  - Тело: `{ question, network_id?, model?, system? }`
  - По умолчанию сеть: `GENAI_DEFAULT_LLM_NETWORK` (`gemini-3-flash`)
  - Ответ: `{ answer, raw }`

- `POST /api/genai/image`
  - One-shot генерация изображения
  - Тело: `{ prompt, network_id?, model?, width?, height? }`
  - По умолчанию сеть: `GENAI_DEFAULT_IMAGE_NETWORK` (`flux-2`)
  - Важно: изображение сохраняется на сервере (не только URL)
  - Папка: `GENAI_IMAGES_DIR` (`app/storage/genai`)
  - Ответ: `{ filename, stored_path, source_url, raw }`

---

## 5) Переменные окружения

### Backend (`backend/.env`)
- `APP_NAME`
- `APP_ENV`
- `LOG_LEVEL`
- `UPLOADS_DIR`
- `UPLOADS_MAX_SIZE_MB`
- `CORS_ORIGINS`
- `CORS_ORIGIN_REGEX`
- `GENAI_API_KEY` (обязателен для `/api/genai/*`)
- `GENAI_BASE_URL` (обычно `https://api.gen-api.ru/api/v1`)
- `GENAI_DEFAULT_LLM_NETWORK`
- `GENAI_DEFAULT_IMAGE_NETWORK`
- `GENAI_IMAGES_DIR`

### Frontend (`frontend/.env`)
- `NUXT_PUBLIC_API_BASE`
- `NUXT_PUBLIC_COUNTER_PATH`
- `NUXT_PUBLIC_UPLOAD_IMAGE_PATH`
- `NUXT_PUBLIC_UPLOAD_LIST_PATH`
- `NUXT_PUBLIC_UPLOAD_RENAME_PATH`
- `NUXT_PUBLIC_UPLOAD_DELETE_BASE_PATH`
- `NUXT_PUBLIC_UPLOAD_PREVIEW_BASE_PATH`
- `NUXT_PUBLIC_GENAI_TEXT_PATH`
- `NUXT_PUBLIC_GENAI_IMAGE_PATH`

---

## 6) Функционал страницы `/gen`

Что есть сейчас:
1. Блок GenAI Text:
- ввод вопроса,
- кнопка отправки,
- вывод ответа.

2. Блок GenAI Image:
- ввод промпта,
- генерация,
- показ сообщения о сохранении на сервере (`stored_path`).

3. Блок Uploads:
- drag&drop или клик по зоне,
- загрузка файлов,
- список загруженных,
- rename (автосохранение по blur/Enter, без отдельной кнопки apply),
- delete,
- мини-превью,
- полноэкранная модалка по клику на превью.

---

## 7) Карта файлов (практически каждый файл)

Ниже — описание файлов, чтобы можно было точечно писать промпты на улучшение.

## 7.1 Корневой уровень
- `README.md` — краткое описание и запуск проекта
- `AI.md` — архитектурная документация первого уровня
- `AI_2.md` — этот подробный документ
- `LICENSE` — лицензия
- `.gitignore` — git-исключения

## 7.2 Backend: инфраструктура
- `backend/pyproject.toml`
  - зависимости, build-system, pytest config
- `backend/uv.lock`
  - lock-файл зависимостей `uv`
- `backend/Makefile`
  - команды `run`, `test`, `lint`
- `backend/Dockerfile`
  - образ backend
- `backend/docker-compose.yml`
  - сервис backend
- `backend/README.md`
  - локальный запуск, endpoints
- `backend/.env` / `backend/.env.example`
  - runtime-конфиг приложения

## 7.3 Backend: core/app
- `backend/app/main.py`
  - создание FastAPI app
  - CORS middleware
  - подключение `api_router`
  - endpoint `/health`

- `backend/app/core/config.py`
  - pydantic settings (`Settings`)
  - централизованный доступ к env (`get_settings`)

- `backend/app/core/logging.py`
  - настройка логирования приложения

- `backend/app/api/router.py`
  - сборка всех feature роутеров

- `backend/app/api/deps.py`
  - место для зависимостей (пока минимально используется)

- `backend/app/__init__.py`, `backend/app/api/__init__.py`, `backend/app/core/__init__.py`
  - package markers

## 7.4 Backend: feature counter
- `backend/app/features/counter/repo.py`
  - in-memory `count` + lock
- `backend/app/features/counter/service.py`
  - бизнес-метод `next_count`
- `backend/app/features/counter/schemas.py`
  - `CounterResponse`
- `backend/app/features/counter/router.py`
  - endpoint `GET /counter`
- `backend/app/features/counter/__init__.py`

## 7.5 Backend: feature uploads
- `backend/app/features/uploads/schemas.py`
  - схемы upload/list/rename/delete
- `backend/app/features/uploads/service.py`
  - sanitize filename
  - валидация MIME/size
  - сохранение файлов
  - уникализация имен
  - list/rename/delete/get preview file
- `backend/app/features/uploads/api.py`
  - API роуты uploads
- `backend/app/features/uploads/__init__.py`

## 7.6 Backend: feature genai
- `backend/app/features/genai/client.py`
  - low-level клиент GenAPI:
    - submit/poll
    - извлечение текста
    - извлечение image payload (URL/base64/raw)
    - загрузка байт изображения
- `backend/app/features/genai/schemas.py`
  - схемы text/image запросов и ответов
- `backend/app/features/genai/service.py`
  - orchestration логика:
    - question -> llm answer
    - image generation -> download -> save file
- `backend/app/features/genai/api.py`
  - `/api/genai/text`, `/api/genai/image`
- `backend/app/features/genai/__init__.py`

## 7.7 Backend: storage
- `backend/app/storage/uploads/*`
  - пользовательские загруженные картинки
- `backend/app/storage/genai/*`
  - сгенерированные GenAI картинки

## 7.8 Backend: tests
- `backend/tests/test_counter.py`
  - проверка глобального инкремента счетчика
- `backend/tests/test_uploads_service.py`
  - sanitize
  - unique naming
  - rename
  - delete

## 7.9 Frontend: инфраструктура
- `frontend/package.json`
  - скрипты и зависимости
- `frontend/package-lock.json`
  - lock
- `frontend/nuxt.config.ts`
  - runtimeConfig (все API пути)
- `frontend/tsconfig.json`
- `frontend/components.json`
- `frontend/Dockerfile`
- `frontend/.env` / `frontend/.env.example`

## 7.10 Frontend: app
- `frontend/app/app.vue`
  - общий layout + footer

- `frontend/app/pages/index.vue`
  - простая страница/демо (в т.ч. счетчик)

- `frontend/app/pages/gen.vue`
  - основная рабочая страница:
    - GenAI text тест
    - GenAI image тест (сохранение на сервер)
    - uploads CRUD + preview modal

- `frontend/app/plugins/theme.client.ts`
  - тема на клиенте
- `frontend/app/plugins/ssr-width.ts`
  - SSR width integration

- `frontend/app/composables/useThemeMode.ts`
  - управление темой
- `frontend/app/composables/useTelegram.ts`
  - хелпер Telegram WebApp

- `frontend/app/assets/css/tailwind.css`
- `frontend/assets/css/tailwind.css`
  - стили Tailwind (актуальный путь для Nuxt в конфиге)

## 7.11 Frontend: UI-kit
- `frontend/app/components/ThemeModeSwitcher.vue`
- `frontend/app/components/ui/button/*`
- `frontend/app/components/ui/dropdown-menu/*`
  - библиотечные UI-компоненты и обертки

## 7.12 Frontend: static
- `frontend/public/favicon.ico`
- `frontend/public/robots.txt`

---

## 8) Типичные сценарии использования

1. Загрузка пользовательского изображения:
- Пользователь на `/gen` кидает файл в dropzone
- `POST /api/uploads/image`
- Файл сохраняется в `app/storage/uploads`
- Файл появляется в списке

2. Переименование:
- Пользователь меняет имя в input
- blur/Enter -> `PATCH /api/uploads/rename`
- UI обновляет имя и preview URL

3. Удаление:
- Кнопка `Удалить` -> `DELETE /api/uploads/file/{filename}`
- Элемент удаляется из списка

4. Генерация текста через GenAI:
- Вопрос -> `POST /api/genai/text`
- Ответ показывается в блоке текста

5. Генерация изображения через GenAI:
- Промпт -> `POST /api/genai/image`
- backend получает URL/данные, скачивает и сохраняет файл в `app/storage/genai`
- UI показывает путь сохранения

---

## 9) Готовые направления для промптов на улучшение

Ниже темы, по которым можно формулировать задачи:

1. Безопасность и валидация:
- добавить антивирус-сканирование upload-файлов,
- добавить checksum и deduplication,
- строгая валидация расширения + MIME + magic bytes.

2. Upload UX:
- прогресс-бар загрузки,
- мультизагрузка,
- сортировка/фильтрация списка,
- пагинация.

3. Preview:
- carousel в модалке,
- горячие клавиши (`Esc`, стрелки),
- lazy loading thumbnails.

4. GenAI:
- выбор сети/модели в UI,
- queue + статус задач,
- история запросов,
- ограничения rate limit на пользователя.

5. Storage:
- перенос на S3/MinIO,
- фоновые задачи на очистку,
- метаданные файлов в БД.

6. Тестирование:
- интеграционные тесты API с TestClient,
- тесты на genai client parsing разных форматов ответа,
- e2e frontend тесты для `/gen`.

7. Архитектура:
- DI для сервисов вместо модульных singletons,
- выделение domain-слоя,
- observability (structured logs + metrics + traces).

---

## 10) Как запустить

Backend:
```bash
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm run dev
```

Открыть:
- `http://localhost:3000/gen`

