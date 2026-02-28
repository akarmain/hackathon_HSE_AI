type WorkType = "school" | "student" | "academic"

type PresentationFileRef = {
  key: string
  fileId: string
  originalName?: string
  mimeType?: string
}

type CreatePresentationPayload = {
  prompt: string
  slideCount: number
  workType: WorkType
  showScript: boolean
  files: PresentationFileRef[]
}

type SlideStatus = "pending" | "ready" | "failed"
type PresentationStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"

type PresentationSlide = {
  index: number
  imageUrl: string
  status: SlideStatus
}

type PresentationStatusResponse = {
  status: PresentationStatus
  slidesReady: number
  slidesTotal: number
  slides: PresentationSlide[]
  scriptText?: string | null
  downloadUrl?: string | null
}

const TERMINAL_STATUSES = new Set<PresentationStatus>([
  "completed",
  "completed_with_errors",
  "failed",
])

export const usePresentationGenerator = () => {
  const config = useRuntimeConfig()
  const apiBase = String(config.public.apiBase || "")
  const presentationsPath = String(config.public.presentationsPath || "/api/presentations")

  const presentationId = ref<string | null>(null)
  const status = ref<PresentationStatus | null>(null)
  const slidesReady = ref(0)
  const slidesTotal = ref(0)
  const slides = ref<PresentationSlide[]>([])
  const scriptText = ref("")
  const downloadUrl = ref("")
  const isSubmitting = ref(false)
  const isPolling = ref(false)
  const errorMessage = ref("")

  let pollTimer: ReturnType<typeof setTimeout> | null = null

  const presentationsBaseUrl = computed(() => `${apiBase}${presentationsPath}`)

  const absoluteUrl = (path: string) => {
    if (!path) {
      return ""
    }
    if (path.startsWith("http://") || path.startsWith("https://")) {
      return path
    }
    return `${apiBase}${path}`
  }

  const resetState = () => {
    stopPolling()
    presentationId.value = null
    status.value = null
    slidesReady.value = 0
    slidesTotal.value = 0
    slides.value = []
    scriptText.value = ""
    downloadUrl.value = ""
    errorMessage.value = ""
  }

  const applyStatus = (payload: PresentationStatusResponse) => {
    status.value = payload.status
    slidesReady.value = payload.slidesReady
    slidesTotal.value = payload.slidesTotal
    slides.value = payload.slides
    scriptText.value = payload.scriptText || ""
    downloadUrl.value = payload.downloadUrl ? absoluteUrl(payload.downloadUrl) : ""
  }

  const pollStatus = async () => {
    if (!presentationId.value) {
      return
    }

    try {
      const response = await fetch(`${presentationsBaseUrl.value}/${presentationId.value}/status`)
      const payload = (await response.json()) as PresentationStatusResponse | { detail?: string }
      if (!response.ok) {
        errorMessage.value = "detail" in payload && payload.detail ? payload.detail : "Status polling failed."
        stopPolling()
        return
      }

      applyStatus(payload as PresentationStatusResponse)
      if (status.value && TERMINAL_STATUSES.has(status.value)) {
        stopPolling()
      }
    } catch {
      errorMessage.value = "Network error while polling presentation status."
      stopPolling()
    }
  }

  const startPolling = () => {
    stopPolling()
    isPolling.value = true

    const tick = async () => {
      await pollStatus()
      if (isPolling.value) {
        pollTimer = setTimeout(tick, 1500)
      }
    }
    void tick()
  }

  const stopPolling = () => {
    isPolling.value = false
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  const createPresentation = async (payload: CreatePresentationPayload) => {
    resetState()
    isSubmitting.value = true
    try {
      const response = await fetch(presentationsBaseUrl.value, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      const data = (await response.json()) as
        | { presentationId: string, status: PresentationStatus }
        | { detail?: string }
      if (!response.ok) {
        errorMessage.value = "detail" in data && data.detail ? data.detail : "Presentation creation failed."
        return
      }

      presentationId.value = (data as { presentationId: string }).presentationId
      status.value = (data as { status: PresentationStatus }).status
      startPolling()
    } catch {
      errorMessage.value = "Network error while creating presentation."
    } finally {
      isSubmitting.value = false
    }
  }

  onBeforeUnmount(() => {
    stopPolling()
  })

  return {
    presentationId,
    status,
    slidesReady,
    slidesTotal,
    slides,
    scriptText,
    downloadUrl,
    isSubmitting,
    isPolling,
    errorMessage,
    createPresentation,
    pollStatus,
    startPolling,
    stopPolling,
    resetState,
    absoluteUrl,
  }
}
