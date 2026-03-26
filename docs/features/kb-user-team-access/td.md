# 功能 TD：用户与团队与知识库访问控制

## 元信息
- feature_id: `kb-user-team-access`
- owner: `TBD`
- status: `active`
- version_introduced: `v0.1`
- version_updated: `v0.1`

---
## 目标上线版本 v1.0

## 1. 设计目标

实现可演进的权限基础层：
- 用户与团队关系灵活（多对多）
- 知识库归属明确（单 team）
- 默认权限来自团队关系
- 资源权限例外由知识库成员表覆盖

---

## 2. 领域模型

- `user`
- `team`
- `team_membership`（user-team 多对多）
- `knowledge_base`（owner_team_id 单归属）
- `knowledge_base_membership`（例外授权，不存团队全量）

约束：
- `knowledge_base.owner_team_id` 必填
- `knowledge_base_membership.role` 仅允许 `owner/editor/viewer`
- 同一 `(knowledge_base_id, user_id)` 唯一

---

## 3. 权限判定规则（MVP）

默认权限：
- 用户属于 `knowledge_base.owner_team_id` 对应团队 -> 默认 `viewer`

例外权限：
- 若 `knowledge_base_membership` 存在记录，则覆盖默认权限
- 适用场景：提升、降级、跨团队、临时授权

权限矩阵：
- `kb:read` -> owner/editor/viewer
- `kb:write` -> owner/editor
- `kb:delete` -> owner

判定顺序：
1. 查 `knowledge_base_membership`（有则直接用）
2. 无例外记录时，按 team 默认权限（同团队默认 viewer）
3. 否则拒绝

---

## 4. 服务分层建议

- API 层：参数校验、响应封装
- Service 层：业务编排、权限判定
- Repository 层：数据访问

建议新增：
- `services/access_control.py`
- `repositories/team_repo.py`
- `repositories/kb_repo.py`

---

## 5. 一致性与事务

- 创建知识库 + 写入 owner 例外授权（owner）同事务提交
- 用户移出团队时，不自动删除知识库例外授权（避免误删），走显式流程

---

## 6. 演进策略

v0.x：
- 本地单体快速迭代
- schema 变更记录到 `schema-change-log`

v1.0 前：
- 切换 Alembic
- 权限服务独立测试覆盖

---

## 7. 与现有系统集成

- 与 RAG 检索链路集成点：
  - 查询前按 `knowledge_base_id + user_id` 判定 `kb:read`
- 与审计集成点：
  - 授权变更写入 `audit_log`
