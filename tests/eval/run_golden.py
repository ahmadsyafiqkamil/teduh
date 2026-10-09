"""Measure tool selection against tests/eval/golden_questions.yaml (CONCEPT §13, >= 90%).

Deliberately NOT a pytest test. Each question is a real Gemini call, so putting these in the
suite would make `uv run pytest` cost money, take minutes, and fail intermittently for
reasons unrelated to the code under change.

What is graded is which TOOLS the agent reached for, not the prose it produced. Prose is
judged separately by the provenance validator. That split matters: an answer can be
beautifully worded and still be wrong because it never consulted the data, and that is
exactly the failure this project exists to prevent.

Run: uv run python -m tests.eval.run_golden
Output: tests/eval/reports/golden_<timestamp>.json
"""

import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from teduh_agent.agent import root_agent

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "tests" / "eval" / "golden_questions.yaml"
REPORT_DIR = ROOT / "tests" / "eval" / "reports"

APP_NAME = "teduh_agent"
USER_ID = "eval"

# CONCEPT §13.
TOOL_ACCURACY_TARGET = 0.9
LATENCY_P50_TARGET_S = 8.0

# A question that hangs would otherwise stall the whole run.
PER_QUESTION_TIMEOUT_S = 120.0

# ADK-internal tools that are routing machinery, not domain tools. transfer_to_agent is how
# the coordinator hands off to a sub-agent; grading it as a wrong tool call would fail every
# allow_extra:false question that legitimately routes to a specialist. The routing is still
# visible in Outcome.agents, so nothing is hidden -- only the domain-tool signal is graded.
IGNORED_TOOLS = frozenset({"transfer_to_agent"})


@dataclass(frozen=True)
class Outcome:
    id: str
    question: str
    expected_tools: list[str]
    called_tools: list[str]
    forbidden_hit: list[str]
    allow_extra: bool
    passed: bool
    reason: str
    elapsed_s: float
    agents: list[str]


def load_questions() -> list[dict]:
    questions = yaml.safe_load(GOLDEN_PATH.read_text())
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{GOLDEN_PATH} tidak memuat daftar pertanyaan")
    return questions


def _tools_and_agents(event) -> tuple[list[str], str | None]:
    """Extract tool names called in one event, plus the agent that authored it."""
    tools: list[str] = []
    content = getattr(event, "content", None)
    for part in getattr(content, "parts", None) or []:
        call = getattr(part, "function_call", None)
        if call is not None and getattr(call, "name", None) and call.name not in IGNORED_TOOLS:
            tools.append(call.name)
    return tools, getattr(event, "author", None)


async def _ask(runner: Runner, session_id: str, question: str) -> tuple[list[str], list[str]]:
    called: list[str] = []
    agents: list[str] = []
    message = types.Content(role="user", parts=[types.Part(text=question)])

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=message
    ):
        tools, author = _tools_and_agents(event)
        called.extend(tools)
        if author and author not in agents:
            agents.append(author)
    return called, agents


async def run_one(runner: Runner, question: dict, index: int) -> Outcome:
    """Ask one question in a fresh session and grade the tools it reached for.

    Async so every question runs on the SAME event loop as its siblings. The [OI]-compatible
    model backend holds an httpx connection pool that is bound to the loop it was created on;
    wrapping each question in its own asyncio.run() closes that loop underneath the client and
    the next question dies with "Event loop is closed".
    """
    session_id = f"golden-{index}"
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )

    expected = list(question.get("expected_tools") or [])
    forbidden = list(question.get("forbidden_tools") or [])
    allow_extra = bool(question.get("allow_extra", True))

    started = time.perf_counter()
    try:
        called, agents = await asyncio.wait_for(
            _ask(runner, session_id, question["question"]),
            timeout=PER_QUESTION_TIMEOUT_S,
        )
    except TimeoutError:
        return Outcome(
            id=question["id"],
            question=question["question"],
            expected_tools=expected,
            called_tools=[],
            forbidden_hit=[],
            allow_extra=allow_extra,
            passed=False,
            reason=f"waktu habis setelah {PER_QUESTION_TIMEOUT_S:.0f} detik",
            elapsed_s=time.perf_counter() - started,
            agents=[],
        )
    elapsed = time.perf_counter() - started

    called_set = set(called)
    missing = [tool for tool in expected if tool not in called_set]
    forbidden_hit = [tool for tool in forbidden if tool in called_set]
    extra = [tool for tool in called_set if tool not in expected]

    reasons: list[str] = []
    if missing:
        reasons.append(f"tool wajib tidak dipanggil: {', '.join(missing)}")
    if forbidden_hit:
        reasons.append(f"tool terlarang dipanggil: {', '.join(forbidden_hit)}")
    if not allow_extra and extra:
        reasons.append(f"tool di luar rute yang benar: {', '.join(sorted(extra))}")

    return Outcome(
        id=question["id"],
        question=question["question"],
        expected_tools=expected,
        called_tools=called,
        forbidden_hit=forbidden_hit,
        allow_extra=allow_extra,
        passed=not reasons,
        reason="; ".join(reasons) or "ok",
        elapsed_s=elapsed,
        agents=agents,
    )


