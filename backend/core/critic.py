"""OPEC Agent Loop: Critic Component for self-reflection and execution evaluation."""

import logging
from dataclasses import dataclass

from core.executor import StepExecutionResult
from core.planner import PlanStep

logger = logging.getLogger("aria.core.critic")


@dataclass
class Critique:
    """Evaluation produced by the Critic for a step or entire plan."""

    step_id: int
    success: bool
    score: float  # 0.0 to 1.0
    evaluation: str
    needs_replan: bool = False
    suggested_action: str = "continue"  # continue, retry, replan, abort


class Critic:
    """Evaluates execution outputs, catches failures, and guides self-correction."""

    def evaluate_step(
        self,
        step: PlanStep,
        result: StepExecutionResult,
        goal: str,
    ) -> Critique:
        """Evaluate whether an executed step succeeded and fulfilled expectations."""
        # 1. Action requires approval: valid pending state
        if result.requires_approval:
            return Critique(
                step_id=step.step_id,
                success=True,
                score=1.0,
                evaluation="Action successfully submitted for owner approval.",
                needs_replan=False,
                suggested_action="await_approval",
            )

        # 2. Hard failure or error returned
        if not result.success or result.error:
            error_str = result.error or "Unknown failure"
            return Critique(
                step_id=step.step_id,
                success=False,
                score=0.0,
                evaluation=f"Step {step.step_id} failed with error: {error_str}",
                needs_replan=True,
                suggested_action="replan",
            )

        # 3. Output emptiness check
        raw_out = str(result.output or "").strip()
        if not raw_out:
            return Critique(
                step_id=step.step_id,
                success=False,
                score=0.2,
                evaluation="Step produced empty output without explicit error.",
                needs_replan=True,
                suggested_action="replan",
            )

        # 4. Check for typical tool-level soft failures
        if "not found" in raw_out.lower() and step.action == "files.read":
            return Critique(
                step_id=step.step_id,
                success=False,
                score=0.3,
                evaluation=f"File specified in {step.action} was not found.",
                needs_replan=True,
                suggested_action="replan",
            )

        # 5. Success
        return Critique(
            step_id=step.step_id,
            success=True,
            score=1.0,
            evaluation="Step executed successfully with valid output.",
            needs_replan=False,
            suggested_action="continue",
        )

    def evaluate_plan_completion(
        self,
        goal: str,
        step_results: list[StepExecutionResult],
    ) -> Critique:
        """Assess overall completion across all executed steps."""
        if not step_results:
            return Critique(
                step_id=0,
                success=False,
                score=0.0,
                evaluation="No steps were executed.",
                needs_replan=True,
            )

        failed = [r for r in step_results if not r.success]
        if failed:
            return Critique(
                step_id=0,
                success=False,
                score=len(step_results) - len(failed) / len(step_results),
                evaluation=f"{len(failed)} of {len(step_results)} steps failed.",
                needs_replan=True,
            )

        return Critique(
            step_id=0,
            success=True,
            score=1.0,
            evaluation="All planned steps executed successfully.",
            needs_replan=False,
            suggested_action="finish",
        )


__all__ = ["Critic", "Critique"]
