# v1.0 数据模型与迁移方案

## 1. 目标

定义 v1.0 最小可用数据模型，支持文档入库、切片索引、问答引用、反馈评测与审计。

---

## 2. 核心表（PostgreSQL）

### 2.1 knowledge_source
- `id` (pk)
- `name`
- `type` (local/wiki)
- `config_json`
- `sync_mode` (scheduled/manual)
- `status`
- `created_at` `updated_at`

### 2.2 knowledge_document
- `id` (pk)
- `source_id` (fk)
- `title`
- `path`
- `doc_version`
- `department`
- `permission_scope`
- `status`
- `updated_at`

### 2.3 knowledge_chunk
- `id` (pk)
- `doc_id` (fk)
- `chunk_index`
- `content`
- `token_count`
- `index_version`
- `embedding vector`
- `permission_scope`

### 2.4 qa_session / qa_message
- 会话与消息，记录用户 query 与系统 answer
- `qa_message` 记录 `confidence`、`grounded`

### 2.5 qa_citation
- `message_id` (fk)
- `doc_id` `chunk_id`
- `score`

### 2.6 feedback_record
- `message_id` (fk)
- `rating` (up/down)
- `comment`
- `created_at`

### 2.7 index_job
- `source_id`
- `mode`
- `status`
- `error_message`
- `started_at` `finished_at`

### 2.8 audit_log
- `actor_id`
- `action`
- `resource_type` `resource_id`
- `trace_id`
- `created_at`

---

## 3. 索引策略

- 向量索引：pgvector（HNSW/IVFFLAT 视规模选择）
- 全文索引：OpenSearch（BM25）
- 召回策略：向量与全文分数融合

---

## 4. Migration 规则

- 所有 schema 变更必须以 migration 文件提交
- 禁止直接修改线上表结构
- 破坏性变更流程：
  1) 增量加字段（兼容）
  2) 双写验证
  3) 流量切换
  4) 清理旧字段

---

## 5. 回滚方案

- 结构回滚：保留旧字段至少一个版本周期
- 索引回滚：保留 `active_index_version-1`
- Prompt 回滚：保留最近 3 个稳定版本

---

## 6. 数据质量检查

上线前最小检查：
- 空 chunk 比例
- 超长 chunk 比例
- 重复 chunk 比例
- 无权限标记记录比例
