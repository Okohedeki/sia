from dataclasses import dataclass
from .work_unit import WorkUnit


@dataclass
class ClaimResult:
    """Result of attempting to claim a work unit."""

    success: bool
    work_unit: WorkUnit
    queue_position: int | None = None
    owner_agent_id: str | None = None
    message: str = ""

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "work_unit": self.work_unit.to_dict(),
            "message": self.message,
        }
        if self.queue_position is not None:
            result["queue_position"] = self.queue_position
        if self.owner_agent_id is not None:
            result["owner_agent_id"] = self.owner_agent_id
        return result


@dataclass
class ApiResponse:
    """Generic API response wrapper."""

    success: bool
    message: str
    data: dict | None = None

    def to_dict(self) -> dict:
        result = {
            "success": self.success,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        return result
