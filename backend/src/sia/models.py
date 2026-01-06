"""Sia data models."""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field
import uuid


class AgentState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentSource(str, Enum):
    HOOKS = "hooks"       # Claude Code via hooks
    SDK = "sdk"           # Programmatic via SDK
    UNKNOWN = "unknown"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class StepLog(BaseModel):
    """A log entry for a plan step."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    message: str
    level: str = "info"  # info, warning, error, debug
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlanStep(BaseModel):
    """A step in an agent's plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    index: int  # Step number (1-based)
    description: str
    status: StepStatus = StepStatus.PENDING
    files: list[str] = Field(default_factory=list)  # Files involved in this step
    logs: list[StepLog] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Plan(BaseModel):
    """An agent's execution plan."""

    steps: list[PlanStep] = Field(default_factory=list)
    current_step_index: Optional[int] = None  # 1-based index of current step
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkUnit(BaseModel):
    """A resource (file/directory) being worked on by an agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    path: str  # File or directory path
    agent_id: str  # Agent working on this resource
    step_index: Optional[int] = None  # Which step this is associated with
    operation: str = "unknown"  # read, write, execute, etc.
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ToolCall(BaseModel):
    """Represents a single tool execution."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    duration_ms: int
    step_index: Optional[int] = None  # Which step this tool call is part of
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Agent(BaseModel):
    """Represents an agent instance."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str
    name: Optional[str] = None
    model: Optional[str] = None
    source: AgentSource = AgentSource.UNKNOWN
    state: AgentState = AgentState.PENDING
    response: Optional[str] = None
    error: Optional[str] = None
    plan: Optional[Plan] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Session tracking
    session_id: Optional[str] = None
    working_directory: Optional[str] = None
    last_activity: datetime = Field(default_factory=datetime.utcnow)


# API Request/Response models

class RegisterAgentRequest(BaseModel):
    task: str
    name: Optional[str] = None
    model: Optional[str] = None
    source: Optional[str] = None  # "hooks", "sdk", etc.


class UpdateStateRequest(BaseModel):
    state: str
    response: Optional[str] = None
    error: Optional[str] = None


class ReportToolCallRequest(BaseModel):
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    duration_ms: int
    step_index: Optional[int] = None


class ToolCallResponse(BaseModel):
    id: str
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str
    duration_ms: int
    step_index: Optional[int] = None
    timestamp: datetime


# Plan-related request models

class SetPlanRequest(BaseModel):
    """Request to set an agent's plan."""
    steps: list[str]  # List of step descriptions


class UpdateStepRequest(BaseModel):
    """Request to update a step's status."""
    status: str  # pending, in_progress, completed, skipped
    files: Optional[list[str]] = None  # Files being worked on


class AddStepLogRequest(BaseModel):
    """Request to add a log entry to a step."""
    message: str
    level: str = "info"


# Response models

class StepLogResponse(BaseModel):
    id: str
    message: str
    level: str
    timestamp: datetime


class PlanStepResponse(BaseModel):
    id: str
    index: int
    description: str
    status: StepStatus
    files: list[str]
    logs: list[StepLogResponse]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class PlanResponse(BaseModel):
    steps: list[PlanStepResponse]
    current_step_index: Optional[int] = None
    created_at: datetime


class WorkUnitResponse(BaseModel):
    id: str
    path: str
    agent_id: str
    step_index: Optional[int] = None
    operation: str
    created_at: datetime


class AgentResponse(BaseModel):
    id: str
    task: str
    name: Optional[str] = None
    model: Optional[str] = None
    source: AgentSource = AgentSource.UNKNOWN
    state: AgentState
    response: Optional[str] = None
    error: Optional[str] = None
    plan: Optional[PlanResponse] = None
    tool_calls: list[ToolCallResponse] = []
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    session_id: Optional[str] = None
    working_directory: Optional[str] = None
    last_activity: Optional[datetime] = None
