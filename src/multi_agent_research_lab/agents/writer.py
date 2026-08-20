"""Writer agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(
        self,
        settings: Settings | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or LLMClient(self.settings)

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""
        system_prompt = (
            "You are a professional technical writer and research synthesist. "
            "Your job is to produce a comprehensive, publication-ready research report "
            "based on the provided research notes and analysis notes.\n\n"
            "REQUIREMENTS:\n"
            "1. Ground all claims in the provided sources.\n"
            "2. Use inline citations like [1], [2] referencing the source notes.\n"
            "3. Structure with clear Markdown headers, bullet points, and deep technical details.\n"
            "4. Include a 'References / Sources' section at the end."
        )
        notes = state.research_notes or "No research notes available."
        analysis = state.analysis_notes or "No analysis notes available."
        user_prompt = (
            f"Research Topic: {state.request.query}\n"
            f"Target Audience: {state.request.audience}\n\n"
            f"Research Sources & Notes:\n{notes}\n\n"
            f"Structured Analysis Notes:\n{analysis}\n\n"
            "Please write the complete, well-cited research report."
        )

        response = self.llm.complete(system_prompt=system_prompt, user_prompt=user_prompt)

        state.final_answer = response.content
        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=response.content,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event(
            "writer.done",
            {
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            },
        )
        return state
