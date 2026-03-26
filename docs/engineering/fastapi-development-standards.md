# FastAPI 开发规范（rag-service）

## 1. 目标

本规范用于约束 `apps/rag-service` 的开发质量，确保接口稳定、可维护、可测试、可运维。

---

## 2. 项目结构规范

推荐结构：
- `app/main.py`：应用装配与生命周期
- `app/core/`：配置、日志、异常处理、中间件
- `app/api/`：路由层（只做协议转换）
- `app/schemas/`：请求/响应模型（Pydantic）
- `app/models/`：ORM 模型
- `app/services/`：业务逻辑
- `app/repositories/`：数据访问
- `app/tasks/`：异步任务

要求：
- 路由层禁止直接写复杂业务。
- 路由层禁止直接拼装 SQL。

---

## 3. 配置管理规范

- 使用 `pydantic-settings`，环境变量前缀统一 `KB_`。
- 严禁在代码中硬编码凭据。
- 必须区分环境：`dev/test/prod`。
- 配置项需提供合理默认值，并在 README 记录。

---

## 4. 数据库规范（阶段化）

### 4.1 v0.x 本地原型阶段（单人开发）
- 允许使用 `create_all` 快速迭代。
- 必须维护 `schema-change-log` 记录结构变化。
- 必须维护可初始化数据库的 SQL 脚本（当前为 `infra/db/migrations/0001_init.sql`）。

### 4.2 v1.0 前（多人协作/准备上线）
- 必须切换到 Alembic 迁移。
- 禁止在 `main.py` 里做隐式 schema 变更。
- 每次 schema 变更必须可追溯、可回滚。

会话管理：
- 每请求一会话（依赖注入）。
- 统一事务边界：`commit/rollback` 由 service 层控制。
- 禁止在多个层级重复 `commit`。

---

## 5. API 设计规范

- 输入/输出必须使用 Pydantic 模型，禁止 `dict` 裸输入。
- 每个接口显式声明 `response_model`。
- 统一响应结构：`code/message/data/trace_id`。
- 错误返回走统一异常处理器，禁止各路由手写重复错误体。
- 路由按版本管理（`/api/v1/...`），破坏性变更升级版本。

---

## 6. 异常与日志规范

- 全局异常处理：业务异常、校验异常、未知异常分级处理。
- 结构化日志字段至少包含：`trace_id`、`path`、`method`、`latency_ms`、`status_code`。
- 生成 `trace_id` 的中间件统一注入并透传。
- 日志中禁止打印敏感信息。

---

## 7. 安全规范

- 生产环境必须开启鉴权（JWT/OIDC 至少一种）。
- 接口需做输入长度和枚举约束。
- 数据权限过滤应在查询阶段执行。
- 必须启用 CORS 白名单，不允许默认全开放。

---

## 8. 测试规范

最低要求：
- 单元测试：service/repository 关键逻辑
- API 测试：关键路由正反用例
- 覆盖率目标：核心模块 >= 80%

推荐工具：
- `pytest`
- `httpx` + FastAPI TestClient
- `pytest-asyncio`（如引入异步）

门禁：
- PR 必须通过 lint + test
- 新增接口必须带测试用例

---

## 9. 代码风格与静态检查

- 类型注解必填（公开函数和核心逻辑）
- 格式化：`black`
- 规范检查：`ruff`
- 类型检查：`mypy`

建议在 CI 中执行：
- `ruff check .`
- `black --check .`
- `mypy app`
- `pytest`

---

## 10. Docker 与运行规范

- 镜像使用 `python:3.11-slim`。
- 开发环境支持热更新（`uvicorn --reload`）。
- 生产环境禁止 `--reload`。
- 使用 `.dockerignore` 控制构建上下文，避免带入 `.venv`、数据库文件。

---

## 11. 当前阶段整改清单（v0.x）

P0：
- 路由输入从 `dict` 改为 Pydantic 模型
- 为核心路由补 `response_model`
- 增加 schema-change-log 并坚持更新

P1：
- 增加全局异常处理与统一 trace_id 中间件
- 增加结构化日志
- 增加 pytest API 用例

P2：
- 分层重构（service/repository）
- 接入鉴权与权限过滤
- 切换 Alembic（触发条件满足时）
