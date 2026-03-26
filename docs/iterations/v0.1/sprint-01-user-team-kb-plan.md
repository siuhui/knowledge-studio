# v0.1 Sprint 01 Plan（用户/团队/知识库访问）

## 1. 目标
完成 User-Team-KnowledgeBase 权限基础能力的可开发闭环。

## 2. 工作拆分（WBS）

### A. 数据模型与初始化
- A1: 新增 users/teams/team_memberships
- A2: 新增 knowledge_bases/knowledge_base_memberships（例外授权）
- A3: 初始化脚本与 schema-change-log 同步

### B. API 交付
- B1: users 创建/查询
- B2: teams 创建/成员管理（创建者自动为 team_admin）
- B3: knowledge_bases 创建/例外授权管理

### C. 权限判定
- C1: 默认权限：同团队成员 -> viewer
- C2: 覆盖权限：知识库例外授权优先
- C3: 越权统一返回 `PERMISSION_DENIED`

### D. 审计
- D1: 授权变更写入 audit_log
- D2: 关键权限操作补 trace_id

### E. 测试
- E1: 角色矩阵单元测试
- E2: 授权接口 API 测试

## 3. 验收标准
- User-Team 多对多关系可查询可维护
- KnowledgeBase 创建必须绑定 owner_team_id
- 同团队成员默认具备 viewer 访问
- knowledge_base_memberships 仅保存例外授权
- 越权场景测试全部通过
