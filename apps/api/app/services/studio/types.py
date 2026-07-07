from dataclasses import dataclass

from app.services.agent.types import Artifact


@dataclass
class ChapterPlan:
    title: str
    plan: str


@dataclass
class ChapterMaterial:
    chapter: ChapterPlan
    materials: list[Artifact]


@dataclass
class ChapterContent:
    title: str
    content: str
