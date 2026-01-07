"""Agent registry - in-memory store for agent instances."""

from datetime import datetime
from typing import Optional, Union
import uuid
from .models import (
    Agent, AgentState, AgentSource, ToolCall,
    Plan, PlanStep, StepLog, StepStatus, StepConfidence, WorkUnit,
    PlanStepInput, Run, Span, SpanKind, SpanStatus
)


class AgentRegistry:
    """In-memory registry for tracking agents, runs, and spans."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._work_units: dict[str, WorkUnit] = {}  # path -> WorkUnit
        self._runs: dict[str, Run] = {}  # run_id -> Run
        self._spans: dict[str, Span] = {}  # span_id -> Span
        self._spans_by_trace: dict[str, list[str]] = {}  # trace_id -> [span_ids]

    def register(
        self,
        task: str,
        name: Optional[str] = None,
        model: Optional[str] = None,
        source: Optional[str] = None,
        session_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        parent_agent_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Agent:
        """Register a new agent."""
        # Parse source
        agent_source = AgentSource.UNKNOWN
        if source:
            try:
                agent_source = AgentSource(source)
            except ValueError:
                pass

        # If this is a root agent (no parent), create a new run
        if not parent_agent_id:
            run = self._create_run(task)
            trace_id = run.trace_id
        elif trace_id is None and parent_agent_id:
            # Inherit trace_id from parent
            parent = self._agents.get(parent_agent_id)
            if parent:
                trace_id = parent.trace_id

        agent = Agent(
            task=task,
            name=name,
            model=model,
            source=agent_source,
            session_id=session_id,
            working_directory=working_directory,
            trace_id=trace_id,
            parent_agent_id=parent_agent_id,
        )

        # Create span for this agent
        if trace_id:
            parent_span_id = None
            if parent_agent_id:
                parent = self._agents.get(parent_agent_id)
                if parent:
                    parent_span_id = parent.span_id
            span = self._create_span(
                trace_id=trace_id,
                kind=SpanKind.AGENT,
                name=name or f"Agent {agent.id}",
                agent_id=agent.id,
                parent_id=parent_span_id,
            )
            agent.span_id = span.id

            # Update run with agent info
            run = self._runs.get(self._get_run_id_by_trace(trace_id))
            if run:
                run.agent_ids.append(agent.id)
                if not parent_agent_id:
                    run.root_agent_id = agent.id

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
        steps: list[Union[str, PlanStepInput, dict]],
    ) -> Optional[Plan]:
        """Set an agent's execution plan."""
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        plan_steps = []
        for i, step_data in enumerate(steps):
            if isinstance(step_data, str):
                # Simple string description
                plan_steps.append(PlanStep(index=i + 1, description=step_data))
            elif isinstance(step_data, dict):
                # Dictionary with extended fields
                confidence = None
                if step_data.get('confidence'):
                    try:
                        confidence = StepConfidence(step_data['confidence'])
                    except ValueError:
                        pass
                plan_steps.append(PlanStep(
                    index=i + 1,
                    description=step_data.get('description', ''),
                    owner=step_data.get('owner'),
                    resources=step_data.get('resources', []),
                    artifacts=step_data.get('artifacts', []),
                    reason=step_data.get('reason'),
                    confidence=confidence,
                    blocked_by=step_data.get('blocked_by', []),
                    can_parallel=step_data.get('can_parallel', False),
                ))
            elif isinstance(step_data, PlanStepInput):
                # PlanStepInput object
                confidence = None
                if step_data.confidence:
                    try:
                        confidence = StepConfidence(step_data.confidence)
                    except ValueError:
                        pass
                plan_steps.append(PlanStep(
                    index=i + 1,
                    description=step_data.description,
                    owner=step_data.owner,
                    resources=step_data.resources,
                    artifacts=step_data.artifacts,
                    reason=step_data.reason,
                    confidence=confidence,
                    blocked_by=step_data.blocked_by,
                    can_parallel=step_data.can_parallel,
                ))

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

    # =====================================
    # Run & Span Management (Tracing)
    # =====================================

    def _create_run(self, name: str) -> Run:
        """Create a new run (root trace)."""
        run = Run(name=name)
        self._runs[run.id] = run
        self._spans_by_trace[run.trace_id] = []
        return run

    def _get_run_id_by_trace(self, trace_id: str) -> Optional[str]:
        """Get run ID by trace ID."""
        for run_id, run in self._runs.items():
            if run.trace_id == trace_id:
                return run_id
        return None

    def _create_span(
        self,
        trace_id: str,
        kind: SpanKind,
        name: str,
        agent_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        step_index: Optional[int] = None,
        file_path: Optional[str] = None,
        operation: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> Span:
        """Create a new span in a trace."""
        span = Span(
            trace_id=trace_id,
            parent_id=parent_id,
            kind=kind,
            name=name,
            agent_id=agent_id,
            step_index=step_index,
            file_path=file_path,
            operation=operation,
            attributes=attributes or {},
        )
        self._spans[span.id] = span
        if trace_id in self._spans_by_trace:
            self._spans_by_trace[trace_id].append(span.id)

        # Update run stats
        run_id = self._get_run_id_by_trace(trace_id)
        if run_id:
            run = self._runs[run_id]
            run.total_spans += 1

        return span

    def end_span(
        self,
        span_id: str,
        status: SpanStatus = SpanStatus.COMPLETED,
        error_message: Optional[str] = None,
    ) -> Optional[Span]:
        """End a span with the given status."""
        span = self._spans.get(span_id)
        if not span:
            return None

        span.end_time = datetime.utcnow()
        span.status = status
        span.duration_ms = int((span.end_time - span.start_time).total_seconds() * 1000)
        if error_message:
            span.error_message = error_message

        # Update run stats
        run_id = self._get_run_id_by_trace(span.trace_id)
        if run_id:
            run = self._runs[run_id]
            if status == SpanStatus.COMPLETED:
                run.completed_spans += 1
            elif status == SpanStatus.FAILED:
                run.failed_spans += 1
            elif status == SpanStatus.BLOCKED:
                run.blocked_spans += 1

        return span

    def set_span_blocked(
        self,
        span_id: str,
        blocked_by_span_id: Optional[str] = None,
        blocked_by_resource: Optional[str] = None,
    ) -> Optional[Span]:
        """Mark a span as blocked."""
        span = self._spans.get(span_id)
        if not span:
            return None

        span.status = SpanStatus.BLOCKED
        span.blocked_by_span_id = blocked_by_span_id
        span.blocked_by_resource = blocked_by_resource
        return span

    def get_run(self, run_id: str) -> Optional[Run]:
        """Get a run by ID."""
        return self._runs.get(run_id)

    def get_run_by_trace(self, trace_id: str) -> Optional[Run]:
        """Get a run by trace ID."""
        run_id = self._get_run_id_by_trace(trace_id)
        if run_id:
            return self._runs.get(run_id)
        return None

    def list_runs(self) -> list[Run]:
        """List all runs, newest first."""
        return sorted(
            self._runs.values(),
            key=lambda r: r.start_time,
            reverse=True,
        )

    def get_spans_for_trace(self, trace_id: str) -> list[Span]:
        """Get all spans for a trace."""
        span_ids = self._spans_by_trace.get(trace_id, [])
        spans = [self._spans[sid] for sid in span_ids if sid in self._spans]
        return sorted(spans, key=lambda s: s.start_time)

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get a span by ID."""
        return self._spans.get(span_id)

    def end_run(
        self,
        run_id: str,
        status: SpanStatus = SpanStatus.COMPLETED,
    ) -> Optional[Run]:
        """End a run."""
        run = self._runs.get(run_id)
        if not run:
            return None

        run.end_time = datetime.utcnow()
        run.status = status
        run.duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)

        # Calculate max concurrency and collect files touched
        spans = self.get_spans_for_trace(run.trace_id)
        run.files_touched = list(set(
            s.file_path for s in spans if s.file_path
        ))

        # Calculate max concurrent spans at any point
        events = []
        for s in spans:
            events.append((s.start_time, 1))
            if s.end_time:
                events.append((s.end_time, -1))
        events.sort(key=lambda x: x[0])
        current = 0
        max_conc = 0
        for _, delta in events:
            current += delta
            max_conc = max(max_conc, current)
        run.max_concurrency = max_conc

        return run

    def create_tool_span(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: dict,
        step_index: Optional[int] = None,
    ) -> Optional[Span]:
        """Create a span for a tool call."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.trace_id:
            return None

        return self._create_span(
            trace_id=agent.trace_id,
            kind=SpanKind.TOOL,
            name=tool_name,
            agent_id=agent_id,
            parent_id=agent.span_id,
            step_index=step_index,
            attributes={"tool_input": tool_input},
        )

    def create_workspace_span(
        self,
        agent_id: str,
        file_path: str,
        operation: str,
        step_index: Optional[int] = None,
    ) -> Optional[Span]:
        """Create a span for a workspace mutation."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.trace_id:
            return None

        return self._create_span(
            trace_id=agent.trace_id,
            kind=SpanKind.WORKSPACE,
            name=f"{operation}: {file_path}",
            agent_id=agent_id,
            parent_id=agent.span_id,
            step_index=step_index,
            file_path=file_path,
            operation=operation,
        )

    def get_run_for_agent(self, agent_id: str) -> Optional[Run]:
        """Get the run that an agent belongs to."""
        agent = self._agents.get(agent_id)
        if not agent or not agent.trace_id:
            return None
        return self.get_run_by_trace(agent.trace_id)


# Global registry instance
registry = AgentRegistry()
