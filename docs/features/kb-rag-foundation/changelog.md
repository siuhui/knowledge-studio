# Changelog：kb-rag-foundation

## v1.0
- 新增 0->1 范围定义（接入、切片、混合检索、RAG 问答、引用、权限审计）。
- 新增技术设计（模块化单体、异步任务链路、可演进拆分边界）。
- 新增 API 契约草案与数据迁移方案。

## v0.1
- 新增 `ingest-workflow.md`：从用户场景用例出发，细化 ingest 操作流程、状态流转、当前实现边界与目标对象存储方案。
- 调整数据接入范围：移除 local connector 的正式规划定位，统一为 object storage / wiki。
- 补充上传资产台账设计：新增 `uploaded_object` 表、状态机与 `source` 职责边界。
- 补充上传管理契约：`GET /uploads`、`GET /uploads/{id}`、`DELETE /uploads/{id}`。
- 明确索引任务状态联动：`uploaded -> indexed/failed`。
