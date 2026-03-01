<template>
  <div class="workspace-page fade-in">
    <div v-if="!isViewerMode" class="idle-state panel-appear">
      <section class="idle-card">
        <textarea
          v-model="presentationPrompt"
          class="prompt-input"
          placeholder="Введите описание презентации"
        />

        <div class="idle-controls">
          <div class="mini-select-wrap">
            <span class="mini-label">Слайды</span>
            <select v-model.number="slideCount" class="mini-select">
              <option v-for="count in slideCountOptions" :key="count" :value="count">
                {{ count }}
              </option>
            </select>
          </div>

          <div class="mini-select-wrap">
            <span class="mini-label">Тип</span>
            <select v-model="workType" class="mini-select">
              <option value="school">Школьная</option>
              <option value="student">Студенческая</option>
              <option value="academic">Академическая</option>
            </select>
          </div>

          <div class="switch-row switch-chip">
            <span class="text-xs text-muted-foreground">Сценарий</span>
            <Switch v-model:model-value="showScript" />
          </div>

          <Button
            type="button"
            size="icon"
            class="launch-btn"
            :disabled="isSubmitting || isUploading"
            @click="submitPresentation"
          >
            ↑
          </Button>
        </div>

        <div class="thumb-strip idle-thumb-strip">
          <Button
            type="button"
            variant="outline"
            size="icon"
            class="upload-tile"
            :disabled="isSubmitting || isUploading"
            @click="openFileDialog"
          >
            +
          </Button>

          <div
            v-for="item in uploadedFiles"
            :key="item.name"
            class="thumb-wrap"
          >
            <Popover
              :open="hoveredFileName === item.name"
              @update:open="(open) => onFilePopoverOpenChange(item.name, open)"
            >
              <PopoverTrigger as-child>
                <Button
                  type="button"
                  variant="outline"
                  class="thumb-tile"
                  @mouseenter="openFilePopover(item.name)"
                  @mouseleave="scheduleCloseFilePopover(item.name)"
                  @click="openFilePreview(item)"
                >
                  <img :src="item.previewUrl" :alt="item.name" class="thumb-image">
                </Button>
              </PopoverTrigger>

              <PopoverContent
                side="top"
                align="center"
                :side-offset="10"
                class="file-key-popover"
                @mouseenter="openFilePopover(item.name)"
                @mouseleave="scheduleCloseFilePopover(item.name)"
              >
                <div class="file-key-row">
                  <input
                    v-model="item.assetKey"
                    type="text"
                    class="key-input"
                    placeholder="Ключ / описание"
                  >
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="outline"
                    class="delete-mini"
                    :disabled="item.isDeleting"
                    @click="deleteFile(item)"
                  >
                    {{ item.isDeleting ? "..." : "×" }}
                  </Button>
                </div>
              </PopoverContent>
            </Popover>

            <p class="thumb-key-label">{{ item.assetKey || "key" }}</p>
          </div>
        </div>
      </section>

      <input
        ref="fileInputRef"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        class="hidden"
        @change="onFileInputChange"
      >

      <p v-if="errorMessage" class="mt-2 text-xs text-red-500">{{ errorMessage }}</p>
      <p v-if="presentationError" class="mt-2 text-xs text-red-500">{{ presentationError }}</p>
    </div>

    <div v-else class="viewer-state slide-up">
      <aside class="viewer-sidebar panel-appear">
        <section class="side-card">
          <textarea
            v-model="presentationPrompt"
            class="prompt-input compact"
            placeholder="Введите описание презентации"
          />

          <div class="idle-controls compact-row">
            <div class="mini-select-wrap">
              <span class="mini-label">Слайды</span>
              <select v-model.number="slideCount" class="mini-select">
                <option v-for="count in slideCountOptions" :key="`view-${count}`" :value="count">
                  {{ count }}
                </option>
              </select>
            </div>

            <div class="mini-select-wrap flex-1">
              <span class="mini-label">Тип</span>
              <select v-model="workType" class="mini-select">
                <option value="school">Школьная</option>
                <option value="student">Студенческая</option>
                <option value="academic">Академическая</option>
              </select>
            </div>
          </div>

          <div class="viewer-actions">
            <div class="switch-row">
              <span class="text-xs text-muted-foreground">Сценарий</span>
              <Switch v-model:model-value="showScript" />
            </div>

            <Button
              type="button"
              class="generate-btn"
              :disabled="isSubmitting || isUploading"
              @click="submitPresentation"
            >
              {{ isSubmitting ? "Генерация..." : "Генерация" }}
            </Button>
          </div>
        </section>

        <section class="side-card">
          <p class="section-title">Файлы</p>
          <div class="thumb-strip">
            <Button
              type="button"
              variant="outline"
              size="icon"
              class="upload-tile"
              @click="openFileDialog"
            >
              +
            </Button>

            <div
              v-for="item in uploadedFiles"
              :key="`viewer-${item.name}`"
              class="thumb-wrap"
            >
              <Popover
                :open="hoveredFileName === item.name"
                @update:open="(open) => onFilePopoverOpenChange(item.name, open)"
              >
                <PopoverTrigger as-child>
                  <Button
                    type="button"
                    variant="outline"
                    class="thumb-tile"
                    @mouseenter="openFilePopover(item.name)"
                    @mouseleave="scheduleCloseFilePopover(item.name)"
                    @click="openFilePreview(item)"
                  >
                    <img :src="item.previewUrl" :alt="item.name" class="thumb-image">
                  </Button>
                </PopoverTrigger>

                <PopoverContent
                  side="top"
                  align="center"
                  :side-offset="10"
                  class="file-key-popover"
                  @mouseenter="openFilePopover(item.name)"
                  @mouseleave="scheduleCloseFilePopover(item.name)"
                >
                  <div class="file-key-row">
                    <input
                      v-model="item.assetKey"
                      type="text"
                      class="key-input"
                      placeholder="Ключ / описание"
                    >
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="outline"
                      class="delete-mini"
                      :disabled="item.isDeleting"
                      @click="deleteFile(item)"
                    >
                      {{ item.isDeleting ? "..." : "×" }}
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>

              <p class="thumb-key-label">{{ item.assetKey || "key" }}</p>
            </div>
          </div>

          <input
            ref="fileInputRef"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            class="hidden"
            @change="onFileInputChange"
          >
        </section>

        <section v-if="showScript" class="side-card">
          <p class="section-title">Сценарий</p>
          <pre :class="['script-block', { 'script-block-placeholder': !scriptText.trim() }]">
            {{ scenarioPreviewText }}
          </pre>
        </section>

        <p v-if="errorMessage" class="text-xs text-red-500">{{ errorMessage }}</p>
        <p v-if="presentationError" class="text-xs text-red-500">{{ presentationError }}</p>
      </aside>

      <section class="viewer-content">
        <header class="content-header">
          <p class="progress-title">{{ progressTitle }}</p>
          <a
            v-if="downloadUrl"
            :href="downloadUrl"
            class="download-btn"
            download="presentation.pdf"
          >
            Скачать PDF
          </a>
        </header>

        <div class="slides-feed">
          <article
            v-for="slide in slidesFeed"
            :key="slide.index"
            class="slide-row"
          >
            <div class="slide-meta">
              <p class="slide-title">Слайд {{ slide.index }}</p>
              <p class="slide-status">
                {{ slide.status === "ready" ? "Готов" : slide.status === "failed" ? "Ошибка" : "Генерация" }}
              </p>
            </div>

            <button
              v-if="slide.status === 'ready' && slide.imageUrl"
              type="button"
              class="slide-preview"
              @click="openSlidePreview(slide)"
            >
              <img
                :src="absoluteUrl(slide.imageUrl)"
                :alt="`slide ${slide.index}`"
                class="slide-image"
              >
            </button>

            <div v-else class="slide-pending">
              <span>{{ slide.status === "failed" ? "Ошибка рендера" : "Генерируется..." }}</span>
            </div>
          </article>
        </div>
      </section>
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

      <div class="preview-modal-card">
        <img
          :src="previewImageUrl"
          :alt="previewImageName"
          class="preview-modal-image"
        >

        <div v-if="previewModal.kind === 'file'" class="preview-modal-footer">
          <span class="text-xs text-muted-foreground">Ключ файла</span>
          <input
            v-model="previewModal.item.assetKey"
            type="text"
            class="modal-key-input"
            placeholder="Ключ / описание"
          >
        </div>
      </div>
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Switch } from "@/components/ui/switch"

