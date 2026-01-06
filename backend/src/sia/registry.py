"""Agent registry - in-memory store for agent instances."""

from datetime import datetime
from typing import Optional
from .models import (
    Agent, AgentState, AgentSource, ToolCall,
    Plan, PlanStep, StepLog, StepStatus, WorkUnit
)


class AgentRegistry:
    """In-memory registry for tracking agents."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._work_units: dict[str, WorkUnit] = {}  # path -> WorkUnit

    def register(
        self,
        task: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        source: Optional[str] = None,
        session_id: Optional[str] = None,
        working_directory: Optional[str] = None,
    ) -> Agent:
        """Register a new agent."""
        # Parse source
        agent_source = AgentSource.UNKNOWN
        if source:
            try:
                agent_source = AgentSource(source)
            except ValueError:
                pass

        agent = Agent(
            task=task,
            name=name,
            model=model,
            source=agent_source,
            session_id=session_id,
            working_directory=working_directory,
        )
        self._agents[agent.id] = agent
        return agent

    def get(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def remove(self, agent_id: str) -> bool:
        """Remove an agent by ID."""
        if agent_id in self._agents:
            # Also clean up work units
            self.clear_agent_work_units(agent_id)
            del self._agents[agent_id]
            return True
        return False

    def remove_by_session(self, session_id: str) -> bool:
        """Remove an agent by session ID."""
        agent_id = None
        for aid, agent in self._agents.items():
            if agent.session_id == session_id:
                agent_id = aid
                break
        if agent_id:
            return self.remove(agent_id)
        return False

    def touch(self, agent_id: str) -> None:
        """Update last_activity timestamp for an agent."""
        agent = self._agents.get(agent_id)
        if agent:
            agent.last_activity = datetime.utcnow()

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
        step_index: Optional[int] = None,
    ) -> Optional[ToolCall]:
        """Record a tool call for an agent."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        # Use current step index if not provided
        if step_index is None and agent.plan and agent.plan.current_step_index:
            step_index = agent.plan.current_step_index

        tool_call = ToolCall(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            duration_ms=duration_ms,
            step_index=step_index,
        )
        agent.tool_calls.append(tool_call)
        return tool_call

    # Plan management methods

    def set_plan(
        self,
        agent_id: str,
        steps: list[str],
    ) -> Optional[Plan]:
        """Set an agent's execution plan."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        plan_steps = [
            PlanStep(index=i + 1, description=desc)
            for i, desc in enumerate(steps)
        ]
        agent.plan = Plan(steps=plan_steps)
        return agent.plan

    def update_step(
        self,
        agent_id: str,
        step_index: int,
        status: str,
        files: Optional[list[str]] = None,
    ) -> Optional[PlanStep]:
        """Update a step's status and optionally its files."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.plan:
            return None

        # Find the step
        step = None
        for s in agent.plan.steps:
            if s.index == step_index:
                step = s
                break

        if not step:
            return None

        # Update status
        try:
            new_status = StepStatus(status)
        except ValueError:
            return None

        step.status = new_status

        # Track timing
        if new_status == StepStatus.IN_PROGRESS:
            step.started_at = datetime.utcnow()
            agent.plan.current_step_index = step_index
        elif new_status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
            step.completed_at = datetime.utcnow()
            # Auto-advance current_step_index if this was the current step
            if agent.plan.current_step_index == step_index:
                # Find next pending step
                next_step = None
                for s in agent.plan.steps:
                    if s.index > step_index and s.status == StepStatus.PENDING:
                        next_step = s
                        break
                agent.plan.current_step_index = next_step.index if next_step else None

        # Update files and track work units
        if files is not None:
            step.files = files
            # Register work units for files
            for file_path in files:
                self._add_work_unit(agent_id, file_path, step_index, "write")

        return step

    def add_step_log(
        self,
        agent_id: str,
        step_index: int,
        message: str,
        level: str = "info",
    ) -> Optional[StepLog]:
        """Add a log entry to a step."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.plan:
            return None

        # Find the step
        step = None
        for s in agent.plan.steps:
            if s.index == step_index:
                step = s
                break

        if not step:
            return None

        log = StepLog(message=message, level=level)
        step.logs.append(log)
        return log

    # Work unit management

    def _add_work_unit(
        self,
        agent_id: str,
        path: str,
        step_index: Optional[int],
        operation: str,
    ) -> WorkUnit:
        """Internal: Add or update a work unit."""
        # Normalize path
        normalized_path = path.replace("\\", "/")

        work_unit = WorkUnit(
            path=normalized_path,
            agent_id=agent_id,
            step_index=step_index,
            operation=operation,
        )
        self._work_units[normalized_path] = work_unit
        return work_unit

    def track_file_access(
        self,
        agent_id: str,
        path: str,
        operation: str,
    ) -> WorkUnit:
        """Track a file access from an agent."""
        agent = self._agents.get(agent_id)
        step_index = None
        if agent and agent.plan:
            step_index = agent.plan.current_step_index
        return self._add_work_unit(agent_id, path, step_index, operation)

    def remove_work_unit(self, path: str) -> bool:
        """Remove a work unit by path."""
        normalized_path = path.replace("\\", "/")
        if normalized_path in self._work_units:
            del self._work_units[normalized_path]
            return True
        return False

    def list_work_units(self) -> list[WorkUnit]:
        """List all active work units."""
        return list(self._work_units.values())

    def get_agent_work_units(self, agent_id: str) -> list[WorkUnit]:
        """Get work units for a specific agent."""
        return [wu for wu in self._work_units.values() if wu.agent_id == agent_id]

    def clear_agent_work_units(self, agent_id: str) -> int:
        """Clear all work units for an agent. Returns count removed."""
        to_remove = [path for path, wu in self._work_units.items() if wu.agent_id == agent_id]
        for path in to_remove:
            del self._work_units[path]
        return len(to_remove)


# Global registry instance
registry = AgentRegistry()
