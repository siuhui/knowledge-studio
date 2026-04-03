# 上传流程（对象存储）

## 1. 目标
- 定义用户如何从浏览器上传文件到对象存储（MinIO/S3 兼容）。
- 定义上传完成后的资产台账落库与索引状态联动。

## 2. 用户操作主流程
1. 用户在前端选择文件并指定目标知识库 `kb_id`。
2. 前端调用 `POST /api/v1/uploads/presign` 获取 `upload_url + upload_fields + object_key`。
3. 前端以 `multipart/form-data POST` 直传到 MinIO/S3（不经业务服务转发文件流）。
4. 前端调用 `POST /api/v1/uploads/complete`。
5. 服务端做 `head_object` 校验并写入/幂等更新 `uploaded_object`（状态 `uploaded`）。
6. 用户或系统触发 `POST /api/v1/index/jobs` 执行 ingest/index。
7. 索引任务回写 `uploaded_object` 状态为 `indexed` 或 `failed`。

## 3. 关键设计
- 大文件上传走对象存储直传，避免业务服务成为传输瓶颈。
- 业务服务负责：权限校验、预签名、落库台账、状态联动。
- 对象键规则：`kb/{kb_id}/{kb_slug}/raw/{yyyymmdd}/{ulid}_{hash}{ext}`。
- 不在 `object_key` 暴露原始文件名；原名存对象元数据 `x-amz-meta-original-filename`。
- 上传大小由 presigned POST policy 限制（默认 20MB）。

## 4. 失败处理
- 预签名过期：前端重新请求 `presign`。
- 上传中断：前端重试同一 `object_key` 或重新申请。
- `complete` 失败：前端可重放（接口需幂等）。
- 索引失败：将 `uploaded_object.status` 置为 `failed` 并记录原因，支持重试索引。

## 5. source 与 uploaded_object 的关系
- `source`：描述“去哪里扫描、怎么增量同步”的连接配置。
- `uploaded_object`：描述“上传了什么文件、当前状态是什么、谁上传”的资产台账。
- 上传管理接口（列表/详情/删除）面向 `uploaded_object`，不面向 `source`。
