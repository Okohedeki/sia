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
    AgentResponse,
    ToolCallResponse,
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
    )
    if not tool_call:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ToolCallResponse(**tool_call.model_dump())


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
        return FileResponse(index_file)
    return {"message": "Sia Control Plane API", "docs": "/docs"}


# Mount static assets (JS, CSS, etc.)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
