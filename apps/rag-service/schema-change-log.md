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
