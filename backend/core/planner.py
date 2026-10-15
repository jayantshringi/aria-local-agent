"""OPEC Agent Loop: Planner Component for goal decomposition and multi-step plan generation."""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from core.observer import Observation
from tools.registry import tool_registry

logger = logging.getLogger("aria.core.planner")


@dataclass
class PlanStep:
    """A single discrete step in an execution plan."""

    step_id: int
    action: str  # Tool name or cognitive operation
    args: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    dependencies: list[int] = field(default_factory=list)
    status: str = "pending"  # pending, executing, completed, failed, skipped
    result: Any = None
    critique: str | None = None


@dataclass
class ExecutionPlan:
    """A complete multi-step execution plan generated for a user goal."""

    plan_id: str
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    strategy: str = ""
    is_complete: bool = False

    def get_pending_steps(self) -> list[PlanStep]:
        """Return steps that are ready for execution (dependencies satisfied)."""
        completed_ids = {s.step_id for s in self.steps if s.status == "completed"}
        ready = []
        for s in self.steps:
            if s.status == "pending":
                if all(dep in completed_ids for dep in s.dependencies):
                    ready.append(s)
        return ready

    def mark_step_completed(self, step_id: int, result: Any) -> None:
        for s in self.steps:
            if s.step_id == step_id:
                s.status = "completed"
                s.result = result
                break
        self.is_complete = all(s.status == "completed" for s in self.steps)

    def mark_step_failed(self, step_id: int, error: str) -> None:
        for s in self.steps:
            if s.step_id == step_id:
                s.status = "failed"
                s.result = error
                break


