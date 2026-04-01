from typing import Literal

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=255)
    status: Literal["active", "inactive"] = "active"


class UserItem(BaseModel):
    id: str
    email: str
    display_name: str
    status: Literal["active", "inactive"]


class TeamCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    creator_user_id: str = Field(min_length=1)
    status: Literal["active", "archived"] = "active"


class TeamMemberUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: Literal["team_admin", "member"] = "member"


class TeamItem(BaseModel):
    id: str
    name: str
    status: Literal["active", "archived"]


class TeamMemberItem(BaseModel):
    user_id: str
    team_id: str
    role: Literal["team_admin", "member"]


class TeamMemberListPayload(BaseModel):
    items: list[TeamMemberItem]


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    owner_team_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    status: Literal["active", "archived"] = "active"


class KnowledgeBaseItem(BaseModel):
    id: str
    name: str
    owner_team_id: str
    status: Literal["active", "archived"]


class KnowledgeBaseMemberUpsertRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: Literal["owner", "editor", "viewer"]


class KnowledgeBaseMemberItem(BaseModel):
    user_id: str
    knowledge_base_id: str
    role: Literal["owner", "editor", "viewer"]


class KnowledgeBaseMemberListPayload(BaseModel):
    items: list[KnowledgeBaseMemberItem]


class PermissionCheckPayload(BaseModel):
    user_id: str
    knowledge_base_id: str
    action: Literal["read", "write", "delete"]
    role: Literal["owner", "editor", "viewer", "none"]
    allowed: bool
    source: Literal["kb_exception", "team_default", "none"]
