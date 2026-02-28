<template>
  <div class="relative h-[calc(100vh-4rem)] overflow-hidden px-3 py-3 fade-in">
    <div class="h-full rounded-2xl border bg-background/85 shadow-sm backdrop-blur">
      <div class="grid h-full grid-cols-1 gap-3 p-3 xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside class="flex min-h-0 flex-col gap-3 panel-appear">
          <section class="rounded-xl border bg-card/70 p-3">
            <div class="mb-2 flex items-center justify-between gap-2">
              <h1 class="text-lg font-semibold">AI Deck Builder</h1>
              <span class="rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-muted-foreground">compact</span>
            </div>
            <p class="mb-2 text-xs text-muted-foreground">
              Введите тему, настройте параметры в меню и запустите генерацию.
            </p>
            <textarea
              v-model="presentationPrompt"
              class="h-36 w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="Например: Презентация проекта о развитии города Мытищи"
            />
            <div class="mt-2 flex items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 flex-1 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="isSubmitting || isUploading"
                @click="submitPresentation"
              >
                {{ isSubmitting ? "Генерация..." : "Сгенерировать" }}
              </button>
              <button
                type="button"
                class="inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors hover:bg-accent"
                @click="prefillDemo"
              >
                Демо
              </button>
            </div>
            <div class="mt-2 flex items-center justify-between rounded-md border bg-background/70 px-2 py-1.5">
              <span class="text-xs text-muted-foreground">Генерация сценария (speaker notes)</span>
              <Switch v-model:model-value="showScript" />
            </div>
            <p v-if="presentationError" class="mt-2 text-xs text-red-500">{{ presentationError }}</p>
          </section>

          <div class="flex flex-wrap gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger as-child>
                <Button type="button" variant="outline" size="sm" class="h-8">
                  Настройки
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent class="w-64" align="start">
                <DropdownMenuLabel>Параметры генерации</DropdownMenuLabel>
                <DropdownMenuSeparator />

                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    Слайды: {{ slideCount }}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent class="w-36">
                    <DropdownMenuItem
                      v-for="count in slideCountOptions"
                      :key="count"
                      @click="selectSlideCount(count)"
                    >
                      {{ count }}
                    </DropdownMenuItem>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>

                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>
                    Тип: {{ workTypeLabel }}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent class="w-44">
                    <DropdownMenuItem @click="selectWorkType('school')">Школьная</DropdownMenuItem>
                    <DropdownMenuItem @click="selectWorkType('student')">Студенческая</DropdownMenuItem>
                    <DropdownMenuItem @click="selectWorkType('academic')">Академическая</DropdownMenuItem>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>

                <DropdownMenuSeparator />
                <DropdownMenuLabel class="text-[11px] text-muted-foreground">
                  Дополнительные опции скрыты в компактном режиме
                </DropdownMenuLabel>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8"
              @click="showFilesPanel = !showFilesPanel"
            >
              {{ showFilesPanel ? "Скрыть файлы" : "Файлы" }}
            </Button>

            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8"
              @click="showLegacyPanel = !showLegacyPanel"
            >
              Legacy
            </Button>
          </div>

          <transition name="panel">
            <section v-if="showFilesPanel" class="flex min-h-0 flex-1 flex-col rounded-xl border bg-card/70 p-3">
              <h2 class="mb-2 text-sm font-medium">Файлы и ключи</h2>
              <div
                class="cursor-pointer rounded-md border-2 border-dashed p-3 text-center transition-colors"
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
                <p class="text-xs text-muted-foreground">Перетащите изображение или нажмите</p>
              </div>
              <p class="mt-1 text-[11px] text-muted-foreground">PNG/JPG/WEBP/GIF до 10MB</p>

              <input
                ref="fileInputRef"
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                class="hidden"
                @change="onFileInputChange"
              >

              <p v-if="errorMessage" class="mt-1 text-xs text-red-500">{{ errorMessage }}</p>

              <ul v-if="uploadedFiles.length" class="mt-2 min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
                <li
                  v-for="item in uploadedFiles"
                  :key="item.name"
                  class="rounded-md border bg-background/70 p-2"
                >
                  <div class="flex items-start gap-2">
                    <button type="button" class="block" @click="openPreview(item)">
                      <img
                        :src="item.previewUrl"
                        :alt="item.name"
                        class="h-14 w-14 rounded-md border object-cover"
                      >
                    </button>
                    <div class="min-w-0 flex flex-1 flex-col gap-1.5">
                      <input
                        v-model="item.assetKey"
                        type="text"
                        class="h-8 w-full rounded-md border bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        placeholder="Ключ, например logo_team"
                      >

                      <div class="flex items-center gap-1.5">
                        <input
                          v-model="item.editName"
                          type="text"
                          class="h-8 w-full rounded-md border bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          placeholder="Новое имя"
                          :disabled="item.isRenaming || item.isDeleting"
                          @keydown.enter.prevent="renameFile(item)"
                          @blur="renameFile(item)"
                        >
                        <button
                          type="button"
                          class="inline-flex h-8 items-center justify-center rounded-md border border-red-300 px-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                          :disabled="item.isDeleting || item.isRenaming"
                          @click="deleteFile(item)"
                        >
                          {{ item.isDeleting ? "..." : "×" }}
                        </button>
                      </div>
                    </div>
                  </div>
                </li>
              </ul>
              <p v-else class="mt-2 text-xs text-muted-foreground">Нет загруженных файлов</p>
            </section>
          </transition>

          <transition name="panel">
            <section v-if="showLegacyPanel" class="rounded-xl border bg-card/70 p-3">
              <h2 class="mb-2 text-sm font-medium">Legacy GenAI</h2>
              <div class="space-y-2">
                <textarea
                  v-model="genAIQuestion"
                  class="h-20 w-full resize-none rounded-md border bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="Вопрос к LLM"
                />
                <button
                  type="button"
                  class="inline-flex h-8 items-center justify-center rounded-md border px-2 text-xs font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isAskingAI"
                  @click="askGenAI"
                >
                  {{ isAskingAI ? "..." : "Спросить" }}
                </button>
                <p v-if="genAIAnswer" class="rounded-md bg-muted p-2 text-xs">{{ genAIAnswer }}</p>
              </div>

              <div class="mt-2 space-y-2">
                <textarea
                  v-model="genAIImagePrompt"
                  class="h-20 w-full resize-none rounded-md border bg-background px-2 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  placeholder="Промпт для генерации изображения"
                />
                <button
                  type="button"
                  class="inline-flex h-8 items-center justify-center rounded-md border px-2 text-xs font-medium transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="isGeneratingAIImage"
                  @click="generateGenAIImage"
                >
                  {{ isGeneratingAIImage ? "..." : "Сгенерировать" }}
                </button>
                <p v-if="genAIImageSavedPath" class="rounded-md bg-muted p-2 text-xs">{{ genAIImageSavedPath }}</p>
              </div>
            </section>
          </transition>
        </aside>

        <section class="flex min-h-0 flex-col gap-3 slide-up">
          <section class="rounded-xl border bg-card/70 p-3">
            <div class="flex flex-wrap items-center gap-2 text-xs">
              <span class="rounded-full border px-2 py-1">ID: {{ presentationId || "—" }}</span>
              <span class="rounded-full border px-2 py-1">Статус: {{ status || "queued" }}</span>
              <span class="rounded-full border px-2 py-1">Прогресс: {{ slidesReady }} / {{ slidesTotal }}</span>

              <a
                v-if="downloadUrl"
                :href="downloadUrl"
                class="inline-flex h-8 items-center justify-center rounded-md border px-3 text-xs font-medium transition-colors hover:bg-accent"
                target="_blank"
                rel="noreferrer"
              >
                Скачать
              </a>
              <a
                v-if="downloadUrl"
                :href="downloadUrl"
                class="inline-flex h-8 items-center justify-center rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90"
                download="presentation.pdf"
              >
                PDF
              </a>
            </div>
          </section>

          <section class="flex min-h-0 flex-1 flex-col rounded-xl border bg-card/70 p-3">
            <h2 class="mb-2 text-sm font-medium">Слайды</h2>
            <div v-if="slides.length" class="min-h-0 flex-1 overflow-y-auto pr-1">
              <div class="grid gap-2 md:grid-cols-2 2xl:grid-cols-3">
                <div
                  v-for="slide in slides"
                  :key="slide.index"
                  class="rounded-md border bg-background/70 p-2 transition-transform duration-200 hover:-translate-y-0.5"
                >
                  <p class="mb-1 text-[11px] text-muted-foreground">
                    Слайд {{ slide.index }} · {{ slide.status }}
                  </p>
                  <button
                    v-if="slide.status === 'ready'"
                    type="button"
                    class="block w-full"
                    @click="openSlidePreview(slide)"
                  >
                    <img
                      :src="absoluteUrl(slide.imageUrl)"
                      :alt="`slide ${slide.index}`"
                      class="aspect-video w-full rounded object-contain bg-muted"
                    >
                  </button>
                  <div
                    v-else
                    class="flex aspect-video w-full items-center justify-center rounded bg-muted text-[11px] text-muted-foreground"
                  >
                    {{ slide.status === 'failed' ? 'Ошибка рендера' : 'Генерируется...' }}
                  </div>
                </div>
              </div>
            </div>
            <p v-else class="text-xs text-muted-foreground">Слайды появятся по мере генерации.</p>
          </section>

          <section v-if="showScript && scriptText" class="rounded-xl border bg-card/70 p-3">
            <h2 class="mb-1 text-sm font-medium">Сценарий</h2>
            <pre class="max-h-24 overflow-y-auto whitespace-pre-wrap text-xs">{{ scriptText }}</pre>
          </section>
        </section>
      </div>
    </div>

    <button
      v-if="showVideoAssistButton"
      type="button"
      class="video-assist-btn"
      @click="showVideoAssistModal = true"
    >
      Видео
    </button>

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

    <div
      v-if="showVideoAssistModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      @click.self="showVideoAssistModal = false"
    >
      <div class="relative w-full max-w-3xl rounded-xl border bg-black p-3 shadow-2xl panel-appear">
        <button
          type="button"
          class="absolute right-3 top-3 inline-flex h-8 items-center justify-center rounded-md border border-white/40 px-3 text-xs font-medium text-white hover:bg-white/10"
          @click="showVideoAssistModal = false"
        >
          Закрыть
        </button>
        <video
          controls
          autoplay
          playsinline
          class="mt-8 aspect-video w-full rounded-lg"
          :src="videoAssistUrl"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Switch } from "@/components/ui/switch"