type WorkType = "school" | "student" | "academic"

type UploadedFile = {
  name: string
  assetKey: string
  status: "uploaded"
  previewUrl: string
  isDeleting: boolean
}

type UploadImageResponse = {
  filename: string
}

type UploadListResponse = {
  files: Array<{ filename: string }>
}

type FilePreviewModal = {
  kind: "file"
  item: UploadedFile
}

type SlidePreviewModal = {
  kind: "slide"
  url: string
  name: string
}

type PreviewModal = FilePreviewModal | SlidePreviewModal
type SlideFeedItem = {
  index: number
  status: "pending" | "ready" | "failed"
  imageUrl: string
}

const config = useRuntimeConfig()

const presentationPrompt = ref("")
const slideCount = ref(2)
const slideCountOptions = Array.from({ length: 14 }, (_, index) => index + 2)
const workType = ref<WorkType>("student")
const showScript = ref(true)

const showVideoAssistModal = ref(false)
const videoAssistUrl = "https://s3.akarmain.ru/S/sbs.mp4"
const hoveredFileName = ref<string | null>(null)
let filePopoverCloseTimer: ReturnType<typeof setTimeout> | null = null

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

const showVideoAssistButton = computed(() => Boolean(presentationId.value))
const isViewerMode = computed(() => (
  Boolean(isSubmitting.value || presentationId.value || status.value || slides.value.length)
))
const isTerminalStatus = computed(() => (
  ["completed", "completed_with_errors", "failed"].includes(status.value || "")
))

