"""Sia Control Plane - FastAPI Application."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from typing import Any, Optional
from .models import (
    RegisterAgentRequest,
    UpdateStateRequest,
    ReportToolCallRequest,
    SetPlanRequest,
    UpdateStepRequest,
    AddStepLogRequest,
    AgentResponse,
    ToolCallResponse,
    PlanResponse,
    PlanStepResponse,
    StepLogResponse,
    WorkUnitResponse,
    AgentSource,
    SpanResponse,
    RunResponse,
    RunWithSpansResponse,
    TimelineResponse,
    TimelineEvent,
    PlanComparisonResponse,
    PlanDivergence,
    SpanKind,
    SpanStatus,
    AgentGraphNode,
    AgentGraphEdge,
    AgentGraphMetrics,
    AgentGraphResponse,
    GraphEdgeType,
    AgentState,
    WorkspaceNode,
    WorkspaceEdge,
    WorkspaceConflict,
    WorkspaceMapMetrics,
    WorkspaceMapResponse,
    WorkspaceNodeType,
    WorkspaceEdgeType,
)
from .registry import registry
from pydantic import BaseModel


class HookPayload(BaseModel):
    """Payload from Claude Code hooks."""
    hook_type: str = "unknown"
    tool_name: str = ""
    tool_input: dict[str, Any] = {}
    tool_output: str = ""
    session_id: str = ""
    working_directory: str = ""
    tool_data: str = ""  # Raw tool data from hook script


# Track session_id -> agent_id mapping
_session_agents: dict[str, str] = {}

# Locate static files directory (bundled frontend)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Sia Control Plane",
    description="Runtime & Control Plane for Multi-Agent AI Execution",
    version="0.1.0",
)

# Enable logging for debugging
import logging
import asyncio
from datetime import datetime, timedelta
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sia")

# Stale session timeout (seconds) - agents with no activity for this long are removed
STALE_SESSION_TIMEOUT = 60

# CORS configuration - allow connections from anywhere (agents run externally)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def cleanup_stale_sessions():
    """Background task to remove inactive agents."""
    while True:
        await asyncio.sleep(10)  # Check every 10 seconds
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=STALE_SESSION_TIMEOUT)
            agents = registry.list_all()
            for agent in agents:
                if agent.source.value == "hooks" and agent.last_activity < cutoff:
                    # Remove stale agent
                    session_to_remove = None
                    for sid, aid in list(_session_agents.items()):
                        if aid == agent.id:
                            session_to_remove = sid
                            break
                    if session_to_remove:
                        del _session_agents[session_to_remove]
                    registry.remove(agent.id)
                    logger.info(f"[Cleanup] Removed stale agent {agent.name} (inactive for {STALE_SESSION_TIMEOUT}s)")
        except Exception as e:
            logger.error(f"[Cleanup] Error: {e}")


@app.on_event("startup")
async def startup_event():
    """Start background tasks on server startup."""
    asyncio.create_task(cleanup_stale_sessions())


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "sia-control-plane"}


# Agent API - used by SiaAgent instances to report their activity

@app.post("/api/agents/register", response_model=AgentResponse)
async def register_agent(request: RegisterAgentRequest):
    """Register a new agent with the control plane."""
    agent = registry.register(
        task=request.task,
        name=request.name,
        model=request.model,
        source=request.source,
    )
    return AgentResponse(**agent.model_dump())


@app.post("/api/agents/{agent_id}/state", response_model=AgentResponse)
async def update_agent_state(agent_id: str, request: UpdateStateRequest):
    """Update an agent's state."""
    agent = registry.update_state(
        agent_id=agent_id,
        state=request.state,
        response=request.response,
        error=request.error,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(**agent.model_dump())


@app.post("/api/agents/{agent_id}/tools", response_model=ToolCallResponse)
async def report_tool_call(agent_id: str, request: ReportToolCallRequest):
    """Report a tool execution."""
    tool_call = registry.add_tool_call(
        agent_id=agent_id,
        tool_name=request.tool_name,
        tool_input=request.tool_input,
        tool_output=request.tool_output,
        duration_ms=request.duration_ms,
        step_index=request.step_index,
    )
    if not tool_call:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ToolCallResponse(**tool_call.model_dump())


# Plan API - manage agent plans

@app.post("/api/agents/{agent_id}/plan", response_model=PlanResponse)
async def set_agent_plan(agent_id: str, request: SetPlanRequest):
    """Set an agent's execution plan."""
    plan = registry.set_plan(agent_id=agent_id, steps=request.steps)
    if not plan:
        raise HTTPException(status_code=404, detail="Agent not found")
    return PlanResponse(
        steps=[PlanStepResponse(
            id=s.id,
            index=s.index,
            description=s.description,
            status=s.status,
            files=s.files,
            logs=[StepLogResponse(**log.model_dump()) for log in s.logs],
            started_at=s.started_at,
            completed_at=s.completed_at,
            owner=s.owner,
            resources=s.resources,
            artifacts=s.artifacts,
            reason=s.reason,
            confidence=s.confidence,
            blocked_by=s.blocked_by,
            can_parallel=s.can_parallel,
        ) for s in plan.steps],
        current_step_index=plan.current_step_index,
        created_at=plan.created_at,
    )


@app.post("/api/agents/{agent_id}/steps/{step_index}/status", response_model=PlanStepResponse)
async def update_step_status(agent_id: str, step_index: int, request: UpdateStepRequest):
    """Update a step's status and optionally its files."""
    step = registry.update_step(
        agent_id=agent_id,
        step_index=step_index,
        status=request.status,
        files=request.files,
    )
    if not step:
        raise HTTPException(status_code=404, detail="Agent or step not found")
    return PlanStepResponse(
        id=step.id,
        index=step.index,
        description=step.description,
        status=step.status,
        files=step.files,
        logs=[StepLogResponse(**log.model_dump()) for log in step.logs],
        started_at=step.started_at,
        completed_at=step.completed_at,
        owner=step.owner,
        resources=step.resources,
        artifacts=step.artifacts,
        reason=step.reason,
        confidence=step.confidence,
        blocked_by=step.blocked_by,
        can_parallel=step.can_parallel,
    )


@app.post("/api/agents/{agent_id}/steps/{step_index}/logs", response_model=StepLogResponse)
async def add_step_log(agent_id: str, step_index: int, request: AddStepLogRequest):
    """Add a log entry to a step."""
    log = registry.add_step_log(
        agent_id=agent_id,
        step_index=step_index,
        message=request.message,
        level=request.level,
    )
    if not log:
        raise HTTPException(status_code=404, detail="Agent or step not found")
    return StepLogResponse(**log.model_dump())


# Work Units API - track resources being worked on

@app.get("/api/work-units", response_model=list[WorkUnitResponse])
async def list_work_units():
    """List all active work units across all agents."""
    work_units = registry.list_work_units()
    return [WorkUnitResponse(**wu.model_dump()) for wu in work_units]


@app.get("/api/agents/{agent_id}/work-units", response_model=list[WorkUnitResponse])
async def get_agent_work_units(agent_id: str):
    """Get work units for a specific agent."""
    work_units = registry.get_agent_work_units(agent_id)
    return [WorkUnitResponse(**wu.model_dump()) for wu in work_units]


# Hooks API - receives automatic reports from Claude Code hooks

@app.post("/api/hooks/tool-use")
async def hook_tool_use(payload: HookPayload):
    """Handle tool use reports from Claude Code hooks."""
    import json as json_module

    session_id = payload.session_id or "default"

    # Parse tool_data from hook script
    tool_name = payload.tool_name
    tool_input = payload.tool_input
    tool_output = payload.tool_output

    if payload.tool_data:
        try:
            data = json_module.loads(payload.tool_data)
            tool_name = data.get("tool_name") or data.get("tool") or data.get("name") or tool_name
            tool_input = data.get("tool_input") or data.get("input") or tool_input or {}
            tool_output = str(data.get("tool_output") or data.get("output") or tool_output or "")
        except (json_module.JSONDecodeError, TypeError):
            tool_output = payload.tool_data[:500] if not tool_output else tool_output

    if not tool_name:
        logger.warning(f"[Hook] No tool name - raw data: {payload.tool_data[:100] if payload.tool_data else 'empty'}")
        return {"status": "skipped", "reason": "no tool name"}

    logger.info(f"[Hook] {tool_name} | session={session_id[:8]}...")

    # Get or create agent for this session
    if session_id not in _session_agents:
        # Auto-register agent for this session
        working_dir = payload.working_directory or ""
        dir_name = "unknown"
        if working_dir:
            parts = working_dir.replace("\\", "/").split("/")
            dir_name = parts[-1] if parts else "unknown"
        task = f"Session in {dir_name}"
        agent_name = f"claude-{session_id[:8]}" if session_id != "default" else "claude-session"
        agent = registry.register(
            task=task,
            name=agent_name,
            model="claude-code",
            source="hooks",
            session_id=session_id,
            working_directory=working_dir,
        )
        _session_agents[session_id] = agent.id
        registry.update_state(agent.id, "running")
        logger.info(f"[Agent Connected] {agent_name} | dir={dir_name} | id={agent.id}")

    agent_id = _session_agents[session_id]

    # Update last activity
    registry.touch(agent_id)

    # Handle TodoWrite specially - extract plan
    if tool_name == "TodoWrite":
        todos = tool_input.get("todos", [])
        if todos:
            steps = [t.get("content", "") for t in todos if t.get("content")]
            if steps:
                registry.set_plan(agent_id, steps)
                # Update step statuses based on todo statuses
                for i, todo in enumerate(todos, 1):
                    status = todo.get("status", "pending")
                    if status == "in_progress":
                        registry.update_step(agent_id, i, "in_progress")
                    elif status == "completed":
                        registry.update_step(agent_id, i, "completed")

    # Track file operations as work units
    file_path = None
    operation = "unknown"

    if tool_name in ("Read", "read_file", "sia_read_file"):
        file_path = tool_input.get("file_path") or tool_input.get("path")
        operation = "read"
    elif tool_name in ("Write", "write_file", "sia_write_file"):
        file_path = tool_input.get("file_path") or tool_input.get("path")
        operation = "write"
    elif tool_name in ("Edit", "edit_file"):
        file_path = tool_input.get("file_path")
        operation = "write"
    elif tool_name in ("Bash", "bash", "sia_run_command"):
        operation = "execute"

    if file_path:
        registry.track_file_access(agent_id, file_path, operation)

    # Record the tool call
    registry.add_tool_call(
        agent_id=agent_id,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output[:1000] if tool_output else "",  # Truncate long outputs
        duration_ms=0,  # Hooks don't have timing info
    )

    return {"status": "ok", "agent_id": agent_id}


# UI API - used by the frontend to observe agents

@app.get("/api/agents", response_model=list[AgentResponse])
async def list_agents():
    """List all registered agents."""
    agents = registry.list_all()
    return [AgentResponse(**a.model_dump()) for a in agents]


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get a specific agent by ID."""
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(**agent.model_dump())


@app.delete("/api/agents/{agent_id}")
async def remove_agent(agent_id: str):
    """Remove an agent by ID."""
    # Also remove from session mapping
    session_to_remove = None
    for sid, aid in _session_agents.items():
        if aid == agent_id:
            session_to_remove = sid
            break
    if session_to_remove:
        del _session_agents[session_to_remove]

    if registry.remove(agent_id):
        logger.info(f"[Agent Removed] id={agent_id}")
        return {"status": "ok", "agent_id": agent_id}
    raise HTTPException(status_code=404, detail="Agent not found")


@app.delete("/api/sessions/{session_id}")
async def remove_session(session_id: str):
    """Remove an agent by session ID."""
    if session_id in _session_agents:
        agent_id = _session_agents[session_id]
        del _session_agents[session_id]
        registry.remove(agent_id)
        logger.info(f"[Session Removed] session={session_id[:8]}... agent={agent_id}")
        return {"status": "ok", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session not found")


# =====================================
# Tracing API - Runs and Spans
# =====================================

def _span_to_response(span, children: list = None) -> SpanResponse:
    """Convert a Span model to SpanResponse."""
    return SpanResponse(
        id=span.id,
        trace_id=span.trace_id,
        parent_id=span.parent_id,
        kind=span.kind,
        name=span.name,
        status=span.status,
        start_time=span.start_time,
        end_time=span.end_time,
        duration_ms=span.duration_ms,
        agent_id=span.agent_id,
        step_index=span.step_index,
        blocked_by_span_id=span.blocked_by_span_id,
        blocked_by_resource=span.blocked_by_resource,
        blocked_duration_ms=span.blocked_duration_ms,
        attributes=span.attributes,
        error_message=span.error_message,
        file_path=span.file_path,
        operation=span.operation,
        children=children or [],
    )


def _run_to_response(run) -> RunResponse:
    """Convert a Run model to RunResponse."""
    return RunResponse(
        id=run.id,
        trace_id=run.trace_id,
        name=run.name,
        status=run.status,
        start_time=run.start_time,
        end_time=run.end_time,
        duration_ms=run.duration_ms,
        root_agent_id=run.root_agent_id,
        agent_ids=run.agent_ids,
        total_spans=run.total_spans,
        completed_spans=run.completed_spans,
        failed_spans=run.failed_spans,
        blocked_spans=run.blocked_spans,
        max_concurrency=run.max_concurrency,
        files_touched=run.files_touched,
        planned_steps=run.planned_steps,
        executed_steps=run.executed_steps,
    )


def _build_span_tree(spans: list, parent_id: str = None) -> list[SpanResponse]:
    """Build a tree structure from flat span list."""
    children = []
    for span in spans:
        if span.parent_id == parent_id:
            child_response = _span_to_response(
                span,
                children=_build_span_tree(spans, span.id)
            )
            children.append(child_response)
    return children


@app.get("/api/runs", response_model=list[RunResponse])
async def list_runs():
    """List all runs, newest first."""
    runs = registry.list_runs()
    return [_run_to_response(r) for r in runs]


@app.get("/api/runs/{run_id}", response_model=RunWithSpansResponse)
async def get_run(run_id: str):
    """Get a run with all its spans."""
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    spans = registry.get_spans_for_trace(run.trace_id)
    flat_spans = [_span_to_response(s) for s in spans]

    # Build tree structure
    root_span = None
    tree_spans = _build_span_tree(spans, None)
    if tree_spans:
        root_span = tree_spans[0]

    return RunWithSpansResponse(
        run=_run_to_response(run),
        spans=flat_spans,
        root_span=root_span,
    )


@app.get("/api/runs/{run_id}/timeline", response_model=TimelineResponse)
async def get_run_timeline(run_id: str):
    """Get timeline events for a run."""
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    spans = registry.get_spans_for_trace(run.trace_id)
    events = []

    for span in spans:
        # Start event
        events.append(TimelineEvent(
            timestamp=span.start_time,
            event_type="span_start",
            span_id=span.id,
            agent_id=span.agent_id,
            name=span.name,
            status=span.status,
            duration_ms=span.duration_ms,
        ))
        # End event
        if span.end_time:
            events.append(TimelineEvent(
                timestamp=span.end_time,
                event_type="span_end",
                span_id=span.id,
                agent_id=span.agent_id,
                name=span.name,
                status=span.status,
                duration_ms=span.duration_ms,
            ))
        # Blocked event
        if span.status == SpanStatus.BLOCKED:
            events.append(TimelineEvent(
                timestamp=span.start_time,
                event_type="blocked",
                span_id=span.id,
                agent_id=span.agent_id,
                name=f"Blocked: {span.blocked_by_resource or 'unknown'}",
                status=span.status,
                duration_ms=span.blocked_duration_ms,
            ))
        # Error event
        if span.status == SpanStatus.FAILED:
            events.append(TimelineEvent(
                timestamp=span.end_time or span.start_time,
                event_type="error",
                span_id=span.id,
                agent_id=span.agent_id,
                name=span.error_message or "Error",
                status=span.status,
                duration_ms=span.duration_ms,
            ))

    # Sort by timestamp
    events.sort(key=lambda e: e.timestamp)

    # Get unique agent IDs
    agent_ids = list(set(e.agent_id for e in events if e.agent_id))

    return TimelineResponse(
        start_time=run.start_time,
        end_time=run.end_time,
        events=events,
        agents=agent_ids,
    )


@app.get("/api/runs/{run_id}/plan-comparison", response_model=PlanComparisonResponse)
async def get_plan_comparison(run_id: str):
    """Get plan vs execution comparison for a run."""
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get the root agent's plan
    if not run.root_agent_id:
        return PlanComparisonResponse(
            planned_steps=[],
            executed_steps=[],
            divergences=[],
            has_divergence=False,
        )

    agent = registry.get(run.root_agent_id)
    if not agent or not agent.plan:
        return PlanComparisonResponse(
            planned_steps=[],
            executed_steps=[],
            divergences=[],
            has_divergence=False,
        )

    planned = [s.description for s in agent.plan.steps]
    executed = [s.description for s in agent.plan.steps if s.status in ("completed", "in_progress")]

    # Calculate divergences
    divergences = []
    planned_set = set(planned)
    executed_set = set(executed)

    for i, step in enumerate(planned):
        if step in executed_set:
            exec_idx = executed.index(step) if step in executed else None
            if exec_idx != i:
                divergences.append(PlanDivergence(
                    step_description=step,
                    planned_index=i,
                    executed_index=exec_idx,
                    status="reordered"
                ))
            else:
                divergences.append(PlanDivergence(
                    step_description=step,
                    planned_index=i,
                    executed_index=exec_idx,
                    status="executed"
                ))
        else:
            divergences.append(PlanDivergence(
                step_description=step,
                planned_index=i,
                executed_index=None,
                status="skipped"
            ))

    # Check for inserted steps
    for i, step in enumerate(executed):
        if step not in planned_set:
            divergences.append(PlanDivergence(
                step_description=step,
                planned_index=None,
                executed_index=i,
                status="inserted"
            ))

    has_divergence = any(d.status != "executed" for d in divergences)

    return PlanComparisonResponse(
        planned_steps=planned,
        executed_steps=executed,
        divergences=divergences,
        has_divergence=has_divergence,
    )


@app.get("/api/spans/{span_id}", response_model=SpanResponse)
async def get_span(span_id: str):
    """Get a span by ID."""
    span = registry.get_span(span_id)
    if not span:
        raise HTTPException(status_code=404, detail="Span not found")
    return _span_to_response(span)


@app.get("/api/runs/{run_id}/agent-graph", response_model=AgentGraphResponse)
async def get_agent_graph(run_id: str):
    """Get agent interaction graph for a run."""
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    nodes = []
    edges = []
    depth_map: dict[str, int] = {}  # agent_id -> depth
    children_count: dict[str, int] = {}  # agent_id -> child count
    blocking_agents: set[str] = set()

    # Build nodes from agents in this run
    for agent_id in run.agent_ids:
        agent = registry.get(agent_id)
        if not agent:
            continue

        # Calculate depth
        depth = 0
        parent_id = agent.parent_agent_id
        while parent_id:
            depth += 1
            parent = registry.get(parent_id)
            if parent:
                parent_id = parent.parent_agent_id
            else:
                break
        depth_map[agent_id] = depth

        # Track children count for parent
        if agent.parent_agent_id:
            children_count[agent.parent_agent_id] = children_count.get(agent.parent_agent_id, 0) + 1

        # Calculate duration
        duration_ms = None
        if agent.started_at and agent.completed_at:
            duration_ms = int((agent.completed_at - agent.started_at).total_seconds() * 1000)

        node = AgentGraphNode(
            id=agent.id,
            name=agent.name or f"Agent {agent.id}",
            state=agent.state,
            source=agent.source,
            is_root=(agent.id == run.root_agent_id),
            depth=depth,
            tool_calls_count=len(agent.tool_calls),
            duration_ms=duration_ms,
            started_at=agent.started_at,
            completed_at=agent.completed_at,
            error_message=agent.error,
        )
        nodes.append(node)

        # Create spawn edge from parent to this agent
        if agent.parent_agent_id and agent.parent_agent_id in run.agent_ids:
            edge = AgentGraphEdge(
                source_id=agent.parent_agent_id,
                target_id=agent.id,
                edge_type=GraphEdgeType.SPAWN,
                timestamp=agent.created_at,
                label="spawned",
            )
            edges.append(edge)

    # Check for blocking relationships from spans
    spans = registry.get_spans_for_trace(run.trace_id)
    for span in spans:
        if span.blocked_by_span_id:
            blocker_span = registry.get_span(span.blocked_by_span_id)
            if blocker_span and blocker_span.agent_id and span.agent_id:
                # Add blocking edge
                edge = AgentGraphEdge(
                    source_id=blocker_span.agent_id,
                    target_id=span.agent_id,
                    edge_type=GraphEdgeType.BLOCKING,
                    timestamp=span.start_time,
                    label=span.blocked_by_resource or "blocking",
                )
                edges.append(edge)
                blocking_agents.add(blocker_span.agent_id)

    # Calculate metrics
    max_depth = max(depth_map.values()) if depth_map else 0
    fan_out = max(children_count.values()) if children_count else 0
    failed_agents = sum(1 for n in nodes if n.state == AgentState.FAILED)
    blocked_agents = sum(1 for s in spans if s.status == SpanStatus.BLOCKED and s.agent_id)

    metrics = AgentGraphMetrics(
        total_agents=len(nodes),
        max_depth=max_depth,
        fan_out=fan_out,
        failed_agents=failed_agents,
        blocked_agents=blocked_agents,
        bottleneck_agents=list(blocking_agents),
    )

    return AgentGraphResponse(
        nodes=nodes,
        edges=edges,
        metrics=metrics,
        root_agent_id=run.root_agent_id,
    )


@app.get("/api/runs/{run_id}/workspace-map", response_model=WorkspaceMapResponse)
async def get_workspace_map(run_id: str):
    """Get workspace impact map for a run."""
    run = registry.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    nodes: list[WorkspaceNode] = []
    edges: list[WorkspaceEdge] = []
    conflicts: list[WorkspaceConflict] = []

    # Track file -> agents mapping
    file_agents: dict[str, set[str]] = {}  # path -> set of agent_ids
    file_operations: dict[str, set[str]] = {}  # path -> set of operations
    file_node_ids: dict[str, str] = {}  # path -> node_id
    agent_file_count: dict[str, int] = {}  # agent_id -> file count

    # Get spans with file operations
    spans = registry.get_spans_for_trace(run.trace_id)

    for span in spans:
        if span.file_path and span.agent_id:
            path = span.file_path.replace("\\", "/")
            operation = span.operation or "modify"

            # Track agent-file relationships
            if path not in file_agents:
                file_agents[path] = set()
                file_operations[path] = set()
            file_agents[path].add(span.agent_id)
            file_operations[path].add(operation)

            # Track agent activity
            agent_file_count[span.agent_id] = agent_file_count.get(span.agent_id, 0) + 1

    # Also check work units
    for agent_id in run.agent_ids:
        work_units = registry.get_agent_work_units(agent_id)
        for wu in work_units:
            path = wu.path.replace("\\", "/")
            if path not in file_agents:
                file_agents[path] = set()
                file_operations[path] = set()
            file_agents[path].add(agent_id)
            file_operations[path].add(wu.operation)
            agent_file_count[agent_id] = agent_file_count.get(agent_id, 0) + 1

    # Create file nodes
    for path, agent_ids in file_agents.items():
        file_name = path.split("/")[-1] if "/" in path else path
        node_id = f"file-{hash(path) % 10000:04d}"
        file_node_ids[path] = node_id

        operations = file_operations.get(path, set())
        read_count = 1 if "read" in operations else 0
        write_count = 1 if "write" in operations or "modify" in operations else 0

        node = WorkspaceNode(
            id=node_id,
            node_type=WorkspaceNodeType.FILE,
            name=file_name,
            path=path,
            read_count=read_count,
            write_count=write_count,
            touched_by=list(agent_ids),
        )
        nodes.append(node)

        # Create conflict if multiple agents touched this file
        if len(agent_ids) > 1:
            conflict = WorkspaceConflict(
                file_path=path,
                file_id=node_id,
                agents=list(agent_ids),
                operations=list(operations),
            )
            conflicts.append(conflict)

    # Create agent nodes and edges
    for agent_id in run.agent_ids:
        agent = registry.get(agent_id)
        if not agent:
            continue

        agent_node = WorkspaceNode(
            id=f"agent-{agent_id}",
            node_type=WorkspaceNodeType.AGENT,
            name=agent.name or f"Agent {agent_id}",
            agent_id=agent_id,
        )
        nodes.append(agent_node)

        # Create edges for this agent's file operations
        for span in spans:
            if span.agent_id == agent_id and span.file_path:
                path = span.file_path.replace("\\", "/")
                if path in file_node_ids:
                    operation = span.operation or "modify"
                    edge_type = WorkspaceEdgeType.READ if operation == "read" else WorkspaceEdgeType.WRITE

                    edge = WorkspaceEdge(
                        source_id=f"agent-{agent_id}",
                        target_id=file_node_ids[path],
                        edge_type=edge_type,
                        timestamp=span.start_time,
                        step_index=span.step_index,
                    )
                    edges.append(edge)

    # Calculate metrics
    most_touched_file = None
    max_touches = 0
    for path, agent_ids in file_agents.items():
        if len(agent_ids) > max_touches:
            max_touches = len(agent_ids)
            most_touched_file = path

    most_active_agent = None
    max_files = 0
    for agent_id, count in agent_file_count.items():
        if count > max_files:
            max_files = count
            agent = registry.get(agent_id)
            most_active_agent = agent.name if agent and agent.name else agent_id

    metrics = WorkspaceMapMetrics(
        total_files=len(file_agents),
        total_agents=len(run.agent_ids),
        files_with_conflicts=len(conflicts),
        most_touched_file=most_touched_file,
        most_active_agent=most_active_agent,
    )

    return WorkspaceMapResponse(
        nodes=nodes,
        edges=edges,
        conflicts=conflicts,
        metrics=metrics,
    )


# Serve frontend static files
@app.get("/")
async def serve_root():
    """Serve the frontend UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return {"message": "Sia Control Plane API", "docs": "/docs"}


# Serve JS files with correct MIME type
@app.get("/assets/{filename:path}")
async def serve_assets(filename: str):
    """Serve static assets with correct MIME types."""
    file_path = STATIC_DIR / "assets" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")

    # Determine MIME type
    if filename.endswith(".js"):
        media_type = "application/javascript"
    elif filename.endswith(".css"):
        media_type = "text/css"
    elif filename.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(file_path, media_type=media_type)
