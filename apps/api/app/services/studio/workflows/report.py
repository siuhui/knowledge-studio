import contextvars
import json
import re
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from sqlalchemy.orm import Session

from app.core.telemetry import observe, update_current_span
from app.services.agent.configs import GATHER_AGENT_CONFIG
from app.services.agent.runner import AgentRunner
from app.services.agent.types import Artifact, ToolContext
from app.services.llm import llm_provider
from app.services.studio.generators.markdown import assemble_markdown
from app.services.studio.types import ChapterContent, ChapterMaterial, ChapterPlan

PLAN_SYSTEM_PROMPT = """\
You are a report planner. Given a title and instructions, plan a well-structured report outline.

The instructions define what the report should be — they may ask for a document analysis,
a personal study summary, a learning review, a research report, or anything else.
Follow the instructions to decide the report's perspective and structure.

Output valid JSON only — no markdown fences, no extra text:
{"chapters": [{"title": "Chapter Title", "plan": "What this chapter should cover and deliver"}]}

Rules:
- Plan 3-5 chapters
- Each chapter title should be concise and relevant to the report title
- Each plan should describe what the chapter should deliver and what kind of content to look for
- Chapters should form a coherent narrative arc that matches the instructions"""


def _parse_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM output, handling markdown code fences."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    data: dict[str, Any] = json.loads(text)
    return data


@observe(name="studio.report.plan", capture_input=False, capture_output=False)
def _plan_chapters(title: str, instruction: str, style: str, length: str) -> list[ChapterPlan]:
    update_current_span(
        input={"title": title[:200], "instruction": instruction[:200], "style": style, "length": length}
    )
    response = llm_provider.generate(
        system_prompt=PLAN_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Plan a report outline.\n"
                    f"Report title: {title}\n"
                    f"Topic / instructions: {instruction}\n"
                    f"Style: {style}\n"
                    f"Length: {length}\n"
                    f"\nOutput the chapter plan as JSON."
                ),
            }
        ],
    )
    data = _parse_json(response)
    chapters = [ChapterPlan(title=c["title"], plan=c["plan"]) for c in data["chapters"]]
    update_current_span(output={"chapter_count": len(chapters), "titles": [c.title for c in chapters]})
    return chapters


@observe(name="studio.report.gather", capture_input=False, capture_output=False)
def _gather_chapter(
    db: Session, chapter: ChapterPlan, kb_id: str, document_ids: list[str] | None = None
) -> ChapterMaterial:
    update_current_span(
        input={
            "chapter": chapter.title,
            "plan": chapter.plan[:200],
            "doc_filter_count": len(document_ids) if document_ids else 0,
        }
    )
    agent = AgentRunner(llm_provider, GATHER_AGENT_CONFIG)
    ctx = ToolContext(db=db, kb_id=kb_id)
    doc_hint = ""
    if document_ids:
        doc_hint = f"\nOnly search within these documents: {', '.join(document_ids)}"
    result = agent.run(
        task=f"Gather materials for chapter '{chapter.title}': {chapter.plan}{doc_hint}",
        ctx=ctx,
    )
    update_current_span(
        output={
            "chapter": chapter.title,
            "artifact_count": len(result.collected_artifacts),
            "tool_calls": result.total_tool_calls,
            "rounds": result.total_rounds,
        }
    )
    return ChapterMaterial(chapter=chapter, materials=result.collected_artifacts)


def _build_materials_context(materials: list[Artifact]) -> str:
    parts: list[str] = []
    for a in materials:
        title = a.data.get("title", "Untitled")
        snippet = a.data.get("snippet", "")
        parts.append(f"### Source: {title}\n{snippet}")
    return "\n\n".join(parts) if parts else "(No materials found)"


