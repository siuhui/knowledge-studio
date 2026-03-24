# v0.1 Sprint 01 Plan（数据接入与索引）

## 1. Sprint 目标
打通 ingest -> parse -> chunk -> embedding -> index 的最小可用链路。

## 2. 工作拆分（WBS）

### A. 数据接入
- A1: 实现 `local-folder` connector（增量扫描）
- A2: 实现 `wiki` connector（分页拉取 + 增量游标）
- A3: `knowledge_source` 配置校验与状态机（active/paused/error）

### B. 解析与清洗
- B1: 支持 PDF/Word/Markdown 解析
- B2: 页眉页脚、空白段、重复段清洗
- B3: 解析失败重试与死信记录

### C. 切片与向量化
- C1: 固定窗口+重叠切片策略
- C2: chunk 元数据（doc_id/chunk_index/token_count/permission_scope）
- C3: embedding 异步任务与批量写入

### D. 索引与任务跟踪
- D1: pgvector 写入与索引构建
- D2: OpenSearch 文本索引写入
- D3: `index_job` 生命周期（queued/running/success/failed）

### E. 可观测性
- E1: trace_id 贯穿任务链路
- E2: 指标：任务成功率、平均时长、失败率

## 3. 接口与数据变更
- API: `POST /api/v1/index/jobs`, `GET /api/v1/index/jobs/{id}`
- 表: `knowledge_source`, `knowledge_document`, `knowledge_chunk`, `index_job`

## 4. 验收标准（DoD）
- 可对指定数据源发起增量索引任务并成功完成
- 样本集文档入库成功率 >= 98%
- 索引任务失败可定位到错误原因

## 5. 风险与依赖
- 风险：解析器对复杂 PDF 不稳定
- 依赖：对象存储、消息队列、向量扩展启用

## 6. 输出物
- 功能演示脚本
- 索引任务看板截图/日志
- 回写到 `kb-rag-foundation/td.md`
