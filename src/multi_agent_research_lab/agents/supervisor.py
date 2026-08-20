"""Supervisor / router implementation."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import AgentName
from multi_agent_research_lab.core.state import ResearchState


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self, settings: Settings | None = None, enable_critic: bool = True) -> None:
        self.settings = settings or get_settings()
        self.enable_critic = enable_critic

    def decide_next_route(self, state: ResearchState) -> str:
        """Evaluate current state and return the next agent name or 'done'."""
        # 1. Guardrail against infinite loops
        if state.iteration >= self.settings.max_iterations:
            return "done"

        # 2. Sequential routing policy based on missing state fields
        if not state.sources:
            return "researcher"
        if not state.analysis_notes:
            return "analyst"
        if not state.final_answer:
            return "writer"

        # 3. Critic inspection node (Bonus extension)
        if self.enable_critic:
            has_critic_run = any(res.agent == AgentName.CRITIC for res in state.agent_results)
            if not has_critic_run:
                return "critic"

        return "done"

    def run(self, state: ResearchState) -> ResearchState:
        """Update `state.route_history` with the next route."""
        next_route = self.decide_next_route(state)
        state.record_route(next_route)
        state.add_trace_event(
            "supervisor.route",
            {"next_route": next_route, "iteration": state.iteration},
        )
        return state