type WorkType = "school" | "student" | "academic"

type UploadedFile = {
  name: string
  editName: string
  assetKey: string
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
  stored_path: string
}

const config = useRuntimeConfig()

const presentationPrompt = ref("")
const slideCount = ref(8)
const slideCountOptions = Array.from({ length: 16 }, (_, index) => index + 5)
const workType = ref<WorkType>("student")
const showScript = ref(true)

const showFilesPanel = ref(false)
const showLegacyPanel = ref(false)
const showVideoAssistModal = ref(false)
const videoAssistUrl = "https://s3.akarmain.ru/S/sbs.mp4"

const {
  presentationId,
  status,
  slidesReady,
  slidesTotal,
  slides,
  scriptText,
  downloadUrl,
  isSubmitting,
  errorMessage: presentationError,
  createPresentation,
  absoluteUrl,
} = usePresentationGenerator()

const workTypeLabel = computed(() => {
  if (workType.value === "school") return "Школьная"
  if (workType.value === "academic") return "Академическая"
  return "Студенческая"
})

const showVideoAssistButton = computed(() => Boolean(presentationId.value))

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

const normalizeAssetKey = (value: string) => {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "") || "file"
}

const previewUrlFor = (filename: string) => (
  `${uploadPreviewBaseUrl.value}${encodeURIComponent(filename)}`
)

