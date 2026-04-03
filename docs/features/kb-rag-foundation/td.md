# 功能 TD：RAG 基础能力

## 元信息
- feature_id: `kb-rag-foundation`
- owner: `TBD`
- status: `active`
- version_introduced: `v0.1`
- version_updated: `v0.1`

---
## 目标上线版本 v1.0

## 1. 设计目标

v1.0 采用“模块化单体 + 异步任务”方案，以最小复杂度完成可用闭环，并为阶段 2 服务化拆分预留边界。

目标：
- 打通 upload -> ingest -> index -> retrieve -> generate 主链路
- 保证引用可追溯、权限可控、指标可观测
- 保留可拆分接口，避免后续重构推倒

---

## 2. 逻辑模块

- `upload`：预签名、对象校验、上传台账
- `ingestion`：数据源同步、解析、清洗
- `indexing`：切片、embedding、索引写入
- `retrieval`：查询改写、混合召回、重排
- `generation`：Prompt 组装、答案生成、引用绑定
- `governance`：反馈、评测、审计
- `auth`：RBAC、租户隔离、资源鉴权

模块边界要求：
- 模块仅通过 service interface 交互
- 禁止跨模块直接访问内部 repository

---

## 3. 技术选型（v1.0）

- API 与业务：FastAPI（当前）
- DB：PostgreSQL + pgvector
- 全文检索：OpenSearch
- 缓存：Redis
- 队列：RabbitMQ（索引异步化阶段接入）
- 对象存储：MinIO（或云对象存储）

v1.0 原则：
- 先稳定可用，再追求极致性能
- 组件支持后续替换（向量库/模型供应商）

---

## 4. 核心链路设计

### 4.1 上传链路
client -> `uploads/presign` -> object storage POST -> `uploads/complete` -> `uploaded_object` upsert

关键约束：
- key 规则：`kb/{kb_id}/{kb_slug}/raw/{yyyymmdd}/{ulid}_{hash}{ext}`
- `complete` 必做 `head_object` 校验（存在、大小、类型）
- `bucket+object_key` 幂等

### 4.2 入库链路
ingest worker -> parse & clean -> chunk -> embedding -> index upsert -> publish index result

### 4.3 状态联动
- ingest/index 成功：`uploaded_object.status= indexed`
- ingest/index 失败：`uploaded_object.status= failed` + `index_error_message`

### 4.4 问答链路
query -> auth filter -> hybrid retrieve -> rerank -> context build -> LLM generate -> citation bind -> response

补充文档：
- `ingest-workflow.md`
- `upload-workflow.md`

---

## 5. 数据模型职责划分

- `source`：连接器配置，描述扫描位置和增量策略。
- `uploaded_object`：文件资产台账，描述文件元数据、状态和上传人。
- `knowledge_document` / `knowledge_chunk`：索引侧文档与切片实体。

设计原则：
- 配置实体（source）与文件实体（uploaded_object）分离。
- 用户管理动作（列表/详情/删除）只面向 `uploaded_object`。

---

## 6. 可观测与稳定性

- 指标：上传成功率、索引任务时长、索引成功率、检索延迟
- 日志：统一 `trace_id` 串联 upload/ingest/index/retrieve/generate
- 降级：
  - 对象存储异常时禁止 `presign` 并返回可识别错误码
  - 索引失败时保留上传记录并允许重试

---

## 7. 安全设计

- 上传前置鉴权：`editor/owner` 才可上传
- complete 作用域校验：`object_key` 必须 `startswith(kb/{kb_id}/...)`
- 审计记录：上传、删除、索引动作均记录 `actor_id` 与 `trace_id`

---

## 8. 演进预留

- `uploads` 后续支持分片上传与断点续传
- `indexing` 后续拆分异步 worker
- `retrieval`、`generation` 后续服务化
