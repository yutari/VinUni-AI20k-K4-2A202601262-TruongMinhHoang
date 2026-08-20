"""Benchmark report rendering."""

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics]) -> str:
    """Render comprehensive benchmark metrics to Markdown."""
    lines = [
        "# Benchmark Report",
        "",
        "| Run | Latency (s) | Cost (USD) | Quality | Citation Cov. | Failure Rate | Notes |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in metrics:
        cost = f"${item.estimated_cost_usd:.6f}" if item.estimated_cost_usd is not None else "N/A"
        quality = f"{item.quality_score:.1f}" if item.quality_score is not None else "N/A"
        citation = f"{item.citation_coverage:.0%}" if item.citation_coverage is not None else "N/A"
        failure = f"{item.failure_rate:.0%}" if item.failure_rate is not None else "0%"
        lines.append(
            f"| **{item.run_name}** | {item.latency_seconds:.2f} | {cost} | {quality} "
            f"| {citation} | {failure} | {item.notes} |"
        )
    return "\n".join(lines) + "\n"
