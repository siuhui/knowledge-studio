# 工程规范

## 1. 项目结构

```
knowledge-base/
├── README.md
├── .gitignore
├── docs/                              # 项目文档（事实源）
│   ├── prd.md                         #   产品需求
│   ├── data-model.md                  #   数据模型
│   └── engineering-standards.md       #   本文件
├── apps/
│   ├── api/                           # 后端 FastAPI
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                #   应用入口 + lifespan
│   │   │   ├── config.py              #   配置（pydantic-settings）
│   │   │   ├── database.py            #   引擎 + session + Base
│   │   │   ├── dependencies.py        #   FastAPI 依赖注入（get_db, get_current_user）
│   │   │   ├── core/                  #   横切层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── response_codes.py   #     响应码 StrEnum
│   │   │   │   ├── errors.py          #     异常层级
│   │   │   │   ├── exceptions.py      #     全局异常处理器注册
│   │   │   │   ├── security.py        #     JWT + bcrypt
│   │   │   │   └── trace.py           #     请求追踪 ID + RequestIdMiddleware
│   │   │   ├── models/                #   ORM 模型（一表一文件）
│   │   │   │   ├── __init__.py
│   │   │   │   ├── user.py
│   │   │   │   ├── knowledge_base.py
│   │   │   │   ├── source.py
│   │   │   │   ├── document.py
│   │   │   │   └── chunk.py
│   │   │   ├── schemas/               #   Pydantic 请求/响应模型
│   │   │   │   ├── __init__.py
│   │   │   │   ├── common.py          #     ApiResponse[T] 泛型包装
│   │   │   │   ├── auth.py
│   │   │   │   ├── knowledge_base.py
│   │   │   │   ├── source.py
│   │   │   │   └── retrieval/         #   检索相关 schema（子包，防膨胀）
│   │   │   │       ├── __init__.py
│   │   │   │       ├── request.py
│   │   │   │       ├── response.py
│   │   │   │       └── citation.py
│   │   │   ├── repositories/          #   数据访问层
│   │   │   │   ├── __init__.py
│   │   │   │   ├── user_repository.py
│   │   │   │   ├── knowledge_base_repository.py
│   │   │   │   ├── source_repository.py
│   │   │   │   ├── document_repository.py
│   │   │   │   └── chunk_repository.py
│   │   │   ├── services/              #   业务逻辑
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth_service.py
│   │   │   │   ├── knowledge_base_service.py
│   │   │   │   ├── source_service.py
│   │   │   │   ├── document_service.py
│   │   │   │   ├── indexing_service.py
│   │   │   │   └── retrieval/         #   检索服务（子包，防膨胀）
│   │   │   │       ├── __init__.py
│   │   │   │       ├── retriever.py
│   │   │   │       ├── reranker.py
│   │   │   │       ├── citation_builder.py
│   │   │   │       └── service.py
│   │   │   └── api/                   #   路由（薄层）
│   │   │       ├── __init__.py
│   │   │       ├── health.py
│   │   │       ├── auth.py
│   │   │       ├── knowledge_bases.py
│   │   │       ├── sources.py
│   │   │       ├── documents.py       #   上传 / 文档管理
│   │   │       └── retrieval.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   ├── conftest.py
│   │   │   ├── api/                   #   路由测试（镜像 app 结构）
│   │   │   │   ├── test_health.py
│   │   │   │   ├── test_auth.py
│   │   │   │   ├── test_knowledge_bases.py
│   │   │   │   └── test_retrieval.py
│   │   │   ├── services/              #   服务测试
│   │   │   │   └── test_knowledge_base_service.py
│   │   │   └── repositories/          #   仓库测试
│   │   │       └── test_knowledge_base_repository.py
│   │   ├── requirements.txt
│   │   ├── requirements-dev.txt
│   │   └── pyproject.toml             #   ruff + mypy + pytest 配置
│   └── web/                           # 前端 Next.js
│       ├── src/
│       │   ├── app/                   #   App Router（页面路由）
│       │   │   ├── layout.tsx
│       │   │   ├── page.tsx
│       │   │   ├── login/
│       │   │   ├── register/
│       │   │   └── knowledge-bases/
│       │   ├── components/            #   复用组件
│       │   │   ├── ui/                #     基础 UI（Button, Input 等）
│       │   │   └── layout/            #     布局组件（Navbar, Sidebar）
│       │   ├── hooks/                 #   自定义 hooks
│       │   ├── lib/                   #   工具函数 + API client
│       │   │   ├── api.ts             #     fetch 封装
│       │   │   ├── auth.ts            #     token 管理
│       │   │   └── types.ts           #     共享类型
│       │   └── styles/
│       ├── public/
│       ├── package.json
│       ├── tsconfig.json
│       ├── next.config.ts
│       └── biome.json
└── infra/                             # 基础设施（docker-compose 等，后续加）
```

