# API 契约：User-Team-KnowledgeBase（v0.1 草案）

## 1. 用户

### POST /api/v1/users
请求：
```json
{
  "email": "user@example.com",
  "display_name": "Alice",
  "status": "active"
}
```

### GET /api/v1/users/{user_id}
返回用户详情。

## 2. 团队

### POST /api/v1/teams
规则：创建者自动成为该团队 `team_admin`。

请求：
```json
{
  "name": "Team A",
  "creator_user_id": "uuid",
  "status": "active"
}
```

### POST /api/v1/teams/{team_id}/members
请求：
```json
{
  "operator_user_id": "uuid",
  "user_id": "uuid",
  "role": "team_admin"
}
```

权限：
- 仅 `team_admin` 可变更团队成员，越权返回 `PERMISSION_DENIED`。

### GET /api/v1/teams/{team_id}/members
返回团队成员列表。

## 3. 知识库

### POST /api/v1/knowledge-bases
请求：
```json
{
  "name": "KB-A",
  "owner_team_id": "uuid",
  "owner_user_id": "uuid",
  "status": "active"
}
```

创建规则：
- 创建知识库时写入 owner 例外授权（owner）

### POST /api/v1/knowledge-bases/{kb_id}/members
用途：仅处理例外授权（不写团队全量成员）

请求：
```json
{
  "operator_user_id": "uuid",
  "user_id": "uuid",
  "role": "viewer"
}
```

权限：
- 仅 `owner` 可变更知识库例外授权成员，越权返回 `PERMISSION_DENIED`。

### GET /api/v1/knowledge-bases/{kb_id}/members
返回知识库例外授权列表。

## 4. 权限判定接口语义

- 默认：同团队成员对团队归属知识库具备 `viewer`
- 覆盖：存在知识库例外授权时，以例外授权为准

---

统一响应：`code/message/data/trace_id`

统一错误码（建议）：
- `USER_NOT_FOUND`
- `TEAM_NOT_FOUND`
- `KNOWLEDGE_BASE_NOT_FOUND`
- `ROLE_INVALID`
- `PERMISSION_DENIED`

审计事件：
- `TEAM_CREATE`
- `TEAM_MEMBER_UPSERT`
- `KNOWLEDGE_BASE_CREATE`
- `KNOWLEDGE_BASE_MEMBER_UPSERT`
