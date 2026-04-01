from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import KnowledgeBase, KnowledgeBaseMembership, TeamMembership

ROLE_PRIORITY = {"none": 0, "viewer": 1, "editor": 2, "owner": 3}


def resolve_kb_role(db: Session, user_id: str, knowledge_base_id: str) -> tuple[str, str]:
    explicit = db.scalar(
        select(KnowledgeBaseMembership).where(
            KnowledgeBaseMembership.knowledge_base_id == knowledge_base_id,
            KnowledgeBaseMembership.user_id == user_id,
        )
    )
    if explicit is not None:
        return explicit.role.value, "kb_exception"

    kb = db.get(KnowledgeBase, knowledge_base_id)
    if kb is None:
        return "none", "none"

    team_member = db.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == kb.owner_team_id,
            TeamMembership.user_id == user_id,
        )
    )
    if team_member is not None:
        return "viewer", "team_default"

    return "none", "none"


def can_access(action: str, role: str) -> bool:
    if action == "read":
        return ROLE_PRIORITY.get(role, 0) >= ROLE_PRIORITY["viewer"]
    if action == "write":
        return ROLE_PRIORITY.get(role, 0) >= ROLE_PRIORITY["editor"]
    if action == "delete":
        return ROLE_PRIORITY.get(role, 0) >= ROLE_PRIORITY["owner"]
    return False