---

## 2. 命名约定

### 2.1 文件

| 层 | 约定 | 示例 |
|----|------|------|
| 路由 | `名词复数.py` | `knowledge_bases.py`, `sources.py`, `documents.py` |
| 服务 | `名词_service.py` 或 `子包/service.py` | `knowledge_base_service.py`, `retrieval/service.py` |
| 仓库 | `名词_repository.py` | `knowledge_base_repository.py` |
| 模型 | `名词单数.py` | `knowledge_base.py`, `user.py` |
| schema | `名词单数.py` 或 `子包/` | `knowledge_base.py`, `retrieval/request.py` |
| 测试 | 镜像 app 结构 | `api/test_auth.py`, `services/test_knowledge_base_service.py` |
| 前端页面 | 目录 + `page.tsx` | `knowledge-bases/page.tsx` |
| 前端组件 | `PascalCase.tsx` | `Navbar.tsx`, `KnowledgeBaseCard.tsx` |
| 前端 hooks | `useXxx.ts` | `useAuth.ts`, `useKnowledgeBases.ts` |

### 2.2 路由

```
GET    /health/live                        健康存活
GET    /health/ready                       就绪检查

POST   /api/v1/auth/register              注册
POST   /api/v1/auth/login                 登录

GET    /api/v1/knowledge-bases                   列表
POST   /api/v1/knowledge-bases                   创建
GET    /api/v1/knowledge-bases/{id}              详情
PATCH  /api/v1/knowledge-bases/{id}              更新
DELETE /api/v1/knowledge-bases/{id}              删除

POST   /api/v1/knowledge-bases/{id}/sources      创建数据源
GET    /api/v1/knowledge-bases/{id}/sources      列表数据源

POST   /api/v1/documents/upload/presign   获取上传预签名
POST   /api/v1/documents/upload/complete  确认上传完成
GET    /api/v1/documents/{id}             文档详情

POST   /api/v1/retrieval/query            检索
POST   /api/v1/qa/ask                      RAG 问答
```

### 2.3 数据库

| 约定 | 示例 |
|------|------|
| 表名 | 蛇形小写单数 | `user`, `knowledge_base`, `document`, `chunk` |
| 主键 | `id`，UUID 字符串 | `mapped_column(String(36), primary_key=True, default=uuid4)` |
| 外键 | `{entity}_id` | `knowledge_base_id`, `source_id`, `doc_id` |
| 时间戳 | `created_at`, `updated_at` | 带 `onupdate` |

### 2.4 Schema 管理

| 阶段 | 方式 | 说明 |
|------|------|------|
| v0.x（开发） | `Base.metadata.create_all()` | 配置开关 `KB_AUTO_CREATE_TABLES=true`，每次启动自动重建 |
| v1.0（上线） | Alembic | Schema 稳定、有真实数据后引入迁移管理 |

启动时由 `config.py` 控制：

```python
# config.py
auto_create_tables: bool = True  # v0.x dev mode

# main.py lifespan
if settings.auto_create_tables:
    Base.metadata.create_all(bind=engine)
    # 确保 pgvector 扩展已启用
    with engine.connect() as conn:
        conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {settings.database.pg_vector_extension}"))
        conn.commit()
```

---

## 3. 开发流程

### 3.1 分支策略

