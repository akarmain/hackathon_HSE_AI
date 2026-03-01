from enum import StrEnum

from pydantic import BaseModel, Field


class PresentationStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"


class SlideStatus(StrEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class WorkType(StrEnum):
    school = "school"
    student = "student"
    academic = "academic"

class PresentationFileRef(BaseModel):
    key: str
    fileId: str
    originalName: str | None = None
    mimeType: str | None = None


class CreatePresentationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    slideCount: int = Field(ge=2, le=15)
    workType: WorkType
    showScript: bool = True
    files: list[PresentationFileRef] = Field(default_factory=list)


class CreatePresentationResponse(BaseModel):
    presentationId: str
    status: PresentationStatus


class PresentationSlideInfo(BaseModel):
    index: int
    imageUrl: str
    status: SlideStatus


class PresentationStatusResponse(BaseModel):
    status: PresentationStatus
    slidesReady: int
    slidesTotal: int
    slides: list[PresentationSlideInfo]
    scriptText: str | None = None
    downloadUrl: str | None = None


class PresentationPromptTestRequest(BaseModel):
    prompt: str = Field(min_length=1)
    slideCount: int = Field(ge=2, le=15)
    workType: WorkType
    showScript: bool = True
    files: list[PresentationFileRef] = Field(default_factory=list)
    includeHtml: bool = True
    allowImageGeneration: bool = False


class PresentationSlidePreview(BaseModel):
    index: int
    title: str
    layoutHint: str
    html: str | None = None


class PresentationPromptTestResponse(BaseModel):
    scenario: dict
    slides: list[PresentationSlidePreview]
    errors: list[str] = Field(default_factory=list)