const progressTitle = computed(() => {
  if (status.value === "completed") {
    return `Готово ${slidesReady.value} из ${slidesTotal.value || slideCount.value}`
  }
  if (status.value === "completed_with_errors") {
    return `Готово с ошибками ${slidesReady.value} из ${slidesTotal.value || slideCount.value}`
  }
  if (status.value === "failed") {
    return "Генерация завершилась с ошибкой"
  }
  if (status.value === "running") {
    const total = slidesTotal.value || slideCount.value
    const current = Math.max(1, Math.min(total, slidesReady.value + 1))
    return `Идет генерация ${current} из ${total}`
  }
  if (status.value === "queued" || isSubmitting.value) {
    return "Запуск генерации..."
  }
  return "Ожидание генерации"
})

const scenarioPreviewText = computed(() => {
  const text = scriptText.value.trim()
  if (text) {
    return text
  }
  if (isSubmitting.value || status.value === "queued" || status.value === "running") {
    return "Сценарий формируется..."
  }
  return "Сценарий пока недоступен."
})

const slidesFeed = computed<SlideFeedItem[]>(() => {
  const ordered = [...slides.value]
    .sort((a, b) => a.index - b.index)
    .map((slide) => ({
      index: slide.index,
      status: slide.status,
      imageUrl: slide.imageUrl || "",
    }))

  const total = slidesTotal.value || ordered.length || slideCount.value
  if (isTerminalStatus.value) {
    if (ordered.length) {
      return ordered
    }
    return Array.from({ length: total }, (_, idx) => ({
      index: idx + 1,
      status: "pending" as const,
      imageUrl: "",
    }))
  }

  const readyCount = ordered.filter((slide) => slide.status === "ready").length
  const visibleCount = Math.max(1, Math.min(total, readyCount + 1))
  if (!ordered.length) {
    return Array.from({ length: visibleCount }, (_, idx) => ({
      index: idx + 1,
      status: "pending" as const,
      imageUrl: "",
    }))
  }

  const byIndex = new Map(ordered.map((slide) => [slide.index, slide]))
  const feed: SlideFeedItem[] = []
  for (let index = 1; index <= visibleCount; index += 1) {
    const existing = byIndex.get(index)
    feed.push(existing || {
      index,
      status: "pending",
      imageUrl: "",
    })
  }
  return feed
})