- **master 直接开发**（个人项目）
- 提交粒度：一个逻辑变更一个 commit
- 如需回滚，直接 `git revert`

### 3.2 提交规范

```
<type>: <简短描述>

- 具体变更点 1
- 具体变更点 2
```

type：`feat` / `fix` / `refactor` / `docs` / `test` / `chore`

示例：
```
feat: add auth register and login endpoints

- POST /api/v1/auth/register with username + password
- POST /api/v1/auth/login returns JWT token
- get_current_user dependency for protected routes
```

### 3.3 开发节奏

简单功能：
1. 写测试 → 2. 写代码 → 3. 跑测试 → 4. lint

复杂功能：
1. 设计文档 → 用户确认 → 2.写测试 → 3. 写代码 → 4. 跑测试 → 5. lint

每个端点至少一个 happy-path 测试。

### 3.4 版本规范

遵循 Semantic Versioning（`MAJOR.MINOR.PATCH`）：

- **开发期** (`0.y.z`)：API 不稳定，任何东西都可能变
- **MINOR**：一组 feat 聚合为一个版本（按里程碑发布），一个 `MINOR` 可包含多个 feat
- **PATCH**：bug fix 后 bump
- **MAJOR**：API 稳定后发布 `1.0.0`

格式规则：
- `pyproject.toml` / `package.json` / 程序字段 → `0.1.0`（机器可读，无 `v` 前缀）
- 文档 / 注释 / 用户可见消息 → `v0.1.0`（人读，加 `v` 前缀）
- Git tag → `v0.1.0`

示例：`0.1.0`（首个 MVP）→ `0.2.0`（新增 GitHub/URL 数据源）→ `0.2.1`（修一个检索 bug）→ `1.0.0`（API 稳定）。

---

## 4. 命令速查

### 4.1 后端（`apps/api/`）

```bash
# 首次安装
cd apps/api
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
pip install -r requirements.txt -r requirements-dev.txt

# 开发运行
uvicorn app.main:app --reload --port 8000

# 测试
pytest                              # 全部
pytest tests/api/test_auth.py       # 单文件
pytest -m "not slow"                # 跳过慢测试
pytest --tb=short                   # 简短回溯

# 代码质量
ruff check .                        # lint
ruff check --fix .                  # 自动修复
ruff format .                       # 格式化
mypy app/                           # 类型检查
```

### 4.2 前端（`apps/web/`）

```bash
# 首次安装
cd apps/web
pnpm install

# 开发运行
pnpm dev                            # localhost:3000

# 测试
pnpm test                           # vitest
pnpm test -- --coverage             # 覆盖率

# 代码质量
pnpm lint                           # biome lint
pnpm lint --fix                     # 自动修复
pnpm format                         # biome format
pnpm typecheck                      # tsc --noEmit
```

### 4.3 全局

```bash
# API 文档（开发中）
open http://localhost:8000/docs     # Swagger UI
open http://localhost:8000/redoc    # ReDoc
```

---

## 5. 后端代码规范（Python）

### 5.1 通用

- 遵循 PEP 8，由 ruff 强制执行
- 行宽 120 字符
- 类型注解必须（mypy `strict = true`）
- 文档字符串用英文，注释可以用中文
- 禁止裸 `except:`，禁止 `except Exception: pass`

### 5.2 配置管理

#### 技术选型

**pydantic-settings + .env + 环境变量覆盖 + 模块级单例**。

#### 文件结构

- `app/config.py` — Settings 类定义 + 模块级单例 `settings`
- `.env.example` — 模板（提交），列出所有字段及注释
- `.env` — 本地配置（gitignore），从 `.env.example` 复制并填入真实值
- `.env.local` — 本地敏感覆盖（gitignore，可选），优先级高于 `.env`

#### 规则

