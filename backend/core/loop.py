"""OPEC Agent Loop: Central Orchestrator coordinating Observer, Planner, Executor, and Critic."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from app.llm.ollama_client import OllamaClient
from app.llm.persona import load_persona
from core.critic import Critic, Critique
from core.executor import Executor, StepExecutionResult
from core.observer import Observation, Observer
from core.planner import ExecutionPlan, Planner

logger = logging.getLogger("aria.core.loop")


class OPECAgentLoop:
    """The central Observer-Planner-Executor-Critic autonomous agent loop for Aria."""

    def __init__(
        self,
        observer: Observer | None = None,
        planner: Planner | None = None,
        executor: Executor | None = None,
        critic: Critic | None = None,
        max_replans: int = 2,
    ) -> None:
        self.observer = observer or Observer()
        self.planner = planner or Planner()
        self.executor = executor or Executor()
        self.critic = critic or Critic()
        self.max_replans = max_replans
        self.ollama_client = OllamaClient()

    async def run(
        self,
        user_input: str,
        session_id: str | None = None,
        device_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        model: str | None = None,
        event_callback: Callable[[dict[str, Any]], Any] | None = None,
    ) -> dict[str, Any]:
        """Execute complete OPEC loop end-to-end with status reporting."""
        collected_events: list[dict[str, Any]] = []

        async def emit(ev: dict[str, Any]) -> None:
            collected_events.append(ev)
            if event_callback:
                try:
                    res = event_callback(ev)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as cb_err:
                    logger.debug(f"Event callback non-fatal notice: {cb_err}")

        # 1. OBSERVE
        await emit({"type": "observe_start", "input": user_input})
        observation = await self.observer.observe(
            user_input=user_input,
            session_id=session_id,
            history=history,
        )
        await emit(
            {
                "type": "observed",
                "intent": observation.intent,
                "entities": observation.extracted_entities,
                "ambient": observation.ambient_state,
            }
        )

        # 2. PLAN
        await emit({"type": "plan_start"})
        plan = await self.planner.create_plan(observation, model=model)
        await emit(
            {
                "type": "plan_created",
                "plan_id": plan.plan_id,
                "strategy": plan.strategy,
                "step_count": len(plan.steps),
                "steps": [
                    {
                        "step_id": s.step_id,
                        "action": s.action,
                        "description": s.description,
                        "args": s.args,
                    }
                    for s in plan.steps
                ],
            }
        )

        # 3. EXECUTE & CRITIQUE LOOP
        executed_results: list[StepExecutionResult] = []
        critiques: list[Critique] = []
        replan_count = 0

        while True:
            pending_steps = plan.get_pending_steps()
            if not pending_steps:
                break

            current_step = pending_steps[0]
            current_step.status = "executing"
            await emit(
                {
                    "type": "step_executing",
                    "step_id": current_step.step_id,
                    "action": current_step.action,
                    "args": current_step.args,
                }
            )

            # EXECUTOR
            exec_res = await self.executor.execute_step(
                step=current_step,
                observation=observation,
                session_id=session_id,
                device_id=device_id,
            )
            executed_results.append(exec_res)

            # CRITIC
            critique = self.critic.evaluate_step(
                step=current_step,
                result=exec_res,
                goal=user_input,
            )
            critiques.append(critique)
            current_step.critique = critique.evaluation

            await emit(
                {
                    "type": "step_critiqued",
                    "step_id": current_step.step_id,
                    "action": current_step.action,
                    "success": critique.success,
                    "score": critique.score,
                    "evaluation": critique.evaluation,
                    "needs_replan": critique.needs_replan,
                }
            )

            if critique.needs_replan and replan_count < self.max_replans:
                replan_count += 1
                await emit(
                    {
                        "type": "replanning",
                        "attempt": replan_count,
                        "reason": critique.evaluation,
                    }
                )
                plan = self.planner.replan(
                    current_plan=plan,
                    failed_step=current_step,
                    critique=critique.evaluation,
                )
                continue

            if exec_res.success:
                plan.mark_step_completed(current_step.step_id, exec_res.output)
            else:
                plan.mark_step_failed(current_step.step_id, exec_res.error or "Step failed")

        # 4. SYNTHESIZE FINAL RESPONSE
        final_answer = await self._synthesize_response(
            observation=observation,
            plan=plan,
            executed_results=executed_results,
            model=model,
        )

        await emit(
            {
                "type": "loop_completed",
                "final_answer": final_answer,
                "steps_executed": len(executed_results),
            }
        )

        return {
            "success": all(r.success for r in executed_results) if executed_results else True,
            "observation": observation,
            "plan": plan,
            "step_results": executed_results,
            "critiques": critiques,
            "final_answer": final_answer,
            "events": collected_events,
        }

    async def _synthesize_response(
        self,
        observation: Observation,
        plan: ExecutionPlan,
        executed_results: list[StepExecutionResult],
        model: str | None = None,
    ) -> str:
        """Synthesize final helpful response using LLM or structured summary."""
        # If any tool required approval, formulate concise status message
        approval_steps = [r for r in executed_results if r.requires_approval]
        if approval_steps:
            items = ", ".join(f"'{s.action}'" for s in approval_steps)
            return (
                f"I have prepared the action for {items}. "
                "Because this operation modifies state, please confirm approval on your device to proceed."
            )

        # Build context from executed results
        result_texts = []
        for r in executed_results:
            if r.action != "synthesize_response":
                out_str = str(r.output) if r.output is not None else (r.error or "")
                result_texts.append(f"Result of [{r.action}]:\n{out_str}")

        persona = load_persona()
        prompt_parts = [persona]

        if observation.relevant_memories:
            from app.memory.retrieval import format_memories_for_prompt

            prompt_parts.append(format_memories_for_prompt(observation.relevant_memories))

        if observation.approved_profile_facts:
            from app.memory.profile import format_facts_for_prompt

            prompt_parts.append(format_facts_for_prompt(observation.approved_profile_facts))

        if result_texts:
            prompt_parts.append("## Tool Execution Outputs:\n" + "\n\n".join(result_texts))

        system_prompt = "\n\n".join(prompt_parts)

        messages = [
            {"role": "system", "content": system_prompt},
            *observation.dialogue_context,
            {"role": "user", "content": observation.user_input},
        ]

        try:
            tokens: list[str] = []
            async for chunk in self.ollama_client.stream_chat(messages, model=model):
                if chunk["type"] == "delta":
                    tokens.append(chunk["content"])
            reply = "".join(tokens).strip()
            if reply:
                return reply
        except Exception as exc:
            logger.debug(f"LLM synthesis fallback: {exc}")

        # Deterministic fallback response if LLM offline
        if result_texts:
            return "\n\n".join(result_texts)
        return f"I have processed your request: '{observation.user_input}'."


__all__ = ["OPECAgentLoop"]
