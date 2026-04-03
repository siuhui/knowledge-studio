# v0.1 实施进展

## 已完成（2026-03-24）
- 初始化 `apps/rag-service` FastAPI 项目骨架。
- 实现健康检查接口：`/health/live`、`/health/ready`。
- 实现数据源接口：`POST /api/v1/sources`、`GET /api/v1/sources`。
- 实现索引任务接口：`POST /api/v1/index/jobs`、`GET /api/v1/index/jobs/{job_id}`。
- 建立 SQLAlchemy 最小数据模型：`knowledge_source`、`index_job`。
- 新增数据库初始化脚本：`infra/db/migrations/0001_init.sql`（含 v0.1 核心表）。
- 完成本地虚拟环境依赖安装与应用导入校验。

## 待完成（下一步）
- 接入真实 connector（object_storage/wiki）任务执行器。
- 实现 index job worker（queued -> running -> success/failed 状态流转）。
- 打通 chunk 写入与混合检索最小链路。

## 已完成（2026-04-01）
- Sprint 02 最小链路落地：`ingest -> chunk -> index`（原型通道）。
- 新增 `knowledge_document/knowledge_chunk` ORM 映射并接入检索链路。
- `POST /api/v1/index/jobs` 可触发索引任务并输出状态流转与任务统计。
- 新增检索/问答最小 API：
  - `POST /api/v1/retrieval/query`
  - `POST /api/v1/qa/ask`
- 新增测试覆盖：ingest 成功、source 状态校验、检索命中、权限拒绝。

## 已完成（2026-04-03）
- 完成上传资产管理开发前文档冻结：
  - `uploaded_object` 表结构与状态机（`uploaded/indexed/failed/deleted`）
  - `complete` 阶段 `head_object` 校验与幂等 upsert 语义
  - 上传管理接口契约：列表/详情/删除
  - 与 `index_job` 成功/失败状态联动规则
- 明确 `source`（连接配置）与 `uploaded_object`（文件台账）职责边界。