- **导入路径**：`from app.config import settings`，模块级单例，全项目直接引用
- **环境变量前缀**：`KB_`，嵌套字段用 `__` 展开（如 `KB_DATABASE__URL` → `settings.database.url`）
- **配置分组**：按领域拆嵌套类（`DatabaseConfig` / `JWTConfig` / `LLMConfig` / `ObjectStorageConfig`），不在平铺类堆字段
- **无默认值**：必填字段声明时不带 `=`，缺失则启动时报错；基础设施类字段（如 `auto_create_tables`）是例外
- **敏感字段**：用 `pydantic.SecretStr`，取值需调用 `.get_secret_value()`
- **环境隔离**：通过 `KB_ENV` 字段区分（`dev` / `test` / `prod`），启动时 `@field_validator` 校验
- **加载优先级**：`.env.example`（模板）→ `.env`（本地）→ `.env.local`（敏感覆盖）→ 进程环境变量（Docker）
- **.env.example 提交**，`.env` 和 `.env.local` gitignore

### 5.3 分层约束

```
api/           → 参数提取、调用 service、包装 ApiResponse。禁止：写 SQL
services/      → 业务逻辑、调 repository、调外部 API。禁止：直接操作 HTTP 请求对象
repositories/  → 数据访问、封裝 SQLAlchemy 查询。禁止：业务判断
models/        → ORM 映射。禁止：任何逻辑
core/           → 基础设施。禁止：引用 models / services / repositories
```

调用方向：`api → service → repository → db`

**函数签名规范**：

```python
# repository
def get_knowledge_base_by_id(db: Session, *, knowledge_base_id: str) -> KnowledgeBase | None:
    return db.get(KnowledgeBase, knowledge_base_id)

# service
def create_knowledge_base(db: Session, *, user_id: str, name: str, description: str | None = None) -> KnowledgeBase:
    knowledge_base = KnowledgeBase(user_id=user_id, name=name, description=description)
    knowledge_base_repo.save(db, knowledge_base)
    return knowledge_base

# api
@router.post("", response_model=ApiResponse[KnowledgeBaseItem])
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)) -> ApiResponse[KnowledgeBaseItem]:
    knowledge_base = create_knowledge_base(db, user_id=..., name=payload.name, description=payload.description)
    return ApiResponse[KnowledgeBaseItem](message="created", data=KnowledgeBaseItem.model_validate(knowledge_base))
```

### 5.4 错误处理

```python
# service 层抛出业务异常
raise NotFoundError(code=ErrorCode.KNOWLEDGE_BASE_NOT_FOUND, message=f"knowledge_base {id} not found")

# API 层不写 try-except，由全局 handler 统一处理
```

### 5.5 响应格式

**Body** 只包含业务数据，统一结构：
```json
{
  "code": "OK",
  "message": "success",
  "data": { ... }
}
```

**trace_id / request_id 放 Header**，不作为响应体字段：

```http
HTTP/1.1 200 OK
X-Request-ID: 8db5c5fc-7f92-47f1-99e2-f8d71d35f6c7
Content-Type: application/json
```

理由：`request_id` 是协议级元数据（和 `Content-Type`、`ETag` 同类），不是业务数据。AWS、Stripe、GitHub 都是这个做法。后续接入 OpenTelemetry 时可直接加 `traceparent` 头而不改 Body。

**中间件实现**（类式 BaseHTTPMiddleware）：

