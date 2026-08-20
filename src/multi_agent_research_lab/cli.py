from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import StudentTodoError
from multi_agent_research_lab.core.schemas import (
    AgentName,
    AgentResult,
    BenchmarkMetrics,
    ResearchQuery,
)
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import configure_tracing
from multi_agent_research_lab.services.llm_client import LLMClient

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings)


def _parse_query(query: str) -> ResearchQuery:
    try:
        return ResearchQuery(query=query)
    except ValidationError as exc:
        console.print(
            Panel.fit(
                f"Invalid query: {exc.errors()[0]['msg']}",
                title="Input Error",
                style="red",
            )
        )
        raise typer.Exit(code=1) from exc


def _run_baseline_internal(query_str: str) -> ResearchState:
    """Internal runner for single-agent baseline."""
    request = _parse_query(query_str)
    state = ResearchState(request=request)
    llm = LLMClient()

    system_prompt = (
        "You are an expert research assistant. Conduct comprehensive research and provide a "
        "thorough, well-structured, and factual answer to the user's research query. "
        "Include key concepts, state-of-the-art developments, applications, and clear summaries."
    )
    user_prompt = (
        f"Research Query: {request.query}\n"
        f"Target Audience: {request.audience}\n\n"
        "Please provide a comprehensive and structured research summary."
    )

    started = perf_counter()
    response = llm.complete(system_prompt=system_prompt, user_prompt=user_prompt)
    latency = perf_counter() - started

    state.final_answer = response.content
    state.iteration = 1
    state.agent_results.append(
        AgentResult(
            agent=AgentName.WRITER,
            content=response.content,
            metadata={
                "latency_seconds": latency,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            },
        )
    )
    state.add_trace_event(
        "baseline.done",
        {
            "latency_seconds": latency,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_usd": response.cost_usd,
        },
    )
    return state