@observe(name="studio.report.generate", capture_input=False, capture_output=False)
def _generate_chapter(
    material: ChapterMaterial,
    report_title: str,
    instruction: str,
    style: str,
    length: str,
) -> ChapterContent:
    update_current_span(
        input={
            "chapter": material.chapter.title,
            "report_title": report_title[:200],
            "style": style,
            "length": length,
            "material_count": len(material.materials),
        }
    )
    context = _build_materials_context(material.materials)
    content = llm_provider.generate(
        system_prompt=(
            "You are a report writer. Follow the user's instruction for what this chapter should be — "
            "the instruction (and the chapter plan derived from it) defines the perspective, tone, and "
            "what the chapter should deliver. The provided materials are reference content to work with, "
            "not objects to analyze unless the instruction calls for analysis.\n\n"
            "Write in clear, well-structured markdown with appropriate headings, paragraphs, "
            "and bullet lists where helpful."
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"Write the chapter '{material.chapter.title}' for a report titled '{report_title}'.\n"
                    f"Report purpose: {instruction[:500]}\n"
                    f"Style: {style}\n"
                    f"Length guidance: {length}\n"
                    f"Chapter plan: {material.chapter.plan}\n"
                    f"\n## Reference Materials\n\n{context}\n"
                    f"\nWrite the full chapter now. Start with a ## heading for the chapter title."
                ),
            }
        ],
    )
    update_current_span(output={"chapter": material.chapter.title, "char_count": len(content)})
    return ChapterContent(title=material.chapter.title, content=content)


class ReportWorkflow:
    """5-stage report generation pipeline.

    Plan → Gather → Generate → Assemble → Store
    Only the Gather stage uses AgentRunner; other stages are plain LLM calls or pure code.
    """

    def __init__(self, update_progress: Callable[[float, str], None]):
        self.update_progress = update_progress

    @observe(name="studio.report", capture_input=False, capture_output=False)
    def execute(self, db: Session, *, config: dict[str, Any], kb_id: str) -> tuple[str, int]:
        """Run the full pipeline. Returns (markdown, chapter_count)."""
        instruction: str = config["instruction"]
        title: str = config.get("title", instruction)
        style: str = config.get("style", "professional")
        length: str = config.get("length", "medium")
        document_ids: list[str] | None = config.get("document_ids") or None

        update_current_span(
            input={
                "kb_id": kb_id,
                "title": title[:200],
                "style": style,
                "length": length,
                "doc_count": len(document_ids) if document_ids else 0,
            }
        )

        # Stage 1: Plan
        self.update_progress(0.05, "Planning chapter structure...")
        chapters = _plan_chapters(title, instruction, style, length)
        self.update_progress(0.10, f"Planned {len(chapters)} chapters")

        # Stage 2: Gather
        materials: list[ChapterMaterial] = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            gather_futures = {
                ex.submit(contextvars.copy_context().run, _gather_chapter, db, ch, kb_id, document_ids): i
                for i, ch in enumerate(chapters)
            }
            gather_results: list[ChapterMaterial | None] = [None] * len(chapters)
            for g_future in as_completed(gather_futures):
                g_idx = gather_futures[g_future]
                gather_results[g_idx] = g_future.result()
                done = sum(1 for r in gather_results if r is not None)
                self.update_progress(
                    0.10 + 0.30 * done / len(chapters),
                    f"Gathering materials for chapter {done}/{len(chapters)}...",
                )
            materials = [r for r in gather_results if r is not None]

        # Stage 3: Generate
        chapter_contents: list[ChapterContent] = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            gen_futures: dict[Future[ChapterContent], int] = {
                ex.submit(contextvars.copy_context().run, _generate_chapter, mat, title, instruction, style, length): i
                for i, mat in enumerate(materials)
            }
            gen_results: list[ChapterContent | None] = [None] * len(materials)
            for gen_future in as_completed(gen_futures):
                gen_idx = gen_futures[gen_future]
                gen_results[gen_idx] = gen_future.result()
                done = sum(1 for r in gen_results if r is not None)
                self.update_progress(
                    0.40 + 0.40 * done / len(materials),
                    f"Generating chapter {done}/{len(materials)}...",
                )
            chapter_contents = [r for r in gen_results if r is not None]

        # Stage 4: Assemble
        self.update_progress(0.85, "Assembling final report...")
        markdown = assemble_markdown(title, chapter_contents, style, length)

        return markdown, len(chapter_contents)
