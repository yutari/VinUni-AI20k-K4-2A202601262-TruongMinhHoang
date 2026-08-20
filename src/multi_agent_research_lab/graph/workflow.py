"""LangGraph workflow implementation."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.state import ResearchState


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    Orchestrates supervisor and worker agents using a StateGraph.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        supervisor: SupervisorAgent | None = None,
        researcher: ResearcherAgent | None = None,
        analyst: AnalystAgent | None = None,
        writer: WriterAgent | None = None,
        critic: CriticAgent | None = None,
        enable_critic: bool = True,
    ) -> None:
        self.settings = settings or get_settings()
        self.enable_critic = enable_critic
        self.supervisor = supervisor or SupervisorAgent(self.settings, enable_critic=enable_critic)
        self.researcher = researcher or ResearcherAgent()
        self.analyst = analyst or AnalystAgent()
        self.writer = writer or WriterAgent()
        self.critic = critic or CriticAgent(self.settings)
        self.compiled_graph: Any = None

    def _route_from_supervisor(self, state: ResearchState) -> str:
        """Inspect the most recent route decision from the supervisor."""
        if state.route_history:
            last_route = state.route_history[-1]
            if last_route in {"researcher", "analyst", "writer", "critic", "done"}:
                return last_route
        return "done"

    def build(self) -> Any:
        """Create and compile the LangGraph workflow."""
        builder = StateGraph(ResearchState)

        # Add agent nodes
        builder.add_node("supervisor", self.supervisor.run)
        builder.add_node("researcher", self.researcher.run)
        builder.add_node("analyst", self.analyst.run)
        builder.add_node("writer", self.writer.run)
        if self.enable_critic:
            builder.add_node("critic", self.critic.run)

        # Entry point: start at supervisor
        builder.add_edge(START, "supervisor")

        # Supervisor conditional edge
        routes = {
            "researcher": "researcher",
            "analyst": "analyst",
            "writer": "writer",
            "done": END,
        }
        if self.enable_critic:
            routes["critic"] = "critic"

        builder.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            routes,
        )

        # Worker handoffs back to supervisor
        builder.add_edge("researcher", "supervisor")
        builder.add_edge("analyst", "supervisor")
        builder.add_edge("writer", "supervisor")
        if self.enable_critic:
            builder.add_edge("critic", "supervisor")

        self.compiled_graph = builder.compile()
        return self.compiled_graph

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return the final state."""
        if self.compiled_graph is None:
            self.build()

        result = self.compiled_graph.invoke(state)
        if isinstance(result, dict):
            return ResearchState.model_validate(result)
        if isinstance(result, ResearchState):
            return result
        raise ValueError(f"Unexpected graph output type: {type(result)}")
