"""
Agent management API endpoints.

These endpoints allow agents to register themselves and send heartbeats.
In practice, these are called by the Claude Code hooks.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..models import AgentInfo, AgentType
from ..registry import WorkUnitRegistry


router = APIRouter(prefix="/agents", tags=["agents"])

# Registry instance will be set by main.py
_registry: WorkUnitRegistry | None = None


def set_registry(registry: WorkUnitRegistry) -> None:
    global _registry
    _registry = registry


def get_registry() -> WorkUnitRegistry:
    if _registry is None:
        raise HTTPException(status_code=500, detail="Registry not initialized")
    return _registry


# =============================================================================
# Request/Response Models
# =============================================================================


class RegisterAgentRequest(BaseModel):
    session_id: str
    agent_type: str = "main"
    task_tool_use_id: str | None = None
    parent_agent_id: str | None = None


class AgentResponse(BaseModel):
    agent_id: str
    session_id: str
    agent_type: str
    task_tool_use_id: str | None
    parent_agent_id: str | None
    registered_at: str
    last_seen: str


class HeartbeatResponse(BaseModel):
    success: bool
    agent_id: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/register", response_model=AgentResponse)
def register_agent(request: RegisterAgentRequest):
    """
    Register an agent with the system.

    For main agents, only session_id is required.
    For subagents, also provide task_tool_use_id and parent_agent_id.
    """
    registry = get_registry()

    if request.agent_type == "subagent":
        if not request.task_tool_use_id or not request.parent_agent_id:
            raise HTTPException(
                status_code=400,
                detail="Subagents require task_tool_use_id and parent_agent_id",
            )
        agent = AgentInfo.create_subagent(
            session_id=request.session_id,
            task_tool_use_id=request.task_tool_use_id,
            parent_agent_id=request.parent_agent_id,
        )
    else:
        agent = AgentInfo.create_main_agent(session_id=request.session_id)

    registered = registry.register_agent(agent)

    return AgentResponse(
        agent_id=registered.agent_id,
        session_id=registered.session_id,
        agent_type=registered.agent_type.value,
        task_tool_use_id=registered.task_tool_use_id,
        parent_agent_id=registered.parent_agent_id,
        registered_at=registered.registered_at.isoformat(),
        last_seen=registered.last_seen.isoformat(),
    )


@router.post("/{agent_id}/heartbeat", response_model=HeartbeatResponse)
def heartbeat(agent_id: str):
    """
    Send a heartbeat to keep an agent alive.

    Should be called periodically by hooks to prevent TTL expiration.
    """
    registry = get_registry()
    success = registry.heartbeat(agent_id)

    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    return HeartbeatResponse(success=True, agent_id=agent_id)


@router.get("", response_model=list[AgentResponse])
def list_agents():
    """Get all registered agents."""
    registry = get_registry()
    agents = registry.get_all_agents()

    return [
        AgentResponse(
            agent_id=a.agent_id,
            session_id=a.session_id,
            agent_type=a.agent_type.value,
            task_tool_use_id=a.task_tool_use_id,
            parent_agent_id=a.parent_agent_id,
            registered_at=a.registered_at.isoformat(),
            last_seen=a.last_seen.isoformat(),
        )
        for a in agents
    ]


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: str):
    """Get a specific agent by ID."""
    registry = get_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse(
        agent_id=agent.agent_id,
        session_id=agent.session_id,
        agent_type=agent.agent_type.value,
        task_tool_use_id=agent.task_tool_use_id,
        parent_agent_id=agent.parent_agent_id,
        registered_at=agent.registered_at.isoformat(),
        last_seen=agent.last_seen.isoformat(),
    )


@router.delete("/{agent_id}")
def remove_agent(agent_id: str):
    """
    Remove an agent from the system.

    This releases all their work units and removes them from queues.
    """
    registry = get_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    registry.remove_agent(agent_id)
    return {"success": True, "message": f"Agent {agent_id} removed"}
