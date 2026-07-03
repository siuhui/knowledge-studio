"""AgentRunner — stateless ReAct agent execution engine.

A single _run_impl() generator drives both sync (run) and streaming
(run_stream) consumers. The loop is business-agnostic: it only knows
about think → act → observe → repeat → stop.
"""

import json
import time
from collections.abc import AsyncIterator, Generator
from dataclasses import dataclass
from typing import Any

import structlog

from app.services.agent.types import (
    AgentConfig,
    AgentResult,
    AgentStep,
    AgentUsage,
    Artifact,
    ToolContext,
    ToolResult,
)
from app.services.llm import LLMProvider, ToolSpec

logger = structlog.get_logger(__name__)


# ── StepEvent ────────────────────────────────────────────────────────────────


@dataclass
class StepEvent:
    """Internal loop event. _run_impl() yields one per step.

    Consumers (run/run_stream) decide how to handle each event type.
    """

    type: str  # "thought" | "tool_call" | "tool_result" | "final" | "error"
    data: dict[str, Any]
    step: AgentStep


@dataclass
class _RunState:
    """Mutable accumulator for per-run metrics passed from _run_impl to run().

    _run_impl writes token counts into this object as it processes LLM
    responses.  The run() consumer creates the object, passes it in, and
    reads the accumulated values after the generator is exhausted.
    run_stream() does not pass state — _run_impl creates a throwaway one.
    """

    input_tokens: int = 0
    output_tokens: int = 0


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tools_to_specs(tools: list[Any]) -> list[ToolSpec]:
    """Convert agent Tool objects to ToolSpec for the LLM provider.

    The LLM provider only needs schema metadata (name, description, parameters);
    it never calls execute(). This conversion avoids coupling llm.py to the
    full Tool protocol.
    """
    return [ToolSpec(name=t.name, description=t.description, parameters=t.parameters) for t in tools]


# ── AgentRunner ──────────────────────────────────────────────────────────────


