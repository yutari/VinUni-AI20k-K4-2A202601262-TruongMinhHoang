"""Tests for Supervisor, Worker Agents, and Workflow execution."""

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.critic import CriticAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.schemas import (
    AgentName,
    AgentResult,
    ResearchQuery,
    SourceDocument,
)
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse
from multi_agent_research_lab.services.search_client import SearchClient


class DummySearchClient(SearchClient):
    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        return [
            SourceDocument(
                title="GraphRAG Paper",
                url="https://example.com/1",
                snippet="Snippet 1",
            ),
            SourceDocument(
                title="Multi-Agent Survey",
                url="https://example.com/2",
                snippet="Snippet 2",
            ),
        ][:max_results]


class DummyLLMClient(LLMClient):
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        return LLMResponse(
            content="Mock completion content citing [1] and [2].",
            input_tokens=50,
            output_tokens=100,
            cost_usd=0.0001,
        )


def test_supervisor_routes_sequentially() -> None:
    supervisor = SupervisorAgent(enable_critic=False)
    query = ResearchQuery(query="Explain multi-agent systems")

    # 1. Initially no sources -> route to researcher
    state = ResearchState(request=query)
    state = supervisor.run(state)
    assert state.route_history[-1] == "researcher"

    # 2. Has sources, no analysis -> route to analyst
    state.sources = [SourceDocument(title="Doc 1", snippet="Snippet 1")]
    state = supervisor.run(state)
    assert state.route_history[-1] == "analyst"

    # 3. Has analysis notes, no final answer -> route to writer
    state.analysis_notes = "Key analysis notes"
    state = supervisor.run(state)
    assert state.route_history[-1] == "writer"

    # 4. Has final answer and enable_critic=False -> route to done
    state.final_answer = "Final answer summary"
    state = supervisor.run(state)
    assert state.route_history[-1] == "done"


def test_supervisor_routes_with_critic() -> None:
    supervisor = SupervisorAgent(enable_critic=True)
    query = ResearchQuery(query="Explain multi-agent systems")
    state = ResearchState(request=query)
    state.sources = [SourceDocument(title="Doc 1", snippet="Snippet 1")]
    state.analysis_notes = "Key analysis notes"
    state.final_answer = "Final answer summary"

    # Route should be critic when enable_critic is True and critic has not run
    state = supervisor.run(state)
    assert state.route_history[-1] == "critic"

    # After critic has recorded result -> route to done
    state.agent_results.append(
        AgentResult(agent=AgentName.CRITIC, content="Audit Passed", metadata={})
    )
    state = supervisor.run(state)
    assert state.route_history[-1] == "done"


def test_supervisor_max_iterations_guardrail() -> None:
    settings = Settings(max_iterations=3)
    supervisor = SupervisorAgent(settings=settings)
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    state.iteration = 3
    state = supervisor.run(state)
    assert state.route_history[-1] == "done"


def test_researcher_agent() -> None:
    agent = ResearcherAgent(search_client=DummySearchClient())
    state = ResearchState(request=ResearchQuery(query="GraphRAG overview"))
    state = agent.run(state)
    assert len(state.sources) == 2
    assert state.research_notes is not None
    assert "GraphRAG Paper" in state.research_notes
    assert state.agent_results[-1].agent == AgentName.RESEARCHER


def test_analyst_agent() -> None:
    agent = AnalystAgent(llm=DummyLLMClient())
    state = ResearchState(request=ResearchQuery(query="GraphRAG overview"))
    state.research_notes = "Some research notes"
    state = agent.run(state)
    assert state.analysis_notes is not None
    assert "Mock completion" in state.analysis_notes
    assert state.agent_results[-1].agent == AgentName.ANALYST


def test_writer_agent() -> None:
    agent = WriterAgent(llm=DummyLLMClient())
    state = ResearchState(request=ResearchQuery(query="GraphRAG overview"))
    state.research_notes = "Some research notes"
    state.analysis_notes = "Some analysis notes"
    state = agent.run(state)
    assert state.final_answer is not None
    assert "[1]" in state.final_answer
    assert state.agent_results[-1].agent == AgentName.WRITER


def test_critic_agent() -> None:
    agent = CriticAgent()
    state = ResearchState(request=ResearchQuery(query="GraphRAG overview"))
    state.sources = [SourceDocument(title="Doc 1", snippet="Snippet 1")]
    state.final_answer = "This report cites [1] directly."
    state = agent.run(state)
    assert state.agent_results[-1].agent == AgentName.CRITIC
    assert "100%" in state.agent_results[-1].content
    assert state.agent_results[-1].metadata.get("audit_status") == "PASSED"


def test_workflow_end_to_end_mocked() -> None:
    search = DummySearchClient()
    llm = DummyLLMClient()
    workflow = MultiAgentWorkflow(
        supervisor=SupervisorAgent(enable_critic=False),
        researcher=ResearcherAgent(search_client=search),
        analyst=AnalystAgent(llm=llm),
        writer=WriterAgent(llm=llm),
        enable_critic=False,
    )
    init_state = ResearchState(request=ResearchQuery(query="End to end test"))
    final_state = workflow.run(init_state)

    assert final_state.final_answer is not None
    assert final_state.route_history == ["researcher", "analyst", "writer", "done"]
    assert len(final_state.sources) == 2
    assert final_state.analysis_notes is not None


def test_workflow_end_to_end_with_critic_mocked() -> None:
    search = DummySearchClient()
    llm = DummyLLMClient()
    workflow = MultiAgentWorkflow(
        researcher=ResearcherAgent(search_client=search),
        analyst=AnalystAgent(llm=llm),
        writer=WriterAgent(llm=llm),
        critic=CriticAgent(),
        enable_critic=True,
    )
    init_state = ResearchState(request=ResearchQuery(query="End to end test with critic"))
    final_state = workflow.run(init_state)

    assert final_state.final_answer is not None
    assert final_state.route_history == ["researcher", "analyst", "writer", "critic", "done"]
    assert len(final_state.sources) == 2
    assert any(res.agent == AgentName.CRITIC for res in final_state.agent_results)
