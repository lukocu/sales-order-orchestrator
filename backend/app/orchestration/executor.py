"""Execute a validated, matched plan inside an open tracing run.

Stages run one after another; the tasks of a stage run in parallel, each in its own thread
of a pool that is closed before the next stage starts (so every step is written before the
run finishes). Each attempt is its own deterministic step `agent:<capability>`, the retry is
`agent:<capability>#2`. Only transient database errors (`OperationalError`) are retried, once;
agents only read, so a retry has no side effects to repeat. A pool timeout is not retried: the
pool is exhausted and a retry would only add load to it. A task whose prerequisite did not
complete is skipped without a step. Agent exceptions never escape: they become a `failed` task.
"""

import logging
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from app.orchestration.agents import AgentInput
from app.orchestration.planning import stages
from app.orchestration.registry import CAPABILITIES, AgentSpec
from app.orchestration.schema import AgentResult, Capability, TaskOutcome, TaskStatus
from app.tracing import RunHandle

logger = logging.getLogger(__name__)

TRANSIENT_ERRORS: tuple[type[Exception], ...] = (OperationalError,)
MAX_ATTEMPTS = 2

PlanItem = tuple[Capability, AgentSpec, str]  # capability, matched agent, planner's reason


class UnexpectedResult(Exception):
    """An agent returned the result of another capability."""


@dataclass(frozen=True)
class _Attempts:
    status: TaskStatus
    steps: list[str]
    error_type: str | None
    result: AgentResult | None


def step_name(capability: Capability, attempt: int) -> str:
    base = f"agent:{capability}"
    return base if attempt == 1 else f"{base}#{attempt}"


def _run_task(
    traced: RunHandle,
    engine: Engine,
    capability: Capability,
    agent: AgentSpec,
    agent_input: AgentInput,
    inquiry_id: int | None,
    retry_delay_s: float,
) -> _Attempts:
    steps: list[str] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        name = step_name(capability, attempt)
        steps.append(name)
        try:
            with traced.step(name, kind="deterministic"):
                result = agent.run(engine, agent_input)
                if result.capability != capability:
                    raise UnexpectedResult(f"{agent.name} returned {result.capability}")
        except TRANSIENT_ERRORS as exc:
            if attempt < MAX_ATTEMPTS:
                time.sleep(retry_delay_s)
                continue
            error_type = type(exc).__name__
        except Exception as exc:
            error_type = type(exc).__name__
        else:
            return _Attempts("completed", steps, None, result)
        logger.warning(
            "Orchestration of inquiry %s: %s failed with %s", inquiry_id, name, error_type
        )
        return _Attempts("failed", steps, error_type, None)
    raise AssertionError("unreachable")  # pragma: no cover


def execute(
    traced: RunHandle,
    engine: Engine,
    plan: Sequence[PlanItem],
    agent_input: AgentInput,
    *,
    inquiry_id: int | None = None,
    retry_delay_s: float = 0.5,
) -> list[TaskOutcome]:
    """Run every planned task; outcomes are listed by stage, then in registry order.

    `inquiry_id` only labels the logs.
    """
    planned = {capability: (agent, reason) for capability, agent, reason in plan}
    outcomes: dict[Capability, TaskOutcome] = {}
    results: dict[Capability, AgentResult] = {}

    for stage_number, stage in enumerate(stages(list(planned)), start=1):
        runnable: list[Capability] = []
        for capability in stage:
            agent, reason = planned[capability]
            depends_on = list(CAPABILITIES[capability].depends_on)
            if all(
                outcomes.get(d) is not None and outcomes[d].status == "completed"
                for d in depends_on
            ):
                runnable.append(capability)
            else:
                outcomes[capability] = TaskOutcome(
                    capability=capability,
                    agent=agent.name,
                    reason=reason,
                    depends_on=depends_on,
                    stage=stage_number,
                    status="skipped",
                    steps=[],
                )
        if not runnable:
            continue

        with ThreadPoolExecutor(max_workers=len(runnable)) as pool:
            futures = {}
            for capability in runnable:
                agent, _ = planned[capability]
                task_input = replace(
                    agent_input,
                    upstream={d: results[d] for d in CAPABILITIES[capability].depends_on},
                )
                futures[capability] = pool.submit(
                    _run_task,
                    traced,
                    engine,
                    capability,
                    agent,
                    task_input,
                    inquiry_id,
                    retry_delay_s,
                )
            attempts = {capability: future.result() for capability, future in futures.items()}

        for capability in runnable:
            agent, reason = planned[capability]
            done = attempts[capability]
            outcomes[capability] = TaskOutcome(
                capability=capability,
                agent=agent.name,
                reason=reason,
                depends_on=list(CAPABILITIES[capability].depends_on),
                stage=stage_number,
                status=done.status,
                steps=done.steps,
                error_type=done.error_type,
                result=done.result,
            )
            if done.result is not None:
                results[capability] = done.result

    return [outcomes[c] for stage in stages(list(planned)) for c in stage]
