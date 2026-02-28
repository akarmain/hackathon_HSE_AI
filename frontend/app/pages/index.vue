<template>
  <div class="relative h-[calc(100vh-4rem)] overflow-hidden px-4 py-4">
    <div class="absolute inset-0 bg-[radial-gradient(75%_60%_at_10%_10%,rgba(14,165,233,0.16),transparent_70%),radial-gradient(60%_45%_at_90%_10%,rgba(244,114,182,0.16),transparent_70%),linear-gradient(145deg,#f8fafc_0%,#eef2ff_45%,#f8fafc_100%)]" />

    <div class="relative mx-auto grid h-full w-full max-w-6xl grid-cols-1 gap-4 xl:grid-cols-[1.2fr_1fr]">
      <section class="flex flex-col justify-center rounded-2xl border bg-background/80 p-6 shadow-sm backdrop-blur">
        <p class="mb-2 text-xs uppercase tracking-[0.18em] text-muted-foreground">Hackathon HSE AI</p>
        <h1 class="text-3xl font-semibold leading-tight sm:text-4xl">
          Генератор презентаций
          <span class="block text-primary">из текстового запроса и ваших изображений</span>
        </h1>
        <p class="mt-4 max-w-2xl text-sm text-muted-foreground">
          Сервис автоматически строит сценарий, генерирует HTML слайды, рендерит их в PNG и собирает итоговый PDF.
          Вы задаете тему, число слайдов, тип работы и подключаете свои изображения с ключами.
        </p>

        <div class="mt-6 flex flex-wrap gap-2">
          <NuxtLink
            to="/gen"
            class="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            Открыть генератор
          </NuxtLink>
          <a
            href="https://s3.akarmain.ru/S/sbs.mp4"
            target="_blank"
            rel="noreferrer"
            class="inline-flex h-10 items-center justify-center rounded-md border px-4 text-sm font-medium transition-colors hover:bg-accent"
          >
            Смотреть демо-видео
          </a>
        </div>
      </section>

      <section class="grid grid-cols-1 gap-3">
        <article class="rounded-2xl border bg-background/80 p-4 shadow-sm backdrop-blur">
          <h2 class="text-base font-semibold">Как работает</h2>
          <p class="mt-2 text-sm text-muted-foreground">
            Prompt → Master-сценарий → Worker HTML → PNG рендер → PDF экспорт.
          </p>
        </article>

        <article class="rounded-2xl border bg-background/80 p-4 shadow-sm backdrop-blur">
          <h2 class="text-base font-semibold">Что можно настроить</h2>
          <p class="mt-2 text-sm text-muted-foreground">
            Количество слайдов, тип аудитории, speaker notes, привязку ваших изображений по ключам.
          </p>
        </article>

        <article class="rounded-2xl border bg-background/80 p-4 shadow-sm backdrop-blur">
          <h2 class="text-base font-semibold">Что получаете</h2>
          <p class="mt-2 text-sm text-muted-foreground">
            Превью всех слайдов, статус генерации в реальном времени, скачивание результата в PDF.
          </p>
        </article>
      </section>
    </div>
  </div>
</template>