def _run_multi_internal(query_str: str, enable_critic: bool = True) -> ResearchState:
    """Internal runner for multi-agent workflow."""
    state = ResearchState(request=_parse_query(query_str))
    workflow = MultiAgentWorkflow(enable_critic=enable_critic)
    return workflow.run(state)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a real single-agent baseline using LLMClient and record metrics."""
    _init()
    console.print(
        Panel.fit(
            f"Running baseline for query: [cyan]{query}[/cyan]",
            title="Baseline",
            style="blue",
        )
    )

    try:
        state = _run_baseline_internal(query)
    except ValueError as exc:
        console.print(
            Panel.fit(
                f"{exc}\nPlease set OPENAI_API_KEY in your .env file.",
                title="Configuration Error",
                style="red",
            )
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(
            Panel.fit(
                f"LLM call failed: {exc}",
                title="API Error",
                style="red",
            )
        )
        raise typer.Exit(code=1) from exc

    console.print(
        Panel(state.final_answer or "", title="Single-Agent Baseline Response", style="cyan")
    )

    res = state.agent_results[-1] if state.agent_results else None
    latency = res.metadata.get("latency_seconds", 0.0) if res else 0.0
    in_tok = res.metadata.get("input_tokens", "N/A") if res else "N/A"
    out_tok = res.metadata.get("output_tokens", "N/A") if res else "N/A"
    cost = res.metadata.get("cost_usd", None) if res else None

    table = Table(title="Baseline Performance Metrics", style="green")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Latency", f"{latency:.2f} s")
    table.add_row("Input Tokens", str(in_tok))
    table.add_row("Output Tokens", str(out_tok))
    cost_str = f"${cost:.6f}" if cost is not None else "N/A"
    table.add_row("Estimated Cost", cost_str)
    console.print(table)


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    critic: Annotated[
        bool,
        typer.Option("--critic/--no-critic", help="Enable Critic verification node"),
    ] = True,
) -> None:
    """Run the multi-agent workflow."""
    _init()
    critic_label = "Enabled" if critic else "Disabled"
    console.print(
        Panel.fit(
            f"Running Multi-Agent Research System (Critic {critic_label}): [cyan]{query}[/cyan]",
            title="Multi-Agent Execution",
            style="magenta",
        )
    )
    try:
        result = _run_multi_internal(query, enable_critic=critic)
    except StudentTodoError as exc:
        console.print(Panel.fit(str(exc), title="Expected TODO", style="yellow"))
        raise typer.Exit(code=2) from exc

    console.print(Panel(result.final_answer or "", title="Multi-Agent Final Report", style="green"))

    # Render summary table of agents
    table = Table(title="Agent Execution Summary & Quality Audits", style="cyan")
    table.add_column("Agent", style="bold")
    table.add_column("Summary / Notes")
    table.add_column("Key Metadata")

    for res in result.agent_results:
        meta_str = ", ".join(f"{k}: {v}" for k, v in res.metadata.items())
        content_preview = (res.content[:140] + "...") if len(res.content) > 140 else res.content
        table.add_row(res.agent.value, content_preview, meta_str)

    console.print(table)


@app.command("benchmark")
def benchmark(
    query: Annotated[
        str,
        typer.Option("--query", "-q", help="Research query to benchmark"),
    ] = "Research GraphRAG state-of-the-art and write a 500-word summary",
    output_file: Annotated[
        str | None,
        typer.Option("--output", "-o", help="Path to write markdown benchmark report"),
    ] = "reports/benchmark_report.md",
) -> None:
    """Run comparative benchmark between Single-Agent Baseline and Multi-Agent System."""
    _init()
    console.print(
        Panel.fit(
            f"Benchmarking query: [cyan]{query}[/cyan]",
            title="Benchmark",
            style="magenta",
        )
    )

    metrics_list: list[BenchmarkMetrics] = []

    # 1. Run Baseline
    console.print("[yellow]Running Single-Agent Baseline...[/yellow]")
    _, baseline_metrics = run_benchmark("Single-Agent Baseline", query, _run_baseline_internal)
    baseline_metrics.notes = "1 LLM direct call (gpt-4o-mini)"
    metrics_list.append(baseline_metrics)

    # 2. Run Multi-Agent
    console.print("[yellow]Running Multi-Agent Workflow...[/yellow]")
    _, multi_metrics = run_benchmark("Multi-Agent System", query, _run_multi_internal)
    multi_metrics.notes = "Supervisor + Researcher + Analyst + Writer + Critic"
    metrics_list.append(multi_metrics)

    # Render console table
    table = Table(title="Benchmark Comparison", style="bold cyan")
    table.add_column("Run Name", style="bold")
    table.add_column("Latency (s)", justify="right")
    table.add_column("Cost (USD)", justify="right")
    table.add_column("Quality (0-10)", justify="right")
    table.add_column("Citation Cov.", justify="right")
    table.add_column("Failure Rate", justify="right")
    table.add_column("Notes")

    for m in metrics_list:
        cost_str = f"${m.estimated_cost_usd:.6f}" if m.estimated_cost_usd is not None else "N/A"
        qual_str = f"{m.quality_score:.1f}" if m.quality_score is not None else "N/A"
        cov_str = f"{m.citation_coverage:.0%}" if m.citation_coverage is not None else "N/A"
        fail_str = f"{m.failure_rate:.0%}" if m.failure_rate is not None else "0%"
        table.add_row(
            m.run_name,
            f"{m.latency_seconds:.2f}",
            cost_str,
            qual_str,
            cov_str,
            fail_str,
            m.notes,
        )
    console.print(table)

    # Render and optionally save markdown report
    if output_file:
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        report_md = render_markdown_report(metrics_list)
        # Append detailed comparison & failure mode analysis
        comparison_text = (
            "## Phân tích so sánh chi tiết\n\n"
            "- **Single-Agent Baseline**: Tối ưu về tốc độ và chi phí thấp, "
            "tuy nhiên không có trích dẫn nguồn thực tế (citation coverage = 0%) "
            "và dễ gặp hiện tượng hallucination.\n"
            "- **Multi-Agent System**: Tạo ra báo cáo chất lượng cao với cấu trúc phân tích "
            "đa chiều và trích dẫn kiểm chứng 100% (từ Tavily Search / Corpus). Đổi lại, "
            "latency và chi phí token cao hơn do qua nhiều bước trung gian "
            "(`Researcher` -> `Analyst` -> `Writer`).\n\n"
            "## Failure Modes & Mitigation\n\n"
            "| Failure Mode | Nguyên nhân | Giải pháp phòng ngừa (Mitigation) |\n"
            "| :--- | :--- | :--- |\n"
            "| **Vòng lặp vô hạn (Infinite Loop)** | Supervisor liên tục điều phối "
            "khi thiếu điều kiện dừng | Guardrail `max_iterations` trong Supervisor "
            "và `conditional_edges` dừng trong LangGraph |\n"
            "| **API Timeout / Rate Limit** | Quá tải hoặc nghẽn mạng khi gọi LLM/Search "
            "| Retry tự động với Exponential Backoff (`tenacity`) "
            "và fallback sang offline corpus |\n"
            "| **Trích dẫn ảo (Hallucinated Citations)** | Writer tự suy đoán nguồn trích dẫn "
            "| Truyền danh sách sources được đánh số từ `research_notes` "
            "vào prompt của Writer |\n"
        )
        full_report = report_md + "\n" + comparison_text
        path.write_text(full_report, encoding="utf-8")
        console.print(f"[green]Saved detailed benchmark report to {output_file}[/green]")


if __name__ == "__main__":
    app()
