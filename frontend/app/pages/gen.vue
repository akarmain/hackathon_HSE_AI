<template>
  <div class="mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-6 px-4 py-8">
    <h1 class="text-2xl font-semibold">Генерация</h1>

    <div class="flex flex-col gap-2">
      <label class="text-sm font-medium" for="prompt">Промпт</label>
      <textarea
        id="prompt"
        v-model="prompt"
        class="min-h-28 rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        placeholder="Опиши, что хочешь сгенерировать..."
      />
    </div>

    <div class="rounded-md border p-4">
      <h2 class="mb-3 text-base font-medium">Тест GenAI: текст</h2>
      <div class="flex flex-col gap-2">
        <textarea
          v-model="genAIQuestion"
          class="min-h-24 rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          placeholder="Задай вопрос ИИ без контекста..."
        />
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isAskingAI"
            @click="askGenAI"
          >
            {{ isAskingAI ? "Обработка..." : "Спросить ИИ" }}
          </button>
        </div>
        <p v-if="genAIAnswer" class="rounded-md bg-muted p-3 text-sm">{{ genAIAnswer }}</p>
      </div>
    </div>

    <div class="rounded-md border p-4">
      <h2 class="mb-3 text-base font-medium">Тест GenAI: генерация изображения</h2>
      <div class="flex flex-col gap-2">
        <textarea
          v-model="genAIImagePrompt"
          class="min-h-24 rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
          placeholder="Опиши изображение для генерации..."
        />
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isGeneratingAIImage"
            @click="generateGenAIImage"
          >
            {{ isGeneratingAIImage ? "Генерация..." : "Сгенерировать изображение" }}
          </button>
        </div>
        <p v-if="genAIImageSavedPath" class="rounded-md bg-muted p-3 text-sm">
          Изображение сохранено на сервере: {{ genAIImageSavedPath }}
        </p>
      </div>
    </div>

    <div class="flex flex-col gap-3">
      <div
        class="cursor-pointer rounded-md border-2 border-dashed p-6 text-center transition-colors"
        :class="isDragActive ? 'border-primary bg-primary/5' : 'border-border'"
        role="button"
        tabindex="0"
        @dragenter.prevent="isDragActive = true"
        @dragover.prevent="isDragActive = true"
        @dragleave.prevent="isDragActive = false"
        @drop.prevent="onDrop"
        @click="openFileDialog"
        @keydown.enter.prevent="openFileDialog"
        @keydown.space.prevent="openFileDialog"
      >
        <p class="text-sm text-muted-foreground">
          Перетащите изображение сюда или нажмите на это поле
        </p>
      </div>
      <p class="text-xs text-muted-foreground">PNG, JPG, WEBP, GIF до 10MB</p>

      <input
        ref="fileInputRef"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        class="hidden"
        @change="onFileInputChange"
      >

      <p v-if="errorMessage" class="text-sm text-red-500">{{ errorMessage }}</p>
    </div>

    <div class="flex flex-col gap-2">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-lg font-medium">Загруженные файлы</h2>
      </div>
      <ul v-if="uploadedFiles.length" class="space-y-3">
        <li
          v-for="item in uploadedFiles"
          :key="item.name"
          class="rounded-md border p-3"
        >
          <div class="flex items-start gap-3">
            <button type="button" class="block" @click="openPreview(item)">
              <img
                :src="item.previewUrl"
                :alt="item.name"
                class="h-20 w-20 rounded-md border object-cover"
              >
            </button>
            <div class="min-w-0 flex flex-1 flex-col justify-center space-y-2">
              <div class="flex items-center gap-2">
                <input
                  v-model="item.editName"
                  type="text"
                  class="h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="Новое имя файла"
                  :disabled="item.isRenaming || item.isDeleting"
                  @keydown.enter.prevent="renameFile(item)"
                  @blur="renameFile(item)"
                >
                <span v-if="item.isRenaming" class="text-xs text-muted-foreground">Сохраняем...</span>
                <button
                  type="button"
                  class="inline-flex h-9 items-center justify-center rounded-md border border-red-300 px-3 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="item.isDeleting || item.isRenaming"
                  @click="deleteFile(item)"
                >
                  {{ item.isDeleting ? "Удаляем..." : "Удалить" }}
                </button>
              </div>
            </div>
          </div>
        </li>
      </ul>
      <p v-else class="text-sm text-muted-foreground">Пока нет загруженных изображений.</p>
    </div>

    <div
      v-if="previewModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      @click.self="closePreview"
    >
      <button
        type="button"
        class="absolute right-4 top-4 inline-flex h-9 items-center justify-center rounded-md border border-white/40 px-3 text-sm font-medium text-white hover:bg-white/10"
        @click="closePreview"
      >
        Закрыть
      </button>
      <img
        :src="previewModal.url"
        :alt="previewModal.name"
        class="max-h-[95vh] max-w-[95vw] rounded-md object-contain"
      >
    </div>
  </div>