def score(outcomes: list[Outcome]) -> dict:
    latencies = sorted(outcome.elapsed_s for outcome in outcomes)
    passed = sum(1 for outcome in outcomes if outcome.passed)
    return {
        "n_questions": len(outcomes),
        "n_passed": passed,
        "tool_accuracy": passed / len(outcomes) if outcomes else 0.0,
        "latency_p50_s": statistics.median(latencies) if latencies else 0.0,
        "latency_p95_s": latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0,
        "latency_max_s": latencies[-1] if latencies else 0.0,
        "targets": {
            "tool_accuracy": TOOL_ACCURACY_TARGET,
            "latency_p50_s": LATENCY_P50_TARGET_S,
        },
    }


async def main() -> None:
    questions = load_questions()
    runner = Runner(
        agent=root_agent, app_name=APP_NAME, session_service=InMemorySessionService()
    )
    print(f"evaluasi    : {len(questions)} pertanyaan terhadap {root_agent.name}")

    outcomes: list[Outcome] = []
    for index, question in enumerate(questions):
        outcome = await run_one(runner, question, index)
        outcomes.append(outcome)
        mark = "OK  " if outcome.passed else "GAGAL"
        print(
            f"  {mark} {outcome.id}  {outcome.elapsed_s:5.1f}s  "
            f"[{', '.join(outcome.called_tools) or '-'}]"
        )
        if not outcome.passed:
            print(f"        {outcome.reason}")

    summary = score(outcomes)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = REPORT_DIR / f"golden_{stamp}.json"
    report.write_text(
        json.dumps(
            {
                "run_at": datetime.now(UTC).isoformat(),
                "agent": root_agent.name,
                "summary": summary,
                "outcomes": [asdict(outcome) for outcome in outcomes],
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        f"\nakurasi tool: {summary['n_passed']}/{summary['n_questions']} = "
        f"{summary['tool_accuracy']:.1%} (target {TOOL_ACCURACY_TARGET:.0%})"
    )
    print(
        f"latensi     : p50 {summary['latency_p50_s']:.1f}s · "
        f"p95 {summary['latency_p95_s']:.1f}s · maks {summary['latency_max_s']:.1f}s "
        f"(target p50 < {LATENCY_P50_TARGET_S:.0f}s)"
    )
    print(f"laporan     : {report.relative_to(ROOT)}")

    check(summary)


def check(summary: dict) -> None:
    """Report honestly against the targets. Never adjust the eval set to pass."""
    if summary["tool_accuracy"] < TOOL_ACCURACY_TARGET:
        print(
            f"\nPERINGATAN: akurasi pemilihan tool {summary['tool_accuracy']:.1%} di bawah "
            f"target {TOOL_ACCURACY_TARGET:.0%}. Perbaiki prompt sistem atau deskripsi tool. "
            "JANGAN mengubah golden_questions.yaml agar lulus, dan JANGAN mengklaim 90% "
            "di proposal."
        )
    if summary["latency_p50_s"] > LATENCY_P50_TARGET_S:
        print(
            f"PERINGATAN: p50 {summary['latency_p50_s']:.1f}s melewati target "
            f"{LATENCY_P50_TARGET_S:.0f}s. Periksa cache store dan jumlah tool call per jawaban."
        )
    assert summary["n_questions"] == 20, (
        f"{summary['n_questions']} pertanyaan dievaluasi, CONCEPT §13 menyebut 20"
    )
    print("check ok")


if __name__ == "__main__":
    asyncio.run(main())
