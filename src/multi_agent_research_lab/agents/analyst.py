"""Analyst agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or LLMClient(self.settings)

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""
        system_prompt = (
            "You are an expert research analyst. Your responsibility is to analyze "
            "the collected research notes, extract key claims, identify consensus or trade-offs, "
            "and evaluate evidence reliability. Output structured analysis notes."
        )
        notes = state.research_notes or "No research notes available."
        user_prompt = (
            f"Research Topic: {state.request.query}\n"
            f"Target Audience: {state.request.audience}\n\n"
            f"Collected Research Notes:\n{notes}\n\n"
            "Please provide a structured synthesis covering key themes, comparison of viewpoints, "
            "strengths/limitations of evidence, and core takeaways."
        )

        response = self.llm.complete(system_prompt=system_prompt, user_prompt=user_prompt)

        state.analysis_notes = response.content
        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=response.content,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event(
            "analyst.done",
            {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            },
        )
        return state
