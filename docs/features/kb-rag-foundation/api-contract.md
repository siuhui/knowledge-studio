# v1.0 API 契约（草案）

## 1. 设计原则
- REST + JSON
- OpenAPI-first
- 所有响应包含 `trace_id`

---

## 2. API 列表

### 2.1 问答
`POST /api/v1/qa/ask`

请求：
```json
{
  "query": "string",
  "session_id": "string",
  "filters": {"department": "string", "time_range": "string"}
}
```

响应：
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "answer": "string",
    "citations": [{"doc_id": "d1", "chunk_id": "c1", "score": 0.87}],
    "confidence": "high",
    "grounded": true
  },
  "trace_id": "string"
}
```

### 2.2 检索
`POST /api/v1/retrieval/search`

请求：
```json
{
  "query": "string",
  "top_k": 10,
  "filters": {}
}
```

响应：
```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "hits": [{"doc_id": "d1", "chunk_id": "c1", "score": 0.9, "snippet": "..."}]
  },
  "trace_id": "string"
}
```

### 2.3 反馈
`POST /api/v1/feedback`

请求：
```json
{
  "session_id": "string",
  "message_id": "string",
  "rating": "up|down",
  "comment": "string"
}
```

响应：
```json
{
  "code": "OK",
  "message": "accepted",
  "data": {"feedback_id": "string"},
  "trace_id": "string"
}
```

### 2.4 索引任务
`POST /api/v1/index/jobs`

请求：
```json
{
  "source_id": "string",
  "mode": "incremental|full"
}
```

响应：
```json
{
  "code": "OK",
  "message": "accepted",
  "data": {"job_id": "string", "status": "queued"},
  "trace_id": "string"
}
```

`GET /api/v1/index/jobs/{job_id}` 返回任务状态与错误详情。

---

## 3. 错误码规范

- `AUTH_FORBIDDEN`
- `VALIDATION_ERROR`
- `INDEX_JOB_FAILED`
- `RAG_CONTEXT_INSUFFICIENT`
- `UPSTREAM_MODEL_TIMEOUT`

错误响应示例：
```json
{
  "code": "RAG_CONTEXT_INSUFFICIENT",
  "message": "insufficient grounded evidence",
  "data": null,
  "trace_id": "string"
}
```

---

## 4. 兼容性要求

- `v1` 内新增字段仅可追加，不可删除/重命名既有字段
- 破坏性变更必须升级到 `v2`
