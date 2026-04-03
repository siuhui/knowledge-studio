# v0.1 数据模型与迁移方案（Ingest/Upload 阶段）

## 1. 目标

定义 v0.1 最小可用数据模型，支持上传资产管理、文档入库、切片索引与任务追踪。

---

## 2. 核心表（PostgreSQL）

### 2.1 source（原 knowledge_source）
- `id` (pk)
- `kb_id` (fk -> knowledge_bases.id)
- `name`
- `type` (object_storage/wiki)
- `config_json`
- `sync_mode` (scheduled/manual)
- `status`
- `created_at` `updated_at`

说明：
- `source` 表示“去哪里扫描数据”的连接配置（bucket/prefix、cursor、sync_mode）。
- 粒度是“一个数据源配置”，不是“一份文件”。

### 2.2 uploaded_object（新增）
- `id` (pk)
- `kb_id` (fk -> knowledge_bases.id)
- `bucket`
- `object_key`（唯一约束：`uk_uploaded_object_bucket_key`）
- `original_filename`
- `content_type`
- `size_bytes`
- `etag`
- `status` (`uploaded/indexed/failed/deleted`)
- `index_error_message` (nullable)
- `uploader_user_id` (fk -> users.id)
- `created_at` `updated_at`

说明：
- `uploaded_object` 是“单文件资产台账”，面向用户查看、追踪和删除管理。
- 上传完成（`complete`）时通过 `head_object` 获取真实 `size/content_type/etag` 并落库。
- `complete` 使用 `bucket+object_key` 幂等写入或更新（upsert）。

### 2.3 knowledge_document
- `id` (pk)
- `source_id` (fk)
- `title`
- `path`
- `doc_version`
- `department`
- `permission_scope`
- `status`
- `updated_at`

### 2.4 knowledge_chunk
- `id` (pk)
- `doc_id` (fk)
- `chunk_index`
- `content`
- `token_count`
- `index_version`
- `embedding vector`
- `permission_scope`

### 2.5 qa_session / qa_message
- 会话与消息，记录用户 query 与系统 answer
- `qa_message` 记录 `confidence`、`grounded`

### 2.6 qa_citation
- `message_id` (fk)
- `doc_id` `chunk_id`
- `score`

### 2.7 feedback_record
- `message_id` (fk)
- `rating` (up/down)
- `comment`
- `created_at`

### 2.8 index_job
- `source_id`
- `mode`
- `status`
- `error_message`
- `started_at` `finished_at`

### 2.9 audit_log
- `actor_id`
- `action`
- `resource_type` `resource_id`
- `trace_id`
- `created_at`

---

## 3. 状态联动规则

### 3.1 上传状态
- `uploaded`：对象已上传并通过 `complete` 校验落库。
- `indexed`：对应文件已成功完成 ingest->chunk->index。
- `failed`：索引失败，记录失败原因（`index_error_message`）。
- `deleted`：已软删除，不再对业务可见。

### 3.2 与 index_job 联动
- index_job 成功后，将关联 `uploaded_object.status` 从 `uploaded` 更新为 `indexed`。
- index_job 失败后，将关联 `uploaded_object.status` 更新为 `failed` 并写入原因。

---

## 4. source 与 uploaded_object 职责边界

- `source`：连接器/同步配置，描述“从哪里扫、如何增量扫”。
- `uploaded_object`：上传资产台账，描述“这个文件是什么、状态如何、由谁上传”。
- 两者互补，不互相替代。

---

## 5. 索引策略

- 向量索引：pgvector（HNSW/IVFFLAT 视规模选择）
- 全文索引：OpenSearch（BM25）
- 召回策略：向量与全文分数融合

---

## 6. Migration 规则

- 所有 schema 变更必须以 migration 文件提交
- 禁止直接修改线上表结构
- 破坏性变更流程：
  1) 增量加字段（兼容）
  2) 双写验证
  3) 流量切换
  4) 清理旧字段

---

## 7. 回滚方案

- 结构回滚：保留旧字段至少一个版本周期
- 索引回滚：保留 `active_index_version-1`
- Prompt 回滚：保留最近 3 个稳定版本

---

## 8. 数据质量检查

上线前最小检查：
- 空 chunk 比例
- 超长 chunk 比例
- 重复 chunk 比例
- 无权限标记记录比例
