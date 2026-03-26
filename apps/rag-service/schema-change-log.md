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
