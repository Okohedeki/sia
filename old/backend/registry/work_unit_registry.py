"""
WorkUnitRegistry - Central coordination for multi-agent work units.

This is the core component that:
- Tracks all active work units (visible to all agents)
- Manages exclusive claims with FIFO queuing
- Handles TTL expiration and automatic cleanup
- Promotes queued agents when work units are released
"""

import threading
from datetime import datetime, timedelta
from typing import Callable

from ..models import (
    AgentInfo,
    WorkUnit,
    QueueEntry,
    WorkUnitType,
    WorkUnitStatus,
    ClaimResult,
)


class WorkUnitRegistry:
    """
    Thread-safe registry for work units and agents.

    All agents see the same global state. When an agent wants to modify
    a resource, they must claim it. If already claimed, they join a queue.
    """

    def __init__(self, default_ttl_seconds: int = 300):
        self._lock = threading.RLock()
        self._work_units: dict[str, WorkUnit] = {}  # path -> WorkUnit
        self._agents: dict[str, AgentInfo] = {}  # agent_id -> AgentInfo
        self._default_ttl = default_ttl_seconds

        # Callbacks for UI integration (SSE/WebSocket)
        self._on_change_callbacks: list[Callable[[str, dict], None]] = []

    # =========================================================================
    # Agent Management
    # =========================================================================

    def register_agent(self, agent: AgentInfo) -> AgentInfo:
        """Register an agent with the system."""
        with self._lock:
            existing = self._agents.get(agent.agent_id)
            if existing:
                # Update existing agent
                existing.update_last_seen()
                return existing

            self._agents[agent.agent_id] = agent
            self._emit("agent_registered", agent.to_dict())
            return agent

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """Get agent by ID."""
        with self._lock:
            return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentInfo]:
        """Get all registered agents."""
        with self._lock:
            return list(self._agents.values())

    def heartbeat(self, agent_id: str) -> bool:
        """Update agent's last_seen timestamp."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent:
                agent.update_last_seen()
                return True
            return False

    def remove_agent(self, agent_id: str) -> None:
        """Remove an agent and release all their work units."""
        with self._lock:
            if agent_id in self._agents:
                # Release all work units owned by this agent
                for path in list(self._work_units.keys()):
                    wu = self._work_units[path]
                    if wu.owner_agent_id == agent_id:
                        self._release_internal(agent_id, path)
                    # Also remove from queues
                    wu.queue = [e for e in wu.queue if e.agent_id != agent_id]

                del self._agents[agent_id]
                self._emit("agent_removed", {"agent_id": agent_id})

    # =========================================================================
    # Work Unit Management
    # =========================================================================

    def claim(
        self,
        agent_id: str,
        path: str,
        work_unit_type: WorkUnitType = WorkUnitType.FILE,
        ttl_seconds: int | None = None,
    ) -> ClaimResult:
        """
        Attempt to claim a work unit.

        If unclaimed, grants ownership immediately.
        If already claimed by another agent, adds to queue.
        If already owned by this agent, refreshes TTL.
        """
        ttl = ttl_seconds or self._default_ttl

        with self._lock:
            # Auto-register agent if not known
            if agent_id not in self._agents:
                # Create a minimal agent entry (will be enriched later)
                self._agents[agent_id] = AgentInfo(
                    agent_id=agent_id,
                    session_id=agent_id.split(":")[0],  # Extract session from agent_id
                )

            wu = self._work_units.get(path)

            # Case 1: Work unit doesn't exist - create and claim
            if wu is None:
                wu = WorkUnit(
                    path=path,
                    type=work_unit_type,
                    owner_agent_id=agent_id,
                    claimed_at=datetime.utcnow(),
                    status=WorkUnitStatus.CLAIMED,
                    ttl_seconds=ttl,
                    expires_at=datetime.utcnow() + timedelta(seconds=ttl),
                )
                self._work_units[path] = wu
                self._emit("work_unit_claimed", wu.to_dict())

                return ClaimResult(
                    success=True,
                    work_unit=wu,
                    message="Work unit claimed",
                )

            # Case 2: Already owned by this agent - refresh TTL
            if wu.owner_agent_id == agent_id:
                wu.expires_at = datetime.utcnow() + timedelta(seconds=ttl)
                return ClaimResult(
                    success=True,
                    work_unit=wu,
                    message="Ownership refreshed",
                )

            # Case 3: Already in queue - return current position
            if wu.is_in_queue(agent_id):
                position = wu.queue_position(agent_id)
                return ClaimResult(
                    success=False,
                    work_unit=wu,
                    queue_position=position,
                    owner_agent_id=wu.owner_agent_id,
                    message=f"Already in queue at position {position}",
                )

            # Case 4: Owned by another agent - add to queue
            entry = QueueEntry(agent_id=agent_id)
            wu.queue.append(entry)
            position = len(wu.queue)

            self._emit(
                "agent_queued",
                {"path": path, "agent_id": agent_id, "position": position},
            )

            return ClaimResult(
                success=False,
                work_unit=wu,
                queue_position=position,
                owner_agent_id=wu.owner_agent_id,
                message=f"Work unit busy. Added to queue at position {position}",
            )

    def release(self, agent_id: str, path: str) -> bool:
        """
        Release a work unit.

        If there are queued agents, promotes the next one.
        """
        with self._lock:
            return self._release_internal(agent_id, path)

    def _release_internal(self, agent_id: str, path: str) -> bool:
        """Internal release logic (must hold lock)."""
        wu = self._work_units.get(path)
        if wu is None:
            return False

        if wu.owner_agent_id != agent_id:
            return False

        # Promote next in queue, or mark as available
        if wu.queue:
            next_entry = wu.queue.pop(0)
            wu.owner_agent_id = next_entry.agent_id
            wu.claimed_at = datetime.utcnow()
            wu.expires_at = datetime.utcnow() + timedelta(seconds=wu.ttl_seconds)

            self._emit(
                "work_unit_transferred",
                {"path": path, "new_owner": next_entry.agent_id},
            )
        else:
            # No one waiting - mark as available
            wu.owner_agent_id = None
            wu.claimed_at = None
            wu.expires_at = None
            wu.status = WorkUnitStatus.AVAILABLE

            self._emit("work_unit_released", {"path": path})

        return True

    def leave_queue(self, agent_id: str, path: str) -> bool:
        """Remove an agent from a work unit's queue."""
        with self._lock:
            wu = self._work_units.get(path)
            if wu is None:
                return False

            original_len = len(wu.queue)
            wu.queue = [e for e in wu.queue if e.agent_id != agent_id]

            if len(wu.queue) < original_len:
                self._emit(
                    "agent_left_queue",
                    {"path": path, "agent_id": agent_id},
                )
                return True
            return False

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_all_work_units(self) -> list[WorkUnit]:
        """Get all work units (global visibility)."""
        with self._lock:
            return list(self._work_units.values())

    def get_work_unit(self, path: str) -> WorkUnit | None:
        """Get a specific work unit by path."""
        with self._lock:
            return self._work_units.get(path)

    def get_work_units_by_agent(self, agent_id: str) -> list[WorkUnit]:
        """Get all work units owned by an agent."""
        with self._lock:
            return [
                wu
                for wu in self._work_units.values()
                if wu.owner_agent_id == agent_id
            ]

    def get_queue_position(self, agent_id: str, path: str) -> int | None:
        """Get an agent's position in a work unit's queue."""
        with self._lock:
            wu = self._work_units.get(path)
            if wu:
                return wu.queue_position(agent_id)
            return None

    def is_path_available(self, path: str) -> bool:
        """Check if a path is available (not claimed)."""
        with self._lock:
            wu = self._work_units.get(path)
            return wu is None or wu.owner_agent_id is None

    # =========================================================================
    # TTL and Cleanup
    # =========================================================================

    def cleanup_expired(self) -> list[str]:
        """
        Clean up expired work units and agents.

        Returns list of released paths.
        """
        released = []
        now = datetime.utcnow()

        with self._lock:
            # Cleanup expired work units
            for path, wu in list(self._work_units.items()):
                if wu.expires_at and wu.expires_at < now:
                    # Expired - release to next in queue or mark available
                    if wu.owner_agent_id:
                        self._release_internal(wu.owner_agent_id, path)
                        released.append(path)

            # Cleanup expired agents
            for agent_id in list(self._agents.keys()):
                agent = self._agents[agent_id]
                if agent.is_expired():
                    self.remove_agent(agent_id)

        return released

    # =========================================================================
    # Event Emission (for UI integration)
    # =========================================================================

    def on_change(self, callback: Callable[[str, dict], None]) -> None:
        """Register a callback for state changes."""
        self._on_change_callbacks.append(callback)

    def _emit(self, event_type: str, data: dict) -> None:
        """Emit an event to all registered callbacks."""
        for callback in self._on_change_callbacks:
            try:
                callback(event_type, data)
            except Exception:
                pass  # Don't let callback errors break the registry

    # =========================================================================
    # State Export (for UI/debugging)
    # =========================================================================

    def get_state(self) -> dict:
        """Get full registry state as dict (for API/UI)."""
        with self._lock:
            return {
                "agents": [a.to_dict() for a in self._agents.values()],
                "work_units": [wu.to_dict() for wu in self._work_units.values()],
            }
