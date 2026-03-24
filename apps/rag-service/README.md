# rag-service (v0.1)

最小可运行后端服务，覆盖 v0.1 第一阶段核心能力：
- 健康检查
- 数据源创建/查询
- 索引任务创建/查询

## 目录
- `app/main.py`：FastAPI 入口
- `app/models.py`：SQLAlchemy 数据模型（v0.1 最小集合）
- `app/api/sources.py`：数据源接口
- `app/api/index_jobs.py`：索引任务接口

## 启动
```powershell
cd E:\project\knowledge-base\apps\rag-service
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Python 版本要求：`3.11.x`（当前建议 `3.11.4`）。

默认数据库：`sqlite:///./knowledge_base.db`
如需 PostgreSQL：设置环境变量 `KB_DATABASE_URL`。

## 示例调用
```powershell
# 1) 创建 source
curl -X POST http://127.0.0.1:8000/api/v1/sources -H "Content-Type: application/json" -d '{"name":"wiki","source_type":"wiki"}'

# 2) 创建 index job
curl -X POST http://127.0.0.1:8000/api/v1/index/jobs -H "Content-Type: application/json" -d '{"source_id":"<上一步返回id>","mode":"incremental"}'

# 3) 查询 index job
curl http://127.0.0.1:8000/api/v1/index/jobs/<job_id>
```

