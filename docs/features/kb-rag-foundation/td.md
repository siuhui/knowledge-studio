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
- 打通 ingest -> index -> retrieve -> generate 主链路
- 保证引用可追溯、权限可控、指标可观测
- 保留可拆分接口，避免后续重构推倒

---

## 2. 逻辑模块

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

- API 与业务：NestJS（TypeScript）
- RAG 能力：FastAPI（Python）
- DB：PostgreSQL + pgvector
- 全文检索：OpenSearch
- 缓存：Redis
- 队列：RabbitMQ
- 对象存储：MinIO（或云对象存储）

v1.0 原则：
- 先稳定可用，再追求极致性能
- 组件支持后续替换（向量库/模型供应商）

---

## 4. 核心链路设计

### 4.1 入库链路
connector sync -> raw store -> parse & clean -> chunk -> embedding -> index upsert -> publish index_version

### 4.2 问答链路
query -> auth filter -> hybrid retrieve -> rerank -> context build -> LLM generate -> citation bind -> response

### 4.3 反馈链路
feedback submit -> classify issue -> push evaluation backlog -> weekly report

---

## 5. 可观测与稳定性

- 指标：延迟、错误率、索引任务时长、召回率、引用覆盖率
- 日志：统一 trace_id 串联 ingest/retrieve/generate
- 降级：
  - 模型服务不可用时返回“仅检索摘要模式”
  - OpenSearch 异常时仅向量召回（降级开关）

---

## 6. 安全设计

- 检索前置鉴权：仅在授权文档集合内召回
- 审计记录：问题、命中文档、输出摘要、操作人
- 敏感信息：日志脱敏与导出脱敏

---

## 7. 演进预留

为阶段 2 预留拆分点：
- `retrieval`、`generation` 独立服务化
- `evaluation` 独立任务服务
- LLM Gateway 独立化

为阶段 3 预留：
- tool registry
- agent runtime
- graph index adaptor




