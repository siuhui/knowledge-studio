# API 契约（当前实现对齐 + 开发前补充，v0.1）

## 1. 设计原则
- REST + JSON
- OpenAPI-first
- 所有响应包含 `trace_id`
- 统一响应结构：`code/message/data/trace_id`

---

## 2. API 列表

### 2.0 上传（对象存储直传）
`POST /api/v1/uploads/presign`

请求：
```json
{
  "user_id": "string",
  "kb_id": "string",
  "filename": "handbook.pdf",
  "content_type": "application/pdf"
}
```

响应：
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "provider": "minio",
    "bucket": "kb-source",
    "object_key": "kb/<kb_id>/<kb_slug>/raw/20260403/<ulid>_<hash>.pdf",
    "upload_method": "POST",
    "upload_url": "https://...",
    "upload_fields": {
      "key": "...",
      "policy": "...",
      "x-amz-signature": "...",
      "Content-Type": "application/pdf",
      "x-amz-meta-original-filename": "handbook.pdf"
    },
    "expires_in": 900,
    "max_size_bytes": 20971520
  },
  "trace_id": "string"
}
```

`POST /api/v1/uploads/complete`

请求：
```json
{
  "kb_id": "string",
  "bucket": "kb-source",
  "object_key": "kb/<kb_id>/<kb_slug>/raw/20260403/<ulid>_<hash>.pdf",
  "uploader_user_id": "string"
}
```

行为语义：
- 服务端执行 `head_object` 校验：对象存在、`ContentLength > 0`、大小上限、`ContentType` 基本匹配。
- 服务端以 `bucket+object_key` 幂等写入或更新 `uploaded_object` 记录。
- 新记录状态置为 `uploaded`。

响应：
```json
{
  "code": "OK",
  "message": "accepted",
  "data": {
    "accepted": true,
    "uploaded_object_id": "string"
  },
  "trace_id": "string"
}
```

### 2.1 上传管理（开发待实现，先冻结契约）
`GET /api/v1/uploads?kb_id=<id>&user_id=<id>&page=1&page_size=20`

响应：
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [
      {
        "id": "string",
        "kb_id": "string",
        "bucket": "kb-source",
        "object_key": "kb/...",
        "original_filename": "handbook.pdf",
        "content_type": "application/pdf",
        "size_bytes": 102400,
        "etag": "\"abc\"",
        "status": "uploaded",
        "uploader_user_id": "string",
        "created_at": "2026-04-03T10:00:00Z"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 1
  },
  "trace_id": "string"
}
```

`GET /api/v1/uploads/{id}?user_id=<id>`：返回单条详情（字段同上，补充 `index_error_message`）。

`DELETE /api/v1/uploads/{id}?user_id=<id>`
- 语义：软删除 `uploaded_object.status=deleted`，并删除对象存储文件（可异步）。
- 响应：`accepted=true`。

### 2.2 问答
`POST /api/v1/qa/ask`

### 2.3 检索
`POST /api/v1/retrieval/query`

### 2.4 索引任务
`POST /api/v1/index/jobs`

`GET /api/v1/index/jobs/{job_id}`

状态语义：
- 当前实现：`POST /api/v1/index/jobs` 在接口内同步执行最小链路，返回时可能是 `success` 或 `failed`。
- 预留异步化：枚举保持 `queued/running/success/failed`。
- 联动要求：
  - job 成功 -> 关联 `uploaded_object.status: uploaded -> indexed`
  - job 失败 -> 关联 `uploaded_object.status: uploaded -> failed` 且写入失败原因

对象键规则：
- `kb/{kb_id}/{kb_slug}/raw/{yyyymmdd}/{ulid}_{hash}{ext}`

上传约束：
- 通过 presigned POST policy 限制上传大小（`content-length-range`）。
- `complete` 阶段做 `head_object` 校验。

---

## 3. 错误码规范

- `PERMISSION_DENIED`
- `VALIDATION_ERROR`
- `INDEX_JOB_NOT_FOUND`
- `KNOWLEDGE_SOURCE_NOT_FOUND`
- `SOURCE_NOT_ACTIVE`
- `SOURCE_TYPE_NOT_SUPPORTED`
- `UPLOAD_STORAGE_NOT_CONFIGURED`
- `UPLOAD_PRESIGN_FAILED`
- `UPLOAD_OBJECT_NOT_FOUND`
- `UPLOAD_OBJECT_EMPTY`
- `UPLOAD_OBJECT_TOO_LARGE`
- `UPLOAD_OBJECT_CONTENT_TYPE_MISMATCH`
- `UPLOADED_OBJECT_NOT_FOUND`（管理接口）

---

## 4. 兼容性要求

- `v1` 内新增字段仅可追加，不可删除/重命名既有字段
- 破坏性变更必须升级到 `v2`
