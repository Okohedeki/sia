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
