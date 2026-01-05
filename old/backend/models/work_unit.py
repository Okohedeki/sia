from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class WorkUnitType(str, Enum):
    FILE = "file"
    DIRECTORY = "directory"
    PROCESS = "process"


class WorkUnitStatus(str, Enum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    COMPLETED = "completed"


@dataclass
class QueueEntry:
    """Represents an agent waiting in queue for a work unit."""

    agent_id: str
    requested_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self, position: int) -> dict:
        return {
            "agent_id": self.agent_id,
            "requested_at": self.requested_at.isoformat(),
            "position": position,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueueEntry":
        return cls(
            agent_id=data["agent_id"],
            requested_at=datetime.fromisoformat(data["requested_at"])
            if "requested_at" in data
            else datetime.utcnow(),
        )


@dataclass
class WorkUnit:
    """
    Represents a shared resource that agents coordinate around.

    A work unit can be a file, directory, or process resource.
    Only one agent can own a work unit at a time. Others join a queue.
    """

    path: str
    type: WorkUnitType = WorkUnitType.FILE
    id: str = field(default_factory=lambda: f"wu-{uuid4().hex[:12]}")

    # Ownership
    owner_agent_id: str | None = None
    claimed_at: datetime | None = None

    # Queue of waiting agents (FIFO)
    queue: list[QueueEntry] = field(default_factory=list)

    # Lifecycle
    status: WorkUnitStatus = WorkUnitStatus.AVAILABLE
    ttl_seconds: int = 300  # 5 minutes default
    expires_at: datetime | None = None

    def is_claimed(self) -> bool:
        return self.owner_agent_id is not None

    def is_owned_by(self, agent_id: str) -> bool:
        return self.owner_agent_id == agent_id

    def queue_position(self, agent_id: str) -> int | None:
        """Get 1-indexed queue position for an agent, or None if not in queue."""
        for i, entry in enumerate(self.queue):
            if entry.agent_id == agent_id:
                return i + 1
        return None

    def is_in_queue(self, agent_id: str) -> bool:
        return any(entry.agent_id == agent_id for entry in self.queue)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "type": self.type.value,
            "owner_agent_id": self.owner_agent_id,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "queue": [entry.to_dict(i + 1) for i, entry in enumerate(self.queue)],
            "status": self.status.value,
            "ttl_seconds": self.ttl_seconds,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkUnit":
        return cls(
            id=data.get("id", f"wu-{uuid4().hex[:12]}"),
            path=data["path"],
            type=WorkUnitType(data.get("type", "file")),
            owner_agent_id=data.get("owner_agent_id"),
            claimed_at=datetime.fromisoformat(data["claimed_at"])
            if data.get("claimed_at")
            else None,
            queue=[QueueEntry.from_dict(e) for e in data.get("queue", [])],
            status=WorkUnitStatus(data.get("status", "available")),
            ttl_seconds=data.get("ttl_seconds", 300),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
        )
