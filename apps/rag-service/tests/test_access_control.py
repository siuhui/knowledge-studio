import uuid

import pytest

from app.database import Base, SessionLocal, engine
from app.models import (
    KnowledgeBase,
    KnowledgeBaseMembership,
    KnowledgeBaseRole,
    KnowledgeBaseStatus,
    Team,
    TeamMembership,
    TeamRole,
    TeamStatus,
    User,
    UserStatus,
)
from app.services.access_control import can_access, resolve_kb_role


Base.metadata.create_all(bind=engine)


@pytest.mark.parametrize(
    ("role", "action", "expected"),
    [
        ("none", "read", False),
        ("none", "write", False),
        ("none", "delete", False),
        ("viewer", "read", True),
        ("viewer", "write", False),
        ("viewer", "delete", False),
        ("editor", "read", True),
        ("editor", "write", True),
        ("editor", "delete", False),
        ("owner", "read", True),
        ("owner", "write", True),
        ("owner", "delete", True),
    ],
)
def test_can_access_role_matrix(role: str, action: str, expected: bool):
    assert can_access(action, role) is expected


def test_resolve_kb_role_explicit_override_takes_precedence_over_team_default():
    with SessionLocal() as db:
        owner_user = User(
            id=str(uuid.uuid4()),
            email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Owner",
            status=UserStatus.active,
        )
        member_user = User(
            id=str(uuid.uuid4()),
            email=f"member-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Member",
            status=UserStatus.active,
        )
        team = Team(id=str(uuid.uuid4()), name=f"team-{uuid.uuid4().hex[:8]}", status=TeamStatus.active)
        db.add_all([owner_user, member_user, team])
        db.flush()

        db.add_all(
            [
                TeamMembership(
                    id=str(uuid.uuid4()),
                    user_id=owner_user.id,
                    team_id=team.id,
                    role=TeamRole.team_admin,
                ),
                TeamMembership(
                    id=str(uuid.uuid4()),
                    user_id=member_user.id,
                    team_id=team.id,
                    role=TeamRole.member,
                ),
            ]
        )

        kb = KnowledgeBase(
            id=str(uuid.uuid4()),
            name=f"kb-{uuid.uuid4().hex[:8]}",
            owner_team_id=team.id,
            status=KnowledgeBaseStatus.active,
        )
        db.add(kb)
        db.flush()

        db.add(
            KnowledgeBaseMembership(
                id=str(uuid.uuid4()),
                knowledge_base_id=kb.id,
                user_id=member_user.id,
                role=KnowledgeBaseRole.editor,
            )
        )
        db.commit()

        role, source = resolve_kb_role(db, user_id=member_user.id, knowledge_base_id=kb.id)
        assert role == "editor"
        assert source == "kb_exception"