const toUploadedFile = (filename: string): UploadedFile => ({
  name: filename,
  editName: filename,
  assetKey: normalizeAssetKey(filename.replace(/\.[^.]+$/, "")),
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
      const oldDefaultKey = normalizeAssetKey(item.name.replace(/\.[^.]+$/, ""))
      const newDefaultKey = normalizeAssetKey(payload.filename.replace(/\.[^.]+$/, ""))
      item.name = payload.filename
      item.editName = payload.filename
      item.previewUrl = previewUrlFor(payload.filename)
      if (item.assetKey === oldDefaultKey) {
        item.assetKey = newDefaultKey
      }
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

const buildFilesPayload = () => {
  return uploadedFiles.value.map((file) => ({
    key: normalizeAssetKey(file.assetKey),
    fileId: file.name,
    originalName: file.name,
  }))
}

const selectSlideCount = (value: number) => {
  slideCount.value = value
}

const selectWorkType = (value: WorkType) => {
  workType.value = value
}

const submitPresentation = async () => {
  if (!presentationPrompt.value.trim()) {
    return
  }
  await createPresentation({
    prompt: presentationPrompt.value.trim(),
    slideCount: Math.max(5, Math.min(20, slideCount.value || 8)),
    workType: workType.value,
    showScript: showScript.value,
    files: buildFilesPayload(),
  })
}

const prefillDemo = () => {
  presentationPrompt.value = "Презентация проекта AI Deck Builder для финала хакатона"
  slideCount.value = 8
  workType.value = "student"
  showScript.value = true
}

const openPreview = (item: UploadedFile) => {
  previewModal.value = { url: item.previewUrl, name: item.name }
}

const openSlidePreview = (slide: { index: number, imageUrl: string }) => {
  previewModal.value = {
    url: absoluteUrl(slide.imageUrl),
    name: `slide ${slide.index}`,
  }
}

const closePreview = () => {
  previewModal.value = null
}

const askGenAI = async () => {
  const question = genAIQuestion.value.trim()
  if (!question) {
    return
  }

  isAskingAI.value = true
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
      return
    }
    genAIAnswer.value = payload && "answer" in payload ? payload.answer : ""
  } finally {
    isAskingAI.value = false
  }
}

const generateGenAIImage = async () => {
  const prompt = genAIImagePrompt.value.trim()
  if (!prompt) {
    return
  }

  isGeneratingAIImage.value = true
  genAIImageSavedPath.value = ""
  try {
    const response = await fetch(genAIImageUrlApi.value, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    })
    const payload = (await response.json().catch(() => null)) as
      | GenAIImageResponse
      | { detail?: string }
      | null
    if (!response.ok) {
      return
    }
    genAIImageSavedPath.value = payload && "stored_path" in payload ? payload.stored_path : ""
  } finally {
    isGeneratingAIImage.value = false
  }
}

onMounted(() => {
  void loadUploadedFiles()
})
</script>

<style scoped>
.fade-in {
  animation: fadeIn 320ms ease-out;
}

.slide-up {
  animation: slideUp 380ms ease-out;
}

.panel-appear {
  animation: panelAppear 220ms ease-out;
}

.video-assist-btn {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  height: 36px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.video-assist-btn:hover {
  transform: translateY(-50%) translateX(-2px);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
}

.panel-enter-active,
.panel-leave-active {
  transition: all 220ms ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes panelAppear {
  from {
    opacity: 0;
    transform: scale(0.985);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