```python
# core/trace.py
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

注册：
```python
app.add_middleware(RequestIdMiddleware)
```

接口内获取：
```python
request.state.request_id
```

**前端读取**：
```ts
const res = await fetch("/api/health");
const requestId = res.headers.get("X-Request-ID");
```

前端也可主动传：
```ts
fetch("/api/health", { headers: { "X-Request-ID": generateId() } });
```

中间件优先复用传入值，保证一次用户操作从前端 → API → Worker 使用同一个 ID。

通过 `ApiResponse[T]` 泛型包装，不含 trace_id 字段。

### 5.6 日志规范

**原则**：结构化、可搜索、可串联。使用 Python `structlog` 输出 JSON，方便后续接入日志平台（ELK / Loki / Datadog）。

#### 5.6.1 日志级别

| 级别 | 场景 | 示例 |
|------|------|------|
| `DEBUG` | 开发调试，生产不输出 | 函数入参、中间变量、SQL 语句 |
| `INFO` | 正常业务事件 | 注册成功、KnowledgeBase 创建、索引完成 |
| `WARNING` | 可恢复的异常 | Token 即将过期、文件解析失败已跳过、限流触发 |
| `ERROR` | 需要人工介入的错误 | 索引任务失败、LLM 调用超时、数据库连接丢失 |
| `CRITICAL` | 服务不可用 | 数据库完全不可达、密钥丢失 |

#### 5.6.2 日志格式

**所有日志必须结构化**，默认使用 `structlog` JSON 格式：

```json
{
  "timestamp": "2026-06-18T14:30:00.123Z",
  "level": "info",
  "event": "knowledge_base created",
  "request_id": "8db5c5fc-7f92-47f1-99e2-f8d71d35f6c7",
  "user_id": "8db5c5fc-xxxx",
  "knowledge_base_id": "9ec6d6fd-xxxx",
  "duration_ms": 45
}
```

| 字段 | 来源 | 说明 |
|------|------|------|
| `timestamp` | 自动 | ISO 8601 UTC |
| `level` | 自动 | `debug` / `info` / `warning` / `error` / `critical` |
| `event` | 必填 | 人类可读的事件描述，用英文 |
| `request_id` | 中间件注入 | 全链路追踪 ID |
| `user_id` | `get_current_user` 注入 | 当前用户（如有） |
| 业务字段 | 按需 | 如 `knowledge_base_id`、`source_id`、`duration_ms` |

#### 5.6.3 上下文绑定

通过 `structlog.contextvars` 在整个请求生命周期绑定上下文，不用每次手动传参：

```python
# core/logging.py
import structlog

def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # 自动合并 request_id / user_id
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if is_dev else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO if is_prod else logging.DEBUG),
    )

def get_logger(name: str):
    return structlog.get_logger(name)
```

**在中间件里绑定 `request_id`**：

```python
# core/trace.py — RequestIdMiddleware.dispatch()
request.state.request_id = request_id
structlog.contextvars.bind_contextvars(request_id=request_id)
# ... 请求结束后 structlog.contextvars.unbind_contextvars("request_id")
```

**在 security dependency 里绑定 `user_id`**：

```python
# dependencies.py
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    user = auth_service.get_user_from_token(db, token)
    structlog.contextvars.bind_contextvars(user_id=user.id)
    return user
```

这样每一行日志自动携带 `request_id` 和 `user_id`，不需要在每个 `logger.info()` 里手写。

#### 5.6.4 日志位置

| 位置 | 记什么 |
|------|--------|
| `main.py` lifespan | 服务启动/停止、表创建 |
| `api/` 层 | 请求进入/完成（由中间件统一记，不在路由里手写 `logger.info`） |
| `services/` 层 | 业务关键事件：创建/删除/状态变更、外部调用耗时 |
| `repositories/` 层 | **不记日志**（纯数据访问，异常由 service 层处理） |
| `core/exceptions.py` | 异常时记 `ERROR` 级别，附带 `exc_info` |

#### 5.6.5 示例

```python
# ✅ 好的日志
logger = get_logger(__name__)

logger.info("knowledge_base created", knowledge_base_id=knowledge_base.id)
logger.warning("index job retrying", job_id=job_id, attempt=3)
logger.error("llm call failed", duration_ms=2500, exc_info=True)

# ❌ 不好的日志
logger.info(f"knowledge_base {knowledge_base.id} created")          # f-string 不可搜索
logger.error("something went wrong")                    # 没有上下文
logger.warning("upload %s failed, retry %d", key, n)    # 旧式 % 格式化
```

#### 5.6.6 禁止

- **禁止记录密码明文、JWT token、完整身份证号**
- **禁止在循环内打 `INFO` 日志**（如 chunk 遍历，用 `DEBUG`）
- **禁止 `print()`** 替代日志
- **禁止 `exception: pass` 后不打日志**

#### 5.6.7 前端日志

前端不引入额外日志库。开发者用 `console.log`（开发阶段），生产关闭：

```ts
// lib/logger.ts
const isDev = process.env.NODE_ENV === "development";