const isUploading = ref(false)
const errorMessage = ref("")
const uploadedFiles = ref<UploadedFile[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const previewModal = ref<PreviewModal | null>(null)

const previewImageUrl = computed(() => {
  if (!previewModal.value) {
    return ""
  }
  if (previewModal.value.kind === "file") {
    return previewModal.value.item.previewUrl
  }
  return previewModal.value.url
})

const previewImageName = computed(() => {
  if (!previewModal.value) {
    return "preview"
  }
  if (previewModal.value.kind === "file") {
    return previewModal.value.item.name
  }
  return previewModal.value.name
})

const uploadImageUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadImagePath}`,
)
const uploadListUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadListPath}`,
)
const uploadDeleteBaseUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadDeleteBasePath}`,
)
const uploadPreviewBaseUrl = computed(
  () => `${config.public.apiBase}${config.public.uploadPreviewBasePath}`,
)

const normalizeAssetKey = (value: string) => {
  const normalized = value
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}_-]+/gu, "_")
    .replace(/[_-]{2,}/g, "_")
    .replace(/^[_-]+|[_-]+$/g, "")
  return normalized || "file"
}

const previewUrlFor = (filename: string) => (
  `${uploadPreviewBaseUrl.value}${encodeURIComponent(filename)}`
)

const clearFilePopoverCloseTimer = () => {
  if (filePopoverCloseTimer) {
    clearTimeout(filePopoverCloseTimer)
    filePopoverCloseTimer = null
  }
}

const openFilePopover = (fileName: string) => {
  clearFilePopoverCloseTimer()
  hoveredFileName.value = fileName
}

const scheduleCloseFilePopover = (fileName: string) => {
  clearFilePopoverCloseTimer()
  filePopoverCloseTimer = setTimeout(() => {
    if (hoveredFileName.value === fileName) {
      hoveredFileName.value = null
    }
    filePopoverCloseTimer = null
  }, 120)
}

const onFilePopoverOpenChange = (fileName: string, open: boolean) => {
  if (open) {
    openFilePopover(fileName)
    return
  }
  if (hoveredFileName.value === fileName) {
    hoveredFileName.value = null
  }
}

const toUploadedFile = (filename: string): UploadedFile => ({
  name: filename,
  assetKey: normalizeAssetKey(filename.replace(/\.[^.]+$/, "")),
  status: "uploaded",
  previewUrl: previewUrlFor(filename),
  isDeleting: false,
})

const loadUploadedFiles = async () => {
  try {
    const data = await $fetch<UploadListResponse>(uploadListUrl.value)
    uploadedFiles.value = data.files
      .filter((file) => !file.filename.startsWith("."))
      .map((file) => toUploadedFile(file.filename))
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
    if (hoveredFileName.value === item.name) {
      hoveredFileName.value = null
    }
    if (previewModal.value?.kind === "file" && previewModal.value.item.name === item.name) {
      closePreview()
    }
  } catch {
    errorMessage.value = "Ошибка сети при удалении файла."
  } finally {
    item.isDeleting = false
  }
}

const buildFilesPayload = () => {
  return uploadedFiles.value
    .filter((file) => !file.name.startsWith("."))
    .map((file) => ({
      key: normalizeAssetKey(file.assetKey),
      fileId: file.name,
      originalName: file.name,
    }))
}

const submitPresentation = async () => {
  if (!presentationPrompt.value.trim()) {
    return
  }
  await createPresentation({
    prompt: presentationPrompt.value.trim(),
    slideCount: Math.max(2, Math.min(15, slideCount.value || 2)),
    workType: workType.value,
    showScript: showScript.value,
    files: buildFilesPayload(),
  })
}

const openFilePreview = (item: UploadedFile) => {
  previewModal.value = {
    kind: "file",
    item,
  }
}

const openSlidePreview = (slide: { index: number, imageUrl: string }) => {
  previewModal.value = {
    kind: "slide",
    url: absoluteUrl(slide.imageUrl),
    name: `slide ${slide.index}`,
  }
}

const closePreview = () => {
  previewModal.value = null
}

onMounted(() => {
  void loadUploadedFiles()
})

onBeforeUnmount(() => {
  clearFilePopoverCloseTimer()
})
</script>

<style scoped>
.workspace-page {
  position: relative;
  height: calc(100vh - 4rem);
  padding: 10px;
  overflow: hidden;
}

.idle-state {
  height: 100%;
  border: 1px solid hsl(var(--border));
  border-radius: 20px;
  background: hsl(var(--background));
  display: flex;
  align-items: center;
  justify-content: center;
}

.idle-card {
  width: min(930px, 92vw);
  border: 1px solid hsl(var(--border));
  border-radius: 26px;
  background: hsl(var(--card));
  padding: 14px;
}

.prompt-input {
  width: 100%;
  height: 130px;
  resize: none;
  border: none;
  background: transparent;
  font-size: 34px;
  line-height: 1.25;
  outline: none;
}

.prompt-input.compact {
  height: 92px;
  font-size: 13px;
}

.idle-controls {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.compact-row {
  margin-top: 6px;
}

.mini-select-wrap {
  min-width: 86px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.mini-label {
  font-size: 10px;
  color: hsl(var(--muted-foreground));
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.mini-select {
  height: 36px;
  border-radius: 12px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  padding: 0 10px;
  font-size: 13px;
  font-weight: 600;
  outline: none;
}

.launch-btn {
  margin-left: auto;
  width: 52px;
  height: 52px;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  font-size: 24px;
  font-weight: 800;
  padding: 0;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.switch-chip {
  min-height: 34px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  justify-content: flex-start;
  gap: 8px;
}

.thumb-strip {
  margin-top: 8px;
  display: flex;
  gap: 7px;
  overflow-x: auto;
  overflow-y: visible;
  padding-bottom: 2px;
}

.idle-thumb-strip {
  margin-top: 8px;
  min-height: 102px;
}

.thumb-key-label {
  margin: 4px 0 0;
  max-width: 66px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 10px;
  color: hsl(var(--muted-foreground));
  text-align: center;
}

.thumb-wrap {
  position: relative;
  flex: 0 0 auto;
}

.upload-tile,
.thumb-tile {
  width: 66px;
  height: 66px;
  border-radius: 14px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--muted));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  font-weight: 800;
  padding: 0;
}

.thumb-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 13px;
}

.file-key-popover {
  width: 220px;
  padding: 8px;
}

.file-key-row {
  display: flex;
  gap: 6px;
  align-items: center;
}

.key-input,
.modal-key-input {
  width: 100%;
  height: 30px;
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  padding: 0 8px;
  font-size: 12px;
  outline: none;
}

.delete-mini {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid hsl(var(--border));
  color: #dc2626;
  font-weight: 700;
  padding: 0;
}

.viewer-state {
  height: 100%;
  border: 1px solid hsl(var(--border));
  border-radius: 20px;
  background: hsl(var(--background));
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 10px;
  padding: 10px;
}

.viewer-sidebar {
  min-height: 0;
  border: 1px solid hsl(var(--border));
  border-radius: 16px;
  background: hsl(var(--card));
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow: auto;
}

.side-card {
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
  background: hsl(var(--background));
  padding: 8px;
}

.viewer-actions {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.generate-btn {
  height: 34px;
  border-radius: 10px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  font-size: 13px;
  font-weight: 700;
}

.section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
}

.script-block {
  margin-top: 6px;
  max-height: 180px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 11px;
  line-height: 1.4;
}

.script-block-placeholder {
  color: hsl(var(--muted-foreground));
  font-style: italic;
}

.viewer-content {
  min-height: 0;
  border: 1px solid hsl(var(--border));
  border-radius: 16px;
  background: hsl(var(--card));
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.progress-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.download-btn {
  height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid hsl(var(--border));
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
}

.slides-feed {
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.slide-row {
  border: 1px solid hsl(var(--border));
  border-radius: 12px;
  background: hsl(var(--background));
  padding: 8px;
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr);
  gap: 8px;
}

.slide-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  justify-content: center;
}

.slide-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.slide-status {
  margin: 0;
  font-size: 11px;
  color: hsl(var(--muted-foreground));
}

.slide-preview,
.slide-pending {
  width: 100%;
  min-height: 100px;
  border-radius: 10px;
  border: 1px solid hsl(var(--border));
  overflow: hidden;
}

.slide-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: hsl(var(--muted));
}

.slide-pending {
  display: flex;
  align-items: center;
  justify-content: center;
  color: hsl(var(--muted-foreground));
  font-size: 12px;
}

.preview-modal-card {
  width: min(92vw, 1300px);
  max-height: 92vh;
  border: 1px solid hsl(var(--border));
  border-radius: 14px;
  background: hsl(var(--background));
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.preview-modal-image {
  width: 100%;
  max-height: calc(92vh - 68px);
  object-fit: contain;
  background: hsl(var(--muted));
}

.preview-modal-footer {
  border-top: 1px solid hsl(var(--border));
  padding: 8px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.video-assist-btn {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.16);
}

.fade-in {
  animation: fadeIn 250ms ease-out;
}

.slide-up {
  animation: slideUp 300ms ease-out;
}

.panel-appear {
  animation: panelAppear 220ms ease-out;
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
    transform: translateY(8px);
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

@media (max-width: 1200px) {
  .idle-card {
    width: min(96vw, 780px);
  }

  .viewer-state {
    grid-template-columns: 1fr;
  }

  .slide-row {
    grid-template-columns: 1fr;
  }

  .prompt-input {
    font-size: 22px;
  }

  .mini-select {
    font-size: 16px;
  }

  .video-assist-btn {
    right: 12px;
    top: auto;
    bottom: 12px;
    transform: none;
  }
}
</style>
