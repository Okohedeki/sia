"""
Work unit management API endpoints.

These are the core coordination endpoints that hooks call to:
- Claim work units (or join queue if busy)
- Release work units (promotes next in queue)
- Query global state (all agents can see everything)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..models import WorkUnitType
from ..registry import WorkUnitRegistry


router = APIRouter(prefix="/work-units", tags=["work-units"])

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


class ClaimRequest(BaseModel):
    agent_id: str
    path: str
    type: str = "file"  # file, directory, process
    ttl_seconds: int | None = None


class ReleaseRequest(BaseModel):
    agent_id: str
    path: str


class LeaveQueueRequest(BaseModel):
    agent_id: str
    path: str


class QueueEntryResponse(BaseModel):
    agent_id: str
    requested_at: str
    position: int


class WorkUnitResponse(BaseModel):
    id: str
    path: str
    type: str
    owner_agent_id: str | None
    claimed_at: str | None
    queue: list[QueueEntryResponse]
    status: str
    ttl_seconds: int
    expires_at: str | None


class ClaimResponse(BaseModel):
    success: bool
    work_unit: WorkUnitResponse
    queue_position: int | None = None
    owner_agent_id: str | None = None
    message: str


class StateResponse(BaseModel):
    agents: list[dict]
    work_units: list[WorkUnitResponse]


# =============================================================================
# Helper Functions
# =============================================================================


def work_unit_to_response(wu) -> WorkUnitResponse:
    """Convert WorkUnit to response model."""
    return WorkUnitResponse(
        id=wu.id,
        path=wu.path,
        type=wu.type.value,
        owner_agent_id=wu.owner_agent_id,
        claimed_at=wu.claimed_at.isoformat() if wu.claimed_at else None,
        queue=[
            QueueEntryResponse(
                agent_id=e.agent_id,
                requested_at=e.requested_at.isoformat(),
                position=i + 1,
            )
            for i, e in enumerate(wu.queue)
        ],
        status=wu.status.value,
        ttl_seconds=wu.ttl_seconds,
        expires_at=wu.expires_at.isoformat() if wu.expires_at else None,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/claim", response_model=ClaimResponse)
def claim_work_unit(request: ClaimRequest):
    """
    Attempt to claim a work unit.

    If unclaimed: grants ownership (success=true)
    If already owned by requester: refreshes TTL (success=true)
    If owned by another: adds to queue (success=false, queue_position set)

    This is the primary endpoint called by PreToolUse hooks.
    """
    registry = get_registry()

    try:
        work_unit_type = WorkUnitType(request.type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type: {request.type}. Must be file, directory, or process",
        )

    result = registry.claim(
        agent_id=request.agent_id,
        path=request.path,
        work_unit_type=work_unit_type,
        ttl_seconds=request.ttl_seconds,
    )

    return ClaimResponse(
        success=result.success,
        work_unit=work_unit_to_response(result.work_unit),
        queue_position=result.queue_position,
        owner_agent_id=result.owner_agent_id,
        message=result.message,
    )


@router.post("/release")
def release_work_unit(request: ReleaseRequest):
    """
    Release a work unit.

    If there are queued agents, the next one automatically gets ownership.
    If no one is waiting, the work unit becomes available.

    This is called by PostToolUse hooks after tool execution.
    """
    registry = get_registry()
    success = registry.release(request.agent_id, request.path)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot release: either path doesn't exist or agent doesn't own it",
        )

    return {"success": True, "message": f"Released {request.path}"}


@router.post("/leave-queue")
def leave_queue(request: LeaveQueueRequest):
    """
    Remove an agent from a work unit's queue.

    Use this when an agent no longer wants to wait for a resource.
    """
    registry = get_registry()
    success = registry.leave_queue(request.agent_id, request.path)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Agent not in queue for this path",
        )

    return {"success": True, "message": f"Left queue for {request.path}"}


@router.get("", response_model=list[WorkUnitResponse])
def list_work_units():
    """
    Get ALL work units in the system.

    This provides global visibility - every agent can see what everyone
    else is working on. Essential for coordination.
    """
    registry = get_registry()
    work_units = registry.get_all_work_units()

    return [work_unit_to_response(wu) for wu in work_units]


@router.get("/state", response_model=StateResponse)
def get_state():
    """
    Get full system state (agents + work units).

    Primarily for UI consumption to render the full picture.
    """
    registry = get_registry()
    state = registry.get_state()

    return StateResponse(
        agents=state["agents"],
        work_units=[
            work_unit_to_response(
                registry.get_work_unit(wu["path"])
            )
            for wu in state["work_units"]
        ],
    )


@router.get("/by-path")
def get_by_path(path: str = Query(..., description="The path to look up")):
    """
    Get work unit info for a specific path.

    Returns 404 if no work unit exists for this path.
    """
    registry = get_registry()
    wu = registry.get_work_unit(path)

    if not wu:
        raise HTTPException(status_code=404, detail="Work unit not found")

    return work_unit_to_response(wu)


@router.get("/by-agent/{agent_id}", response_model=list[WorkUnitResponse])
def get_by_agent(agent_id: str):
    """
    Get all work units owned by a specific agent.

    Useful for seeing what an agent is currently working on.
    """
    registry = get_registry()
    work_units = registry.get_work_units_by_agent(agent_id)

    return [work_unit_to_response(wu) for wu in work_units]


@router.get("/queue-position")
def get_queue_position(
    agent_id: str = Query(..., description="Agent ID"),
    path: str = Query(..., description="Work unit path"),
):
    """
    Get an agent's position in a work unit's queue.

    Returns null if the agent is not in the queue.
    """
    registry = get_registry()
    position = registry.get_queue_position(agent_id, path)

    return {
        "agent_id": agent_id,
        "path": path,
        "queue_position": position,
        "in_queue": position is not None,
    }


@router.get("/available")
def check_available(path: str = Query(..., description="Path to check")):
    """
    Check if a path is available (not claimed).

    Quick check without attempting to claim.
    """
    registry = get_registry()
    available = registry.is_path_available(path)

    return {
        "path": path,
        "available": available,
    }
