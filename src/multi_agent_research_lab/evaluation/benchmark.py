"""Benchmark evaluation for single-agent baseline vs multi-agent system."""

from collections.abc import Callable
from time import perf_counter

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

Runner = Callable[[str], ResearchState]


def compute_citation_coverage(state: ResearchState) -> float:
    """Calculate the ratio of available sources that are cited in the final answer."""
    if not state.sources or not state.final_answer:
        return 0.0

    cited_indices: set[int] = set()
    for i in range(1, len(state.sources) + 1):
        if f"[{i}]" in state.final_answer or f"[{i}:" in state.final_answer:
            cited_indices.add(i)

    return len(cited_indices) / len(state.sources)


def compute_total_cost(state: ResearchState) -> float:
    """Sum estimated costs from all agent results recorded in state."""
    total_cost = 0.0
    for result in state.agent_results:
        cost = result.metadata.get("cost_usd")
        if cost and isinstance(cost, (int, float)):
            total_cost += float(cost)
    return total_cost


def estimate_quality_score(state: ResearchState) -> float:
    """Heuristic quality scoring on 0-10 scale based on rubric criteria.

    Evaluates:
    - Groundedness / Citations (up to 3.0 pts)
    - Structural Depth and Formatting (up to 3.0 pts)
    - Intermediate Reasoning State (up to 2.0 pts)
    - Relevance / Non-empty Answer (up to 2.0 pts)
    """
    if not state.final_answer:
        return 0.0

    score = 0.0

    # Non-empty and reasonable length
    if len(state.final_answer) > 200:
        score += 2.0
    elif len(state.final_answer) > 50:
        score += 1.0

    # Markdown structure (headers, lists)
    if "# " in state.final_answer or "## " in state.final_answer:
        score += 1.5
    if "- " in state.final_answer or "* " in state.final_answer:
        score += 1.5

    # Citations coverage
    cov = compute_citation_coverage(state)
    score += cov * 3.0

    # Intermediate reasoning notes presence
    if state.analysis_notes:
        score += 1.0
    if state.research_notes:
        score += 1.0

    return min(round(score, 1), 10.0)


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Execute runner on query and compute comprehensive benchmark metrics."""
    started = perf_counter()
    has_error = False
    try:
        state = runner(query)
    except Exception as exc:
        has_error = True
        state = ResearchState(request={"query": query})  # type: ignore[arg-type]
        state.errors.append(str(exc))

    latency = perf_counter() - started
    cost = compute_total_cost(state) if not has_error else 0.0
    coverage = compute_citation_coverage(state) if not has_error else 0.0
    quality = estimate_quality_score(state) if not has_error else 0.0
    failure_rate = 1.0 if (has_error or bool(state.errors)) else 0.0

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=round(latency, 2),
        estimated_cost_usd=round(cost, 6) if cost > 0 else None,
        quality_score=quality,
        citation_coverage=round(coverage, 2),
        failure_rate=failure_rate,
        notes=f"Processed in {state.iteration} iterations"
        if not has_error
        else "Failed with errors",
    )
    return state, metrics
