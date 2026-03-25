# Docker 开发环境说明

## 文件
- `docker-compose.dev.yml`：本地开发编排（服务 + 中间件）
- `data/*`：中间件持久化目录（宿主机可见）

## 持久化目录
- `./data/postgres` -> Postgres 数据
- `./data/redis` -> Redis AOF 数据
- `./data/rabbitmq` -> RabbitMQ 数据
- `./data/minio` -> MinIO 对象数据
- `./data/opensearch` -> OpenSearch 数据

## 启动
```powershell
cd infra/docker
docker compose -f docker-compose.dev.yml up -d --build
```

## 热更新
`rag-service` 已挂载 `../../apps/rag-service/app:/app/app` 并使用 `uvicorn --reload`，修改后端代码后容器会自动重载。

## 前端接入建议（后续）
当前项目未包含前端。后续新增 `apps/web` 后，可在本 compose 增加 `web` 服务：
- 端口示例：`3000:3000`
- 代码挂载：`../../apps/web:/web`
- API 地址通过环境变量指向 `rag-service:8000`