</template>

<script setup lang="ts">
type UploadedFile = {
  name: string
  editName: string
  status: "uploaded"
  previewUrl: string
  isRenaming: boolean
  isDeleting: boolean
}

type UploadImageResponse = {
  filename: string
}

type UploadListResponse = {
  files: Array<{ filename: string }>
}

type RenameResponse = {
  filename: string
}

type GenAITextResponse = {
  answer: string
}

type GenAIImageResponse = {
  filename: string
  stored_path: string
}

const config = useRuntimeConfig()

const prompt = ref("")
const isDragActive = ref(false)
const isUploading = ref(false)
const errorMessage = ref("")
const uploadedFiles = ref<UploadedFile[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const previewModal = ref<{ url: string, name: string } | null>(null)
const genAIQuestion = ref("")
const genAIAnswer = ref("")
const isAskingAI = ref(false)
const genAIImagePrompt = ref("")
const genAIImageSavedPath = ref("")
const isGeneratingAIImage = ref(false)

const uploadImageUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadImagePath}`,
)
const uploadListUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadListPath}`,
)
const uploadRenameUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadRenamePath}`,
)
const uploadDeleteBaseUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadDeleteBasePath}`,
)
const uploadPreviewBaseUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadPreviewBasePath}`,
)
const genAITextUrl = computed(
  () => `${config.public.apiBase}${config.public.genaiTextPath}`,
)
const genAIImageUrlApi = computed(
  () => `${config.public.apiBase}${config.public.genaiImagePath}`,
)

const previewUrlFor = (filename: string) => (
  `${uploadPreviewBaseUrl.value}${encodeURIComponent(filename)}`
)

const toUploadedFile = (filename: string): UploadedFile => ({
  name: filename,
  editName: filename,
  status: "uploaded",
  previewUrl: previewUrlFor(filename),
  isRenaming: false,
  isDeleting: false,
})

const loadUploadedFiles = async () => {
  try {
    const data = await $fetch<UploadListResponse>(uploadListUrl.value)
    uploadedFiles.value = data.files.map((file) => toUploadedFile(file.filename))
  } catch {
    errorMessage.value = "Не удалось загрузить список файлов."
  }
}

const openFileDialog = () => {
  fileInputRef.value?.click()
}

const onFileInputChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    void uploadImage(file)
  }
  input.value = ""
}

const onDrop = (event: DragEvent) => {
  isDragActive.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) {
    void uploadImage(file)
  }
}

const uploadImage = async (file: File) => {
  if (!file.type.startsWith("image/")) {
    errorMessage.value = "Можно загружать только изображения."
    return
  }

  isUploading.value = true
  errorMessage.value = ""

  const formData = new FormData()
  formData.append("file", file, file.name)

  try {
    const response = await fetch(uploadImageUrl.value, {
      method: "POST",
      body: formData,
    })

    const payload = (await response.json().catch(() => null)) as
      | UploadImageResponse
      | { detail?: string }
      | null

    if (!response.ok) {
      errorMessage.value = payload && "detail" in payload && payload.detail
        ? payload.detail
        : "Не удалось загрузить файл."
      return
    }

    if (payload && "filename" in payload) {
      uploadedFiles.value.unshift(toUploadedFile(payload.filename))
    }
  } catch {
    errorMessage.value = "Ошибка сети при загрузке файла."
  } finally {
    isUploading.value = false
  }
}

const renameFile = async (item: UploadedFile) => {
  const nextName = item.editName.trim()
  if (!nextName) {
    item.editName = item.name
    errorMessage.value = "Введите новое имя файла."
    return
  }
  if (nextName === item.name) {
    return
  }

  item.isRenaming = true
  errorMessage.value = ""
  try {
    const response = await fetch(uploadRenameUrl.value, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: item.name,
        new_filename: nextName,
      }),
    })

    const payload = (await response.json().catch(() => null)) as
      | RenameResponse
      | { detail?: string }
      | null

    if (!response.ok) {
      errorMessage.value = payload && "detail" in payload && payload.detail
        ? payload.detail
        : "Не удалось переименовать файл."
      return
    }

    if (payload && "filename" in payload) {
      item.name = payload.filename
      item.editName = payload.filename
      item.previewUrl = previewUrlFor(payload.filename)
    }
  } catch {
    errorMessage.value = "Ошибка сети при переименовании файла."
  } finally {
    item.isRenaming = false
  }
}

const deleteFile = async (item: UploadedFile) => {
  item.isDeleting = true
  errorMessage.value = ""
  try {
    const response = await fetch(
      `${uploadDeleteBaseUrl.value}${encodeURIComponent(item.name)}`,
      { method: "DELETE" },
    )
    const payload = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null

    if (!response.ok) {
      errorMessage.value = payload && payload.detail
        ? payload.detail
        : "Не удалось удалить файл."
      return
    }

    uploadedFiles.value = uploadedFiles.value.filter((file) => file.name !== item.name)
    if (previewModal.value?.name === item.name) {
      closePreview()
    }
  } catch {
    errorMessage.value = "Ошибка сети при удалении файла."
  } finally {
    item.isDeleting = false
  }
}

const openPreview = (item: UploadedFile) => {
  previewModal.value = { url: item.previewUrl, name: item.name }
}

const closePreview = () => {
  previewModal.value = null
}

const askGenAI = async () => {
  const question = genAIQuestion.value.trim()
  if (!question) {
    errorMessage.value = "Введите вопрос для ИИ."
    return
  }

  isAskingAI.value = true
  errorMessage.value = ""
  try {
    const response = await fetch(genAITextUrl.value, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    })
    const payload = (await response.json().catch(() => null)) as
      | GenAITextResponse
      | { detail?: string }
      | null
    if (!response.ok) {
      errorMessage.value = payload && "detail" in payload && payload.detail
        ? payload.detail
        : "Ошибка ответа от ИИ."
      return
    }
    genAIAnswer.value = payload && "answer" in payload ? payload.answer : ""
  } catch {
    errorMessage.value = "Ошибка сети при запросе к ИИ."
  } finally {
    isAskingAI.value = false
  }
}

const generateGenAIImage = async () => {
  const promptValue = genAIImagePrompt.value.trim()
  if (!promptValue) {
    errorMessage.value = "Введите промпт для генерации изображения."
    return
  }

  isGeneratingAIImage.value = true
  errorMessage.value = ""
  genAIImageSavedPath.value = ""
  try {
    const response = await fetch(genAIImageUrlApi.value, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: promptValue }),
    })
    const payload = (await response.json().catch(() => null)) as
      | GenAIImageResponse
      | { detail?: string }
      | null
    if (!response.ok) {
      errorMessage.value = payload && "detail" in payload && payload.detail
        ? payload.detail
        : "Ошибка генерации изображения."
      return
    }
    genAIImageSavedPath.value = payload && "stored_path" in payload ? payload.stored_path : ""
  } catch {
    errorMessage.value = "Ошибка сети при генерации изображения."
  } finally {
    isGeneratingAIImage.value = false
  }
}

onMounted(() => {
  void loadUploadedFiles()
})
</script>
