# 数据模型与迁移方案：User-Team-KnowledgeBase（v0.1）

## 1. 新增表

### users
- id (pk, uuid)
- email (unique)
- display_name
- status (active/inactive)
- created_at/updated_at

### teams
- id (pk, uuid)
- name (unique)
- status
- created_at/updated_at

### team_memberships
- id (pk, uuid)
- user_id (fk -> users.id)
- team_id (fk -> teams.id)
- role (team_admin/member)
- created_at/updated_at
- unique(user_id, team_id)

### knowledge_bases
- id (pk, uuid)
- name
- owner_team_id (fk -> teams.id)
- status
- created_at/updated_at

### knowledge_base_memberships
- id (pk, uuid)
- knowledge_base_id (fk -> knowledge_bases.id)
- user_id (fk -> users.id)
- role (owner/editor/viewer)
- created_at/updated_at
- unique(knowledge_base_id, user_id)

说明：
- `knowledge_base_memberships` 仅存“例外授权”，不存团队全量成员。

## 2. 权限来源

- 默认权限来源：`team_memberships`
  - 同团队成员默认对团队归属知识库拥有 `viewer`
- 覆盖权限来源：`knowledge_base_memberships`
  - 用于提升/降级/跨团队/临时授权

优先级：
- `knowledge_base_memberships` > 团队默认权限

## 3. 迁移策略

v0.x：
- 更新 `infra/db/migrations/0001_init.sql` 或新增增量 SQL（二选一，保持一致）
- 同步写入 `apps/rag-service/schema-change-log.md`

v1.0 前：
- 切换 Alembic 并固化迁移链

## 4. 数据完整性规则
- 创建 knowledge_base 时必须同时写入 owner 例外授权记录
- 删除 team 前必须检查是否存在归属 knowledge_base
