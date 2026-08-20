"""Researcher agent implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.search_client import SearchClient


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(
        self,
        settings: Settings | None = None,
        search_client: SearchClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.search_client = search_client or SearchClient(self.settings)

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""
        docs = self.search_client.search(
            query=state.request.query,
            max_results=state.request.max_sources,
        )

        state.sources = docs
        notes_lines: list[str] = []
        for i, doc in enumerate(docs, 1):
            notes_lines.append(
                f"[{i}] Title: {doc.title}\n"
                f"    URL/Source: {doc.url or 'N/A'}\n"
                f"    Snippet: {doc.snippet}"
            )
        state.research_notes = "\n\n".join(notes_lines)

        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=state.research_notes,
                metadata={"num_sources": len(docs)},
            )
        )
        state.add_trace_event("researcher.done", {"num_sources": len(docs)})
        return state
