# v0.1 Sprint 02 Plan（上传台账与 Ingest/Index 最小闭环）

## 1. Sprint 目标
在现有上传能力上补齐“可管理、可追踪、可联动”的最小闭环：
- 上传完成后落 `uploaded_object`
- 可通过接口管理上传资产
- 与索引任务状态联动

## 2. 工作拆分（WBS）

### A. 数据模型与迁移
- A1: 新增表 `uploaded_object`
- A2: 新增唯一约束 `bucket+object_key`
- A3: 状态枚举 `uploaded/indexed/failed/deleted`
- A4: 增加 `index_error_message` 字段

### B. 上传完成落库
- B1: `complete` 调用 `head_object`
- B2: 校验 `ContentLength>0`、大小上限、`ContentType` 匹配
- B3: 按 `bucket+object_key` 幂等 upsert
- B4: 首次写入状态 `uploaded`

### C. 上传管理 API
- C1: `GET /api/v1/uploads?kb_id=...` 分页列表（按 `created_at` 倒序）
- C2: `GET /api/v1/uploads/{id}` 详情
- C3: `DELETE /api/v1/uploads/{id}` 软删除
- C4: 删除对象存储文件（同步或异步，默认同步实现）

### D. 与索引任务联动
- D1: index job 成功后：`uploaded -> indexed`
- D2: index job 失败后：`uploaded -> failed`
- D3: 失败原因写入 `index_error_message`

### E. 测试与验收
- E1: 单元测试（complete 校验与 upsert）
- E2: 集成测试（presign -> 上传 -> complete -> 列表可见）
- E3: 集成测试（index 成功/失败后状态联动）

## 3. 接口与数据变更
- 新增 API：
  - `GET /api/v1/uploads`
  - `GET /api/v1/uploads/{id}`
  - `DELETE /api/v1/uploads/{id}`
- 强化 API：
  - `POST /api/v1/uploads/complete`（真实校验 + 落库）
- 新增表：`uploaded_object`

## 4. 验收标准（DoD）
- 完成上传后，列表接口可见记录且状态为 `uploaded`
- 索引成功后状态改为 `indexed`
- 索引失败后状态改为 `failed` 且有失败原因
- 删除接口可将状态改为 `deleted`，并删除对象存储文件
- 关键链路测试通过

## 5. 风险与依赖
- 风险：对象存储弱一致或网络抖动导致 `head_object` 失败
- 风险：并发回调导致重复写入
- 依赖：MinIO/S3、PostgreSQL、KB 权限模型

## 6. 输出物
- `kb-rag-foundation/api-contract.md`（接口冻结）
- `kb-rag-foundation/data-schema-migration.md`（表结构冻结）
- `kb-rag-foundation/upload-workflow.md`（流程冻结）
- 后端实现与测试用例
