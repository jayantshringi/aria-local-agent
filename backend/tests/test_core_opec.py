"""Unit and integration tests for the OPEC Agent Loop and Vector Memory."""

import pytest

from app.agent.kill_switch import kill_switch
from core.critic import Critic
from core.executor import Executor
from core.loop import OPECAgentLoop
from core.memory import InMemoryVectorStore
from core.observer import Observer
from core.planner import ExecutionPlan, Planner, PlanStep


@pytest.mark.asyncio
async def test_observer_analysis():
    observer = Observer()
    obs = await observer.observe(
        user_input="Please search for file report.md and visit https://example.org",
        history=[{"role": "user", "content": "hello"}],
    )

    assert obs.intent == "task_execution"
    assert "https://example.org" in obs.extracted_entities["urls"]
    assert "report.md" in obs.extracted_entities["paths"]
    assert "os" in obs.ambient_state
    assert len(obs.dialogue_context) == 1


@pytest.mark.asyncio
async def test_planner_heuristic():
    planner = Planner()
    observer = Observer()

    # Git status plan
    obs_git = await observer.observe("Check git status")
    plan_git = await planner.create_plan(obs_git)
    assert len(plan_git.steps) == 1
    assert plan_git.steps[0].action == "git.action"
    assert plan_git.steps[0].args["action"] == "status"

    # Browser navigation plan
    obs_web = await observer.observe("Go to https://news.ycombinator.com")
    plan_web = await planner.create_plan(obs_web)
    assert len(plan_web.steps) == 1
    assert plan_web.steps[0].action == "browser.navigate"


def test_planner_replan():
    planner = Planner()
    plan = ExecutionPlan(
        plan_id="plan-1",
        goal="Read config.json",
        steps=[
            PlanStep(step_id=1, action="files.read", args={"path": "config.json"}),
            PlanStep(step_id=2, action="synthesize_response", args={}, dependencies=[1]),
        ],
    )
    failed_step = plan.steps[0]
    revised = planner.replan(plan, failed_step, critique="File config.json was not found")

    assert revised.plan_id.endswith("-rev")
    assert any(s.action == "synthesize_response" for s in revised.steps)


@pytest.mark.asyncio
async def test_executor_and_kill_switch():
    executor = Executor()
    observer = Observer()
    obs = await observer.observe("Check status")

    step = PlanStep(step_id=1, action="os.action", args={"action": "system_info"})

    # Normal execution (mocking/allowing low risk or approved execution)
    res = await executor.execute_step(step, obs, auto_approve_low_risk=True)
    assert res.step_id == 1

    # Kill switch active
    await kill_switch.trigger()
    try:
        blocked_res = await executor.execute_step(step, obs)
        assert blocked_res.success is False
        assert "kill switch is currently active" in blocked_res.error
    finally:
        kill_switch.reset()


def test_critic_evaluations():
    critic = Critic()

    # Successful step
    from core.executor import StepExecutionResult

    step = PlanStep(step_id=1, action="test.tool")
    good_res = StepExecutionResult(
        step_id=1, action="test.tool", success=True, output="File found."
    )
    critique_good = critic.evaluate_step(step, good_res, "find file")
    assert critique_good.success is True
    assert critique_good.needs_replan is False
    assert critique_good.score == 1.0

    # Failed step
    bad_res = StepExecutionResult(step_id=1, action="test.tool", success=False, error="Disk full")
    critique_bad = critic.evaluate_step(step, bad_res, "find file")
    assert critique_bad.success is False
    assert critique_bad.needs_replan is True
    assert critique_bad.score == 0.0


@pytest.mark.asyncio
async def test_opec_agent_loop_end_to_end():
    loop = OPECAgentLoop()
    events = []

    def on_event(ev):
        events.append(ev)

    result = await loop.run(
        user_input="git status",
        event_callback=on_event,
    )

    assert result["success"] is True
    assert len(result["events"]) > 0
    event_types = [e["type"] for e in result["events"]]
    assert "observe_start" in event_types
    assert "observed" in event_types
    assert "plan_created" in event_types
    assert "loop_completed" in event_types
    assert result["final_answer"] is not None


def test_in_memory_vector_store():
    store = InMemoryVectorStore(dimension=3)
    assert store.count() == 0

    store.add("doc1", "Document one", [1.0, 0.0, 0.0])
    store.add("doc2", "Document two", [0.0, 1.0, 0.0])
    store.add("doc3", "Document three", [0.8, 0.6, 0.0])

    assert store.count() == 3

    # Query closest to doc1
    results = store.query([1.0, 0.0, 0.0], top_k=2)
    assert len(results) == 2
    assert results[0][0].id == "doc1"
    assert round(results[0][1], 2) == 1.0

    assert store.delete("doc2") is True
    assert store.count() == 2
