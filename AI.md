# Архитектура проекта hackathon_HSE_AI

## Общая структура

Проект построен на основе монорепозитория с разделением на backend и frontend части.

```
hackathon_HSE_AI/
├── backend/          # FastAPI backend приложение
├── frontend/         # Nuxt.js frontend приложение
├── AI.md            # Документация архитектуры
├── README.md        # Основная документация проекта
└── LICENSE          # Лицензия проекта
```

---

## Backend (FastAPI)

**Технологический стек:**
- FastAPI >= 0.115.0
- Uvicorn (ASGI сервер)
- Pydantic Settings
- Python >= 3.11

**Структура папок:**

```
backend/
├── app/                      # Основной код приложения
│   ├── api/                 # API слой
│   │   ├── router.py       # Главный роутер приложения
│   │   └── deps.py         # Зависимости для эндпоинтов
│   │
│   ├── core/               # Ядро приложения
│   │   ├── config.py      # Конфигурация и настройки
│   │   └── logging.py     # Настройка логирования
│   │
│   ├── features/          # Функциональные модули (вертикальная архитектура)
│   │   └── counter/       # Пример feature-модуля
│   │
│   └── main.py           # Точка входа приложения
│
├── tests/                # Тесты приложения
├── Dockerfile           # Docker образ для backend
├── docker-compose.yml   # Docker Compose конфигурация
├── Makefile            # Команды для разработки
├── pyproject.toml      # Конфигурация проекта и зависимости
└── uv.lock            # Lockfile зависимостей
```

**Архитектурные особенности:**
- **Вертикальная feature-архитектура**: каждая фича изолирована в отдельной папке
- **Слоистая структура**: разделение на API, Core и Features
- **Dependency Injection**: использование FastAPI dependencies

---

## Frontend (Nuxt.js)

**Технологический стек:**
- Nuxt.js 4.3.0
- Vue 3.5.27
- TypeScript 5.9.3
- Tailwind CSS 4.1.18
- Shadcn UI / Reka UI
- Vue Router 4.6.4
- Telegram WebApp (vue-tg)

**Структура папок:**

```
frontend/
├── app/                     # Основной код приложения
│   ├── pages/              # Страницы приложения (роутинг)
│   │   └── index.vue      # Главная страница
│   │
│   ├── components/        # Vue компоненты
│   │   ├── ui/           # UI компоненты (shadcn-nuxt)
│   │   └── ThemeModeSwitcher.vue  # Переключатель темы
│   │
│   ├── composables/      # Vue Composables (переиспользуемая логика)
│   ├── lib/             # Утилиты и вспомогательные функции
│   ├── plugins/         # Nuxt плагины
│   ├── assets/          # Статические ресурсы (стили, изображения)
│   └── app.vue         # Корневой компонент приложения
│
├── public/             # Публичные статические файлы
├── .nuxt/             # Сгенерированные файлы Nuxt (не в git)
├── node_modules/      # Зависимости (не в git)
├── Dockerfile         # Docker образ для frontend
├── nuxt.config.ts    # Конфигурация Nuxt
├── tsconfig.json     # Конфигурация TypeScript
├── components.json   # Конфигурация Shadcn UI
├── package.json      # Зависимости и скрипты
└── .env.example     # Пример переменных окружения
```

**Архитектурные особенности:**
- **SSR/SSG**: поддержка серверного рендеринга через Nuxt
- **Автоимпорт**: компоненты и composables импортируются автоматически
- **File-based routing**: роутинг на основе файловой структуры
- **UI Kit**: использование Shadcn UI с Tailwind CSS
- **Telegram WebApp**: интеграция с Telegram Mini Apps

---

## Принципы разработки

### Backend
- **Feature-Driven**: каждая функциональность изолирована в отдельный модуль
- **Clean Architecture**: разделение на слои (API, Domain, Infrastructure)
- **Configuration Management**: централизованное управление настройками через pydantic-settings
- **Testing**: структура для unit и integration тестов

### Frontend
- **Component-Based**: модульная архитектура на основе Vue компонентов
- **Composition API**: использование современного Vue 3 Composition API
- **Type Safety**: полная типизация через TypeScript
- **Design System**: единообразный UI через Shadcn компоненты
- **Responsive Design**: адаптивный дизайн с Tailwind CSS

---

## Docker

Проект полностью контейнеризован:
- **Backend**: отдельный Dockerfile для FastAPI приложения
- **Frontend**: отдельный Dockerfile для Nuxt приложения
- **Docker Compose**: оркестрация сервисов для локальной разработки

---

## Инструменты разработки

### Backend
- **uv**: менеджер зависимостей Python
- **pytest**: фреймворк для тестирования
- **Makefile**: автоматизация команд разработки

### Frontend
- **npm**: менеджер пакетов
- **ESLint**: линтер для кода
- **Prettier**: форматтер кода
- **TypeScript**: статическая типизация

---

## Быстрая проверка MVP загрузки изображений

Backend:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm run dev
```

Проверка:
- Открыть `http://localhost:3000/gen`
- Загрузить изображение через drag&drop или кнопку
- Файл сохраняется в `backend/app/storage/uploads/`