class Planner:
    """Decomposes user objectives into ordered, executable plan steps."""

    def __init__(self) -> None:
        pass

    async def create_plan(
        self,
        observation: Observation,
        model: str | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan based on observation analysis."""
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        goal = observation.user_input

        # 1. First evaluate deterministic heuristic plan
        heuristic_plan = self._create_heuristic_plan(plan_id, goal, observation)
        if heuristic_plan and heuristic_plan.steps:
            return heuristic_plan

        # 2. Try LLM-driven plan generation if local Ollama model is available
        llm_plan = await self._generate_llm_plan(plan_id, goal, observation, model)
        if llm_plan and llm_plan.steps:
            return llm_plan

        # 3. Fallback: single conversational step
        return ExecutionPlan(
            plan_id=plan_id,
            goal=goal,
            strategy="Direct conversational synthesis",
            steps=[
                PlanStep(
                    step_id=1,
                    action="synthesize_response",
                    args={"query": goal},
                    description="Answer query directly based on context and dialogue memory",
                )
            ],
        )

    def _create_heuristic_plan(
        self,
        plan_id: str,
        goal: str,
        obs: Observation,
    ) -> ExecutionPlan | None:
        """Generate fast, deterministic plans for common direct commands."""
        lower = goal.lower()
        entities = obs.extracted_entities
        paths = entities.get("paths", [])
        urls = entities.get("urls", [])

        # Git status / log / diff
        if "git status" in lower:
            return ExecutionPlan(
                plan_id=plan_id,
                goal=goal,
                strategy="Inspect local git status",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="git.action",
                        args={"action": "status"},
                        description="Check working tree and branch status",
                    )
                ],
            )
        if "git diff" in lower:
            return ExecutionPlan(
                plan_id=plan_id,
                goal=goal,
                strategy="Inspect git diff",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="git.action",
                        args={"action": "diff"},
                        description="View uncommitted repository changes",
                    )
                ],
            )

        # Web navigation / URL visit
        if urls:
            url = urls[0]
            return ExecutionPlan(
                plan_id=plan_id,
                goal=goal,
                strategy=f"Visit and extract web page content from {url}",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="browser.navigate",
                        args={"url": url, "action": "navigate"},
                        description=f"Navigate to {url} and extract readable page text",
                    )
                ],
            )

        # File reading
        if any(w in lower for w in ["read", "show", "cat", "view"]) and paths:
            target_path = paths[0]
            return ExecutionPlan(
                plan_id=plan_id,
                goal=goal,
                strategy=f"Read contents of file '{target_path}'",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="files.read",
                        args={"path": target_path},
                        description=f"Read file '{target_path}' from whitelisted folders",
                    )
                ],
            )

        # File search
        if any(w in lower for w in ["search for file", "find file", "look for file"]):
            pattern = paths[0] if paths else "*"
            return ExecutionPlan(
                plan_id=plan_id,
                goal=goal,
                strategy=f"Search for files matching '{pattern}'",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="files.search",
                        args={"pattern": pattern},
                        description=f"Search for files matching pattern '{pattern}'",
                    )
                ],
            )

        # OS system info
        if any(w in lower for w in ["system info", "cpu usage", "ram usage", "host status"]):
            return ExecutionPlan(
                plan_id=plan_id,
                goal=goal,
                strategy="Query host operating system telemetry",
                steps=[
                    PlanStep(
                        step_id=1,
                        action="os.action",
                        args={"action": "system_info"},
                        description="Retrieve CPU, RAM, and disk utilization metrics",
                    )
                ],
            )

        return None

    async def _generate_llm_plan(
        self,
        plan_id: str,
        goal: str,
        obs: Observation,
        model: str | None = None,
    ) -> ExecutionPlan | None:
        """Query local Ollama model to produce a structured JSON execution plan."""
        from app.llm.ollama_client import OllamaClient

        client = OllamaClient()
        available_tools = tool_registry.list_tools()
        tools_summary = "\n".join(f"- {t.name}: {t.description}" for t in available_tools)

        prompt = (
            "You are Aria's OPEC Planner. Break down the user objective into an execution plan.\n"
            "Respond ONLY with a JSON object in this exact schema:\n"
            "{\n"
            '  "strategy": "High level strategy",\n'
            '  "steps": [\n'
            '    {"step_id": 1, "action": "tool_name", "args": {"param": "val"}, "description": "why"}\n'
            "  ]\n"
            "}\n\n"
            f"Available local tools:\n{tools_summary}\n\n"
            f"User Objective: {goal}\n"
            f"Entities detected: {obs.extracted_entities}\n"
        )

        try:
            full_reply = ""
            async for chunk in client.stream_chat(
                [{"role": "user", "content": prompt}], model=model
            ):
                if chunk["type"] == "delta":
                    full_reply += chunk["content"]

            # Parse JSON from model reply
            clean_json = full_reply.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            data = json.loads(clean_json)
            raw_steps = data.get("steps", [])
            steps = []
            for s in raw_steps:
                action = s.get("action", "")
                if tool_registry.get(action) or action == "synthesize_response":
                    steps.append(
                        PlanStep(
                            step_id=int(s.get("step_id", len(steps) + 1)),
                            action=action,
                            args=s.get("args") or {},
                            description=s.get("description", ""),
                            dependencies=s.get("dependencies") or [],
                        )
                    )

            if steps:
                return ExecutionPlan(
                    plan_id=plan_id,
                    goal=goal,
                    strategy=data.get("strategy", ""),
                    steps=steps,
                )
        except Exception as exc:
            logger.debug(f"LLM plan generation bypassed or failed: {exc}")

        return None

    def replan(
        self,
        current_plan: ExecutionPlan,
        failed_step: PlanStep,
        critique: str,
    ) -> ExecutionPlan:
        """Create a revised plan addressing failed step and critique feedback."""
        new_plan = ExecutionPlan(
            plan_id=f"{current_plan.plan_id}-rev",
            goal=current_plan.goal,
            strategy=f"Replanned after step {failed_step.step_id} failure: {critique}",
        )

        for step in current_plan.steps:
            if step.step_id < failed_step.step_id and step.status == "completed":
                new_plan.steps.append(step)
            elif step.step_id == failed_step.step_id:
                # Replace with alternative corrective step or retry
                failed_step.status = "failed"
                new_plan.steps.append(failed_step)
                # Add corrective fallback step
                corrective_id = failed_step.step_id + 10
                new_plan.steps.append(
                    PlanStep(
                        step_id=corrective_id,
                        action="synthesize_response",
                        args={
                            "query": current_plan.goal,
                            "note": f"Fallback after {failed_step.action} failed: {critique}",
                        },
                        description=f"Fallback synthesis due to {critique}",
                        dependencies=[failed_step.step_id],
                    )
                )

        return new_plan


__all__ = ["Planner", "PlanStep", "ExecutionPlan"]