export const logger = {
  debug: (...args: unknown[]) => { if (isDev) console.debug("[DEBUG]", ...args); },
  info:  (...args: unknown[]) => { if (isDev) console.info("[INFO]", ...args); },
  warn:  (...args: unknown[]) => console.warn("[WARN]", ...args),
  error: (...args: unknown[]) => console.error("[ERROR]", ...args),
};
```

`error` 在生产环境也不抑制，用于监控。

---

## 6. 前端代码规范

### 6.1 通用

- TypeScript strict mode
- 组件 `.tsx`，工具 `.ts`
- `const`，不用 `var`
- `async/await`，不用裸 Promise
- 函数返回值必须注解

### 6.2 组件

- 优先 Server Component，需交互的用 `"use client"`
- 一个文件一个组件
- Props 用 `interface`，定义在组件同文件顶部

```tsx
interface KnowledgeBaseCardProps {
  knowledge_base: KnowledgeBase;
  onDelete: (id: string) => void;
}

export function KnowledgeBaseCard({ knowledge_base, onDelete }: KnowledgeBaseCardProps) {
  return <div>...</div>;
}
```

### 6.3 API 调用

统一通过 `lib/api.ts` 封装：

```ts
// lib/api.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function api<T>(path: string, options?: RequestInit): Promise<{ data: T; requestId: string }> {
  const requestId = crypto.randomUUID();
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId,       // 前端生成，全链路追踪
      ...getAuthHeader(),
      ...options?.headers,
    },
    ...options,
  });
  const rid = res.headers.get("X-Request-ID") || requestId;
  if (!res.ok) {
    const err = await res.json();
    throw new ApiError(err.code, err.message, res.status, rid);
  }
  return { data: (await res.json()).data as T, requestId: rid };
}

### 6.4 状态管理

- Token 存 `localStorage`
- 用户状态用 React Context（`AuthProvider`）
- 数据获取后续引入 `SWR` 或 `TanStack Query`

---

## 7. 前后端协作

### 7.1 开发顺序

1. 后端先写 API + 测试，Swagger 可用
2. 前端配 CORS（middleware），指向后端
3. 前端按 API 文档写页面

### 7.2 环境变量

后端（`apps/api/`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `KB_ENV` | `dev` | 环境 |
| `KB_DATABASE__URL` | `postgresql://postgres:postgres@localhost:5432/knowledgebase` | 数据库连接 |
| `KB_DATABASE__PG_VECTOR_EXTENSION` | `vector` | pgvector 扩展名 |
| `KB_LLM__PROVIDER` | `openai` | LLM 服务商（`openai` / `anthropic`） |
| `KB_LLM__API_KEY` | — | API 密钥（必填） |
| `KB_LLM__BASE_URL` | — | API 代理地址（可选） |
| `KB_LLM__CHAT_MODEL` | `gpt-4o-mini` | 对话模型 |
| `KB_LLM__EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型 |
| `KB_LLM__EMBEDDING_DIMENSION` | `1536` | 向量维度（需与 pgvector 一致） |
| `KB_JWT__SECRET` | `dev-secret-change-me` | JWT 签名密钥 |
| `KB_JWT__EXPIRY_MINUTES` | `1440` | Token 有效期（默认 24h） |
| `KB_CORS_ORIGINS` | `["http://localhost:3000"]` | 跨域白名单 |

前端（`apps/web/`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | 后端 API 地址 |

### 7.3 本地联调

```bash
# 终端 1：后端
cd apps/api && uvicorn app.main:app --reload --port 8000

