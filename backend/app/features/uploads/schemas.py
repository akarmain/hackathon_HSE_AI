from pydantic import BaseModel


class UploadImageResponse(BaseModel):
    filename: str
    stored_path: str
    content_type: str
    size: int


class UploadedFileItem(BaseModel):
    filename: str
    stored_path: str


class UploadListResponse(BaseModel):
    files: list[UploadedFileItem]


class RenameUploadRequest(BaseModel):
    filename: str
    new_filename: str


class DeleteUploadResponse(BaseModel):
    filename: str
    deleted: bool
