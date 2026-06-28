from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=200)


class PresignResponse(BaseModel):
    provider: str
    bucket: str
    object_key: str
    upload_url: str
    upload_fields: dict[str, str]
    expires_in: int
    max_size_bytes: int


class UploadCompleteRequest(BaseModel):
    bucket: str = Field(min_length=1, max_length=255)
    object_key: str = Field(min_length=1, max_length=1024)
    etag: str | None = None


class UploadCompleteResponse(BaseModel):
    accepted: bool
    object_key: str
    original_filename: str
    content_type: str
    size_bytes: int
