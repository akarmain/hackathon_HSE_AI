<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="flex flex-col items-center gap-4 text-center">
      <h1 class="text-3xl font-semibold">Счетчик кликов</h1>
      <p class="text-muted-foreground">
        Клик по кнопке отправляет запрос в backend и увеличивает глобальный счетчик.
      </p>

      <button
        :disabled="isLoading"
        class="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
        @click="incrementCounter"
      >
        {{ isLoading ? "Считаем..." : "Клик" }}
      </button>

      <p class="text-xl font-medium">Кликов: {{ count }}</p>
      <p v-if="errorMessage" class="text-sm text-red-500">{{ errorMessage }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()

const count = ref(0)
const isLoading = ref(false)
const errorMessage = ref("")

const incrementCounter = async () => {
  isLoading.value = true
  errorMessage.value = ""

  try {
    const data = await $fetch<{ count: number }>(
      `${config.public.apiBase}${config.public.counterPath}`,
    )
    count.value = data.count
  } catch {
    errorMessage.value = "Не удалось получить значение счетчика."
  } finally {
    isLoading.value = false
  }
}
</script>
