"""Critic agent implementation for citation verification and quality checks."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


class CriticAgent(BaseAgent):
    """Fact-checking and citation audit agent."""

    name = "critic"

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or LLMClient(self.settings)

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and calculate citation coverage."""
        if not state.final_answer:
            return state

        cited_indices: list[int] = []
        for i, doc in enumerate(state.sources, 1):
            if f"[{i}]" in state.final_answer or doc.title.lower() in state.final_answer.lower():
                cited_indices.append(i)

        cited_count = len(cited_indices)
        total_sources = len(state.sources)
        coverage = (cited_count / total_sources) if total_sources > 0 else 1.0

        status = "PASSED" if coverage >= 0.8 else "NEEDS_IMPROVEMENT"
        warning = (
            "" if coverage >= 0.8 else " WARNING: Citation coverage is below the 80% threshold."
        )
        review_note = (
            f"Citation Audit [{status}]: {cited_count}/{total_sources} "
            f"sources cited ({coverage:.0%}).{warning}"
        )

        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=review_note,
                metadata={
                    "citation_coverage": coverage,
                    "sources_count": total_sources,
                    "cited_indices": cited_indices,
                    "audit_status": status,
                },
            )
        )
        state.add_trace_event(
            "critic.done",
            {"citation_coverage": coverage, "audit_status": status, "cited_count": cited_count},
        )
        return state
