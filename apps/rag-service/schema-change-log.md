# rag-service schema change log

> 用于 v0.x 原型阶段记录数据库结构变化。进入 v1.0 前需切换 Alembic。

## 模板
- date:
- author:
- change:
- files:
- migration_sql_updated: yes/no
- backward_compatible: yes/no
- notes:

## 2026-03-26
- date: 2026-03-26
- author: codex
- change: 新增 v0.x 数据库策略说明，保留 `create_all` 开关并规范阶段化迁移策略。
- files: `app/config.py`, `app/main.py`, `docs/engineering/fastapi-development-standards.md`
- migration_sql_updated: no
- backward_compatible: yes
- notes: 当前为本地原型阶段，未引入 Alembic。

## 2026-03-26
- date: 2026-03-26
- author: codex
- change: 新增用户/团队/知识库权限域模型（users, teams, team_memberships, knowledge_bases, knowledge_base_memberships）。
- files: `app/models/identity.py`, `infra/db/migrations/0001_init.sql`
- migration_sql_updated: yes
- backward_compatible: yes
- notes: 权限规则为团队成员默认 viewer，`knowledge_base_memberships` 仅承载例外授权（owner/editor/viewer）。

## 2026-04-01
- date: 2026-04-01
- author: codex
- change: 将单文件 `models.py` 和 `schemas.py` 拆分为包目录，按 source/index_job/identity 分域维护，并通过 `__init__.py` 统一导出保持导入兼容。
- files: `app/models/`, `app/schemas/`, `README.md`
- migration_sql_updated: no
- backward_compatible: yes
- notes: 仅结构重构，无表结构变更。

## 2026-04-01
- date: 2026-04-01
- author: codex
- change: 补齐 Sprint 01 权限与审计：成员授权接口增加操作者字段与越权拦截（`PERMISSION_DENIED`），新增 `audit_log` ORM 写入授权变更审计，补充权限矩阵与越权测试。
- files: `app/api/teams.py`, `app/api/knowledge_bases.py`, `app/models/audit.py`, `app/services/audit.py`, `app/schemas/identity.py`, `tests/test_access_control.py`, `tests/test_user_team_kb_access.py`
- migration_sql_updated: no
- backward_compatible: no
- notes: `POST /teams/{team_id}/members` 与 `POST /knowledge-bases/{kb_id}/members` 请求体新增必填 `operator_user_id`。

## 2026-04-01
- date: 2026-04-01
- author: codex
- change: 引入最小异常规范与事务规范模板：新增统一错误码、业务异常、UoW 事务管理；用户/团队/知识库接口迁移为 API 薄层 + Service 业务层。
- files: `app/core/error_codes.py`, `app/core/errors.py`, `app/core/uow.py`, `app/core/exceptions.py`, `app/api/users.py`, `app/api/teams.py`, `app/api/knowledge_bases.py`, `app/services/users_service.py`, `app/services/teams_service.py`, `app/services/knowledge_bases_service.py`, `docs/engineering/fastapi-development-standards.md`
- migration_sql_updated: no
- backward_compatible: yes
- notes: 重构仅涉及代码结构与错误处理方式，接口路径和返回结构保持不变。

## 2026-04-01
- date: 2026-04-01
- author: codex
- change: 启动 Sprint 02 最小闭环：新增检索与问答接口（`/api/v1/retrieval/query`, `/api/v1/qa/ask`），补齐内容模型映射（`knowledge_document`, `knowledge_chunk`），并加入权限拒绝与引用返回测试。
- files: `app/models/content.py`, `app/schemas/retrieval.py`, `app/schemas/qa.py`, `app/api/retrieval.py`, `app/api/qa.py`, `app/services/retrieval_service.py`, `app/services/qa_service.py`, `tests/test_retrieval_qa.py`, `docs/iterations/v0.1/sprint-03-retrieval-qa-plan.md`
- migration_sql_updated: no
- backward_compatible: yes
- notes: 当前为原型实现，检索为词项打分，问答为模板编排；后续迭代接入向量检索与 LLM 网关。

## 2026-04-01
- date: 2026-04-01
- author: codex
- change: 补齐 Sprint 02 最小 ingest-index 单通道：新增本地目录 ingestion + chunk 写入 + index_job 状态流转服务，并接入任务 API。
- files: `app/services/index_jobs_service.py`, `app/api/index_jobs.py`, `app/core/error_codes.py`, `tests/test_ingest_index_pipeline.py`, `docs/iterations/v0.1/sprint-02-ingest-index-plan.md`
- migration_sql_updated: no
- backward_compatible: yes
- notes: 当前仅支持 `local` source（.md/.txt），`wiki` 与 embedding/vector 通道后续迭代。
