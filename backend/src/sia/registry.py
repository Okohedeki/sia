"""Agent registry - in-memory store for agent instances."""

from datetime import datetime
from typing import Optional
from .models import Agent, AgentState, AgentSource, ToolCall


class AgentRegistry:
    """In-memory registry for tracking agents."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}

    def register(
        self,
        task: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Agent:
        """Register a new agent."""
        # Parse source
        agent_source = AgentSource.UNKNOWN
        if source:
            try:
                agent_source = AgentSource(source)
            except ValueError:
                pass

        agent = Agent(task=task, name=name, model=model, source=agent_source)
        self._agents[agent.id] = agent
        return agent

    def get(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def list_all(self) -> list[Agent]:
        """List all agents, newest first."""
        return sorted(
            self._agents.values(),
            key=lambda a: a.created_at,
            reverse=True,
        )

    def update_state(
        self,
        agent_id: str,
        state: str,
        response: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[Agent]:
        """Update an agent's state."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        try:
            agent.state = AgentState(state)
        except ValueError:
            return None

        if agent.state == AgentState.RUNNING:
            agent.started_at = datetime.utcnow()
        elif agent.state in (AgentState.COMPLETED, AgentState.FAILED):
            agent.completed_at = datetime.utcnow()

        if response is not None:
            agent.response = response
        if error is not None:
            agent.error = error

        return agent

    def add_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: dict,
        tool_output: str,
        duration_ms: int,
    ) -> Optional[ToolCall]:
        """Record a tool call for an agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        tool_call = ToolCall(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            duration_ms=duration_ms,
        )
        agent.tool_calls.append(tool_call)
        return tool_call


# Global registry instance
registry = AgentRegistry()
