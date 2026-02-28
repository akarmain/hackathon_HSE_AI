from pydantic import BaseModel, Field


class GenAITextRequest(BaseModel):
    question: str = Field(min_length=1)
    network_id: str | None = None
    model: str | None = None
    system: str | None = None


class GenAITextResponse(BaseModel):
    answer: str
    raw: dict


class GenAIImageRequest(BaseModel):
    prompt: str = Field(min_length=1)
    network_id: str | None = None
    model: str = "standard"
    width: int = 1024
    height: int = 576


class GenAIImageResponse(BaseModel):
    filename: str
    stored_path: str
    source_url: str | None = None
    raw: dict
