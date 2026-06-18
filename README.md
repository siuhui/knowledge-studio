# KnowledgeBase

本地知识检索与 AI 分析工具。把文档丢进去，能搜、能问、能深度分析。

**v0.1** — 注册/登录 → 创建 KnowledgeBase → 上传文件 → 索引 → 检索 → 带引用回答。

## 文档

- [PRD](docs/prd.md)
- [数据模型](docs/data-model.md)
- [工程规范](docs/engineering-standards.md)

## 技术栈

Python + FastAPI + SQLAlchemy · PostgreSQL 16 + pgvector · MinIO · Next.js 15 · OpenAI API

## 运行

### Docker Compose

```bash
cp apps/api/.env.example apps/api/.env
# 编辑 .env: 改 KB_LLM__API_KEY，localhost → db/minio
```

**标准模式**：
```bash
docker compose -f infra/docker-compose.yml up -d
# http://localhost:8000  |  Swagger: /docs  |  MinIO: :9001  |  Web: :3000
```

**开发模式**（叠加热重载 + 前端 HMR）：

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d
```

### 本地开发

#### 依赖服务

方式一 — Docker 快速启动：

```bash
docker compose -f infra/docker-compose.yml up -d db minio minio-init
```

方式二 — 自行安装运行，确保 PostgreSQL 已启用 pgvector 扩展。

#### 后端

```bash
cd apps/api
cp .env.example .env    # 编辑 .env 改密钥，host 保持 localhost
python -m venv .venv

# 激活虚拟环境（选一个）：
.venv\Scripts\Activate.ps1       # Windows PowerShell
source .venv/Scripts/activate    # Windows Git Bash
source .venv/bin/activate        # macOS / Linux

pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

#### 前端

```bash
cd apps/web
pnpm install && pnpm dev        # http://localhost:3000
```