# 终端 2：前端
cd apps/web && pnpm dev
# → http://localhost:3000
```

---

## 8. 架构演进方向（远期参考）

当前采用 **分层架构**（models / repositories / services / api），规模合适。

当业务域膨胀到 ~10+ 个领域时，可考虑 **领域（Domain/Feature-first）架构**：

```
app/
├── domains/
│   ├── auth/
│   │   ├── api.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── schemas.py
│   │   └── model.py
│   ├── knowledge_base/
│   ├── retrieval/
│   └── ...
└── core/
```

**v0.x ~ v1.0.0 不需要这个**。留在文档里备忘即可。

---

## 9. 待定（后续补）

- CI/CD 配置（GitHub Actions）
- Docker 容器化
- 前端状态管理方案（SWR / TanStack Query）
- E2E 测试方案（Playwright）

---

## 10. RAG 管线技术选型

### 10.1 总原则

- **不用 RAG 框架**（LangChain / LlamaIndex）。管线逻辑自写，直接控制每一步。
- 每步是可替换的抽象，不绑死具体实现。
- v0.1.0 克制：只支持可复制文本的 PDF、Markdown、纯文本。

### 10.2 文档解析（Source → Document）

#### 抽象层

```python
from typing import Protocol

class Parser(Protocol):
    def parse(self, raw_bytes: bytes) -> str: ...
```

注册表：

```python
PARSERS: dict[str, Parser] = {
    "pdf":      PdfParser(),
    "markdown": MarkdownParser(),
    "text":     TextParser(),
}
```

#### 各格式选型

| 格式 | 选型 | 说明 |
|------|------|------|
| PDF | **PyMuPDF (fitz)** | `pip install PyMuPDF`；纯 C 实现，提取质量高，无系统依赖 |
| Markdown | **自写 parser** | 去 frontmatter、图片链接，保留标题层级（标题对后续 chunk 有价值）。不需要 `markdown-it-py` 转 HTML——从 Markdown 到纯文本的信息损失可以接受 |
| Plain Text | **自写** | UTF-8 → GB18030 回退解码；编码检测用 `charset-normalizer`（`pip install charset-normalizer`）

#### v0.1.0 明确不支持

- OCR / 扫描版 PDF（得到的可能是空字符串，需在文档中告知用户）
- DOCX / PPTX / EPUB / HTML
- 图片、音频、视频

### 10.3 分块（Chunking）

**段落感知 + 固定 token 窗口**，不用语义分块。

```
chunk_size = 512 tokens
overlap    = 50 tokens
splitter   = 按段落边界切；段落超长再按句子切
```

v0.1.0 的文件以技术文档为主，段落本身就是自然的语义边界，无需 LangChain 的 `RecursiveCharacterTextSplitter`——自写 20 行。

### 10.4 向量化（Embedding）

**走 API**，和 LLM 共用一个外部出口。

```python
class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

- 默认：OpenAI `text-embedding-3-small`（1536 维）或 Anthropic 对应模型
- 通过抽象层可配置切换，换模型只改配置 + DDL 向量维度
- 不在 v0.1.0 引入本地模型（sentence-transformers 需要 GPU 才实用，CPU 批处理 100 页偏慢且占内存）

### 10.5 检索（Retrieval）

**pgvector 裸用 + PostgreSQL tsvector，RRF 融合**。不加 Elasticsearch / Meilisearch / Pinecone。

```
向量检索：ORDER BY embedding <=> query_embedding LIMIT 20
关键词：  WHERE to_tsvector('english', content) @@ plainto_tsquery('english', query)
融合：    Reciprocal Rank Fusion，Python 里 ~10 行
```

```python
def hybrid_search(db, query: str, query_emb: list[float], top_k: int = 10):
    # 向量检索
    vec = await db.execute(
        select(Chunk, Chunk.embedding.cosine_distance(query_emb).label("dist"))
        .order_by("dist").limit(top_k * 2)
    )
    # 关键词检索
    kw = await db.execute(
        select(Chunk, func.ts_rank(to_tsvector(Chunk.content),
             plainto_tsquery(query)).label("rank"))
        .where(to_tsvector(Chunk.content).match(query))
        .order_by("rank").limit(top_k * 2)
    )
    return rrf_fusion(vec.all(), kw.all(), top_k=top_k)
```

### 10.6 依赖清单（v0.1.0 新增）

```
PyMuPDF                  # PDF 解析
charset-normalizer       # 文本编码检测
openai / anthropic       # LLM + Embedding API
# 无 RAG 框架
# 无外部检索中间件
```