class AgentRunner:
    """Stateless ReAct agent execution engine.

    Does not bind to any specific tools or output format.
    Each call to run() / run_stream() creates new internal state;
    the instance itself is reusable.
    """

    def __init__(self, llm: LLMProvider, config: AgentConfig):
        self.llm = llm
        self.config = config

    # ── Core loop ──────────────────────────────────────────────────────────

    def _run_impl(
        self, task: str, ctx: ToolContext, state: _RunState | None = None
    ) -> Generator[StepEvent, None, None]:
        """Single generator driving both sync and streaming consumers.

        Flow:
          1. Build initial messages: [system_prompt, task]
          2. Loop (max config.max_rounds):
             a. llm.generate_with_tools(messages, tools, output_schema)
             b. Parse ToolCallDecision:
                - is_final → record, yield final, break
                - tool_call → execute tool, append observe to messages
                - error → yield error, break
             c. Check early stop (consecutive rounds with 0 new artifacts)
             d. Check max_rounds

        If state is passed (by run()), token counts are accumulated into it.
        Otherwise a throwaway _RunState is created internally.
        """
        if state is None:
            state = _RunState()
        start_time = time.perf_counter()

        # Build initial messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user", "content": task},
        ]

        total_tool_calls = 0
        consecutive_dry_rounds = 0

        for round_num in range(1, self.config.max_rounds + 1):
            logger.debug("agent round start", round=round_num)

            try:
                decision = self.llm.generate_with_tools(
                    system_prompt="",
                    messages=messages,
                    tools=_tools_to_specs(self.config.tools),
                    output_schema=self.config.output_schema,
                )
            except Exception as exc:
                logger.exception("LLM call failed", round=round_num)
                error_step = AgentStep(
                    thought=None,
                    tool_name=None,
                    tool_args=None,
                    tool_result=None,
                    is_final=False,
                    new_info_count=0,
                )
                yield StepEvent(
                    type="error",
                    data={
                        "type": "error",
                        "message": f"LLM error at round {round_num}: {exc}",
                        "round": round_num,
                    },
                    step=error_step,
                )
                break

            # Accumulate token usage reported by the provider
            state.input_tokens += decision.input_tokens
            state.output_tokens += decision.output_tokens

            # Emit thought event
            thought_step = AgentStep(
                thought=decision.thought,
                tool_name=None,
                tool_args=None,
                tool_result=None,
                is_final=decision.is_final,
                new_info_count=0,
            )
            yield StepEvent(
                type="thought",
                data={
                    "type": "thought",
                    "text": decision.thought or "",
                    "round": round_num,
                },
                step=thought_step,
            )

            # ── Final answer ──
            if decision.is_final:
                final_content = decision.content or ""
                # Build a synthetic ToolResult for the final answer so
                # AgentResult.final_answer can be populated consistently
                final_artifact = Artifact(
                    data={"answer": final_content},
                    source=None,
                )
                final_tool_result = ToolResult(
                    summary=final_content,
                    artifacts=[final_artifact],
                    artifact_count=1,
                )
                final_step = AgentStep(
                    thought=decision.thought,
                    tool_name=None,
                    tool_args=None,
                    tool_result=final_tool_result,
                    is_final=True,
                    new_info_count=1,
                )
                yield StepEvent(
                    type="final",
                    data={
                        "type": "final",
                        "answer": final_content,
                    },
                    step=final_step,
                )
                break

            # ── Tool call ──
            tool_name = decision.tool_name
            tool_args = decision.tool_args or {}

            if tool_name is None:
                logger.warning("no tool name in non-final decision", round=round_num)
                error_step = AgentStep(
                    thought=decision.thought,
                    tool_name=None,
                    tool_args=None,
                    tool_result=None,
                    is_final=False,
                    new_info_count=0,
                )
                yield StepEvent(
                    type="error",
                    data={
                        "type": "error",
                        "message": "LLM returned no tool call and no final answer",
                        "round": round_num,
                    },
                    step=error_step,
                )
                break

            # Emit tool_call event
            tc_step = AgentStep(
                thought=decision.thought,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=None,
                is_final=False,
                new_info_count=0,
            )
            yield StepEvent(
                type="tool_call",
                data={
                    "type": "tool_call",
                    "tool": tool_name,
                    "args": tool_args,
                    "round": round_num,
                },
                step=tc_step,
            )

            # Execute tool (with unknown-tool guard)
            if not self.config.has_tool(tool_name):
                logger.error("unknown tool requested by LLM", tool=tool_name, round=round_num)
                tool_result = ToolResult(
                    summary=f"Unknown tool: '{tool_name}'. Available tools: {[t.name for t in self.config.tools]}",
                    artifacts=[],
                    artifact_count=0,
                )
            else:
                tool = self.config.get_tool(tool_name)
                try:
                    tool_result = tool.execute(ctx, **tool_args)
                except Exception as exc:
                    logger.exception("tool execution failed", tool=tool_name, round=round_num)
                    tool_result = ToolResult(
                        summary=f"Tool '{tool_name}' failed: {exc}",
                        artifacts=[],
                        artifact_count=0,
                        metadata={"error": str(exc)},
                    )

            total_tool_calls += 1

            # Emit tool_result event
            tr_step = AgentStep(
                thought=decision.thought,
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
                is_final=False,
                new_info_count=tool_result.artifact_count,
            )
            yield StepEvent(
                type="tool_result",
                data={
                    "type": "tool_result",
                    "tool": tool_name,
                    "count": tool_result.artifact_count,
                    "round": round_num,
                },
                step=tr_step,
            )

            # Append assistant decision + tool result to message history.
            # The assistant message carries the tool call so both OpenAI
            # (tool_call_id bridging) and Anthropic (user/assistant alternation)
            # receive a well-formed conversation transcript.
            observe_text = (
                f"Tool '{tool_name}' result:\n{tool_result.summary}\n"
                f"(Found {tool_result.artifact_count} item(s). "
                f"Use read_document to get full context if needed.)"
            )
            tool_call_id = f"call_{round_num}"
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {"name": tool_name, "arguments": json.dumps(tool_args)},
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": observe_text,
                }
            )

            # ── Early stop check ──
            if tool_result.artifact_count == 0:
                consecutive_dry_rounds += 1
                if consecutive_dry_rounds >= self.config.early_stop_patience:
                    logger.info(
                        "early stop triggered",
                        consecutive_dry_rounds=consecutive_dry_rounds,
                        total_rounds=round_num,
                    )
                    break
            else:
                consecutive_dry_rounds = 0

        # ── Loop ended (max rounds or early stop) without final answer ──
        else:
            # Reached max_rounds without explicit final answer
            logger.info("max rounds reached", max_rounds=self.config.max_rounds)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "agent run complete",
            total_rounds=round_num,
            total_tool_calls=total_tool_calls,
            latency_ms=elapsed_ms,
        )

    # ── Sync consumer ──────────────────────────────────────────────────────

    def run(self, task: str, ctx: ToolContext) -> AgentResult:
        """Execute synchronously. Consumes all _run_impl events, builds AgentResult."""
        start_time = time.perf_counter()
        state = _RunState()
        steps: list[AgentStep] = []
        collected: list[Artifact] = []
        total_tool_calls = 0
        final_answer: str | None = None

        for event in self._run_impl(task, ctx, state):
            steps.append(event.step)
            if event.type == "tool_result" and event.step.tool_result:
                collected.extend(event.step.tool_result.artifacts)
                total_tool_calls += 1
            elif event.type == "final":
                final_answer = event.data.get("answer") or (
                    event.step.tool_result.summary if event.step.tool_result else None
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return AgentResult(
            steps=steps,
            collected_artifacts=collected,
            final_answer=final_answer,
            total_rounds=len(steps),
            total_tool_calls=total_tool_calls,
            usage=AgentUsage(
                input_tokens=state.input_tokens,
                output_tokens=state.output_tokens,
                total_tool_calls=total_tool_calls,
                latency_ms=elapsed_ms,
            ),
        )

    # ── Streaming consumer ─────────────────────────────────────────────────

    async def run_stream(self, task: str, ctx: ToolContext) -> AsyncIterator[str]:
        """Stream execution. Yields SSE-formatted JSON strings.

        Event types yielded:
          {"type": "thought",     "text": "...", "round": N}
          {"type": "tool_call",   "tool": "...", "args": {...}, "round": N}
          {"type": "tool_result", "tool": "...", "count": N, "round": N}
          {"type": "final",       "answer": "..."}
          {"type": "error",       "message": "..."}
        """
        for event in self._run_impl(task, ctx):
            yield json.dumps(event.data)
