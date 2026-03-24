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
- 接入真实 connector（local/wiki）任务执行器。
- 实现 index job worker（queued -> running -> success/failed 状态流转）。
- 打通 chunk 写入与混合检索最小链路。

- 环境切换：Python 从 3.12 调整为 3.11.4（venv: .venv）。

