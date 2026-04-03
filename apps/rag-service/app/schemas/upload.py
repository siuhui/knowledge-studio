from pydantic import BaseModel, Field


class UploadPresignRequest(BaseModel):
    user_id: str = Field(min_length=1)
    kb_id: str = Field(min_length=1)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=200)


class UploadPresignPayload(BaseModel):
    provider: str
    bucket: str
    object_key: str
    upload_method: str
    upload_url: str
    upload_fields: dict[str, str]
    expires_in: int
    max_size_bytes: int


class UploadCompleteRequest(BaseModel):
    kb_id: str = Field(min_length=1)
    bucket: str = Field(min_length=1, max_length=255)
    object_key: str = Field(min_length=1, max_length=1024)
    etag: str | None = None
    uploader_user_id: str | None = None


class UploadCompletePayload(BaseModel):
    accepted: bool
    uploaded_object_id: str | None = None


class UploadedObjectItem(BaseModel):
    id: str
    kb_id: str
    bucket: str
    object_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    etag: str | None = None
    status: str
    index_error_message: str | None = None
    uploader_user_id: str | None = None
    created_at: str
    updated_at: str


class UploadedObjectListPayload(BaseModel):
    items: list[UploadedObjectItem]
    page: int
    page_size: int
    total: int
