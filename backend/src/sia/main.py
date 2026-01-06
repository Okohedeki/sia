"""Sia Control Plane - FastAPI Application."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

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
)
from .registry import registry

# Locate static files directory (bundled frontend)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Sia Control Plane",
    description="Runtime & Control Plane for Multi-Agent AI Execution",
    version="0.1.0",
)

# CORS configuration - allow connections from anywhere (agents run externally)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
