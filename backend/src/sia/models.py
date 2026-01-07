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
    CURSOR = "cursor"     # Cursor AI via MCP or rules
    SDK = "sdk"           # Programmatic via SDK
    UNKNOWN = "unknown"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class StepConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EXPLORATORY = "exploratory"


class SpanKind(str, Enum):
    """Type of span in the trace."""
    RUN = "run"           # Root span - entire execution run
    AGENT = "agent"       # Agent or subagent
    STEP = "step"         # Plan step execution
    TOOL = "tool"         # Tool call
    WORKSPACE = "workspace"  # Workspace mutation (file read/write)


class SpanStatus(str, Enum):
    """Status of a span."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"   # Waiting on resource or another agent


class Span(BaseModel):
    """A span in the distributed trace - represents a unit of work."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id: str  # Groups all spans in a run
    parent_id: Optional[str] = None  # Parent span ID (null for root)
    kind: SpanKind
    name: str  # Human-readable name
    status: SpanStatus = SpanStatus.RUNNING

    # Timing
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Context
    agent_id: Optional[str] = None  # Which agent owns this span
    step_index: Optional[int] = None  # Associated plan step

    # Blocking info
    blocked_by_span_id: Optional[str] = None  # Which span is blocking this one
    blocked_by_resource: Optional[str] = None  # What resource caused blocking
    blocked_duration_ms: Optional[int] = None

    # Artifacts and data
    attributes: dict[str, Any] = Field(default_factory=dict)  # Arbitrary metadata
    error_message: Optional[str] = None

    # For workspace spans
    file_path: Optional[str] = None
    operation: Optional[str] = None  # read, write, execute


class Run(BaseModel):
    """A complete execution run - the root trace."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str  # User-provided task/description
    status: SpanStatus = SpanStatus.RUNNING

    # Timing
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Agents in this run
    root_agent_id: Optional[str] = None
    agent_ids: list[str] = Field(default_factory=list)

    # Computed metrics
    total_spans: int = 0
    completed_spans: int = 0
    failed_spans: int = 0
    blocked_spans: int = 0
    max_concurrency: int = 0
    files_touched: list[str] = Field(default_factory=list)

    # For plan divergence tracking
    planned_steps: list[str] = Field(default_factory=list)  # Original plan
    executed_steps: list[str] = Field(default_factory=list)  # What actually ran


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
    # Extended fields for detailed plan view
    owner: Optional[str] = None  # Agent or subagent that owns this step
    resources: list[str] = Field(default_factory=list)  # Required resources (files, processes)
    artifacts: list[str] = Field(default_factory=list)  # Expected outputs
    reason: Optional[str] = None  # Why this step was chosen
    confidence: Optional[StepConfidence] = None  # Confidence level
    blocked_by: list[int] = Field(default_factory=list)  # Step indices this is blocked by
    can_parallel: bool = False  # Can run in parallel with other steps


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
    # Tracing
    trace_id: Optional[str] = None  # Which run this agent belongs to
    span_id: Optional[str] = None  # This agent's span in the trace
    parent_agent_id: Optional[str] = None  # Parent agent (for subagents)


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

class PlanStepInput(BaseModel):
    """Input for a single plan step."""
    description: str
    owner: Optional[str] = None
    resources: list[str] = []
    artifacts: list[str] = []
    reason: Optional[str] = None
    confidence: Optional[str] = None  # high, medium, low, exploratory
    blocked_by: list[int] = []
    can_parallel: bool = False


class SetPlanRequest(BaseModel):
    """Request to set an agent's plan."""
    steps: list[str | PlanStepInput]  # List of step descriptions or detailed step objects


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
    # Extended fields
    owner: Optional[str] = None
    resources: list[str] = []
    artifacts: list[str] = []
    reason: Optional[str] = None
    confidence: Optional[StepConfidence] = None
    blocked_by: list[int] = []
    can_parallel: bool = False


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
    # Tracing
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_agent_id: Optional[str] = None


# Tracing response models

class SpanResponse(BaseModel):
    id: str
    trace_id: str
    parent_id: Optional[str] = None
    kind: SpanKind
    name: str
    status: SpanStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    agent_id: Optional[str] = None
    step_index: Optional[int] = None
    blocked_by_span_id: Optional[str] = None
    blocked_by_resource: Optional[str] = None
    blocked_duration_ms: Optional[int] = None
    attributes: dict[str, Any] = {}
    error_message: Optional[str] = None
    file_path: Optional[str] = None
    operation: Optional[str] = None
    # Nested children for tree view
    children: list["SpanResponse"] = []


class RunResponse(BaseModel):
    id: str
    trace_id: str
    name: str
    status: SpanStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    root_agent_id: Optional[str] = None
    agent_ids: list[str] = []
    total_spans: int = 0
    completed_spans: int = 0
    failed_spans: int = 0
    blocked_spans: int = 0
    max_concurrency: int = 0
    files_touched: list[str] = []
    planned_steps: list[str] = []
    executed_steps: list[str] = []


class RunWithSpansResponse(BaseModel):
    """A run with all its spans for the trace waterfall view."""
    run: RunResponse
    spans: list[SpanResponse]  # Flat list of all spans
    root_span: Optional[SpanResponse] = None  # Tree structure


class TimelineEvent(BaseModel):
    """An event on the unified timeline."""
    timestamp: datetime
    event_type: str  # span_start, span_end, blocked, error
    span_id: str
    agent_id: Optional[str] = None
    name: str
    status: SpanStatus
    duration_ms: Optional[int] = None


class TimelineResponse(BaseModel):
    """Timeline data for visualization."""
    start_time: datetime
    end_time: Optional[datetime] = None
    events: list[TimelineEvent] = []
    agents: list[str] = []  # Agent IDs for coloring


class PlanDivergence(BaseModel):
    """Shows how execution diverged from the plan."""
    step_description: str
    planned_index: Optional[int] = None  # Position in plan (null if inserted)
    executed_index: Optional[int] = None  # Position in execution (null if skipped)
    status: str  # executed, skipped, reordered, inserted


class PlanComparisonResponse(BaseModel):
    """Comparison between planned and executed steps."""
    planned_steps: list[str]
    executed_steps: list[str]
    divergences: list[PlanDivergence] = []
    has_divergence: bool = False


# Agent Interaction Graph models

class AgentGraphNode(BaseModel):
    """A node in the agent interaction graph."""
    id: str
    name: str
    state: AgentState
    source: AgentSource
    is_root: bool = False
    depth: int = 0  # Depth in the tree (root = 0)
    tool_calls_count: int = 0
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class GraphEdgeType(str, Enum):
    """Type of edge in the agent interaction graph."""
    SPAWN = "spawn"          # Parent spawned child
    DELEGATE = "delegate"    # Parent delegated task to child
    BLOCKING = "blocking"    # Agent is blocking another


class AgentGraphEdge(BaseModel):
    """An edge in the agent interaction graph."""
    source_id: str  # Source agent ID
    target_id: str  # Target agent ID
    edge_type: GraphEdgeType
    timestamp: datetime  # When this relationship was established
    label: Optional[str] = None  # Optional label (e.g., "blocked by")


class AgentGraphMetrics(BaseModel):
    """Metrics derived from the agent graph."""
    total_agents: int = 0
    max_depth: int = 0  # Maximum depth of the agent tree
    fan_out: int = 0    # Maximum children per agent
    failed_agents: int = 0
    blocked_agents: int = 0
    bottleneck_agents: list[str] = []  # Agents that blocked others


class AgentGraphResponse(BaseModel):
    """Agent interaction graph data for visualization."""
    nodes: list[AgentGraphNode] = []
    edges: list[AgentGraphEdge] = []
    metrics: AgentGraphMetrics = AgentGraphMetrics()
    root_agent_id: Optional[str] = None


# Workspace Impact Map models

class WorkspaceNodeType(str, Enum):
    """Type of node in workspace map."""
    FILE = "file"
    DIRECTORY = "directory"
    AGENT = "agent"


class WorkspaceNode(BaseModel):
    """A node in the workspace impact map."""
    id: str
    node_type: WorkspaceNodeType
    name: str  # File name or agent name
    path: Optional[str] = None  # Full path for files
    agent_id: Optional[str] = None  # For agent nodes
    read_count: int = 0
    write_count: int = 0
    touched_by: list[str] = []  # Agent IDs that touched this file


class WorkspaceEdgeType(str, Enum):
    """Type of edge in workspace map."""
    READ = "read"
    WRITE = "write"
    MODIFY = "modify"


class WorkspaceEdge(BaseModel):
    """An edge showing agent-file interaction."""
    source_id: str  # Agent ID
    target_id: str  # File node ID
    edge_type: WorkspaceEdgeType
    timestamp: datetime
    step_index: Optional[int] = None


class WorkspaceConflict(BaseModel):
    """Shows files touched by multiple agents."""
    file_path: str
    file_id: str
    agents: list[str]  # Agent IDs
    operations: list[str]  # read, write, modify


class WorkspaceMapMetrics(BaseModel):
    """Metrics for workspace impact map."""
    total_files: int = 0
    total_agents: int = 0
    files_with_conflicts: int = 0
    most_touched_file: Optional[str] = None
    most_active_agent: Optional[str] = None


class WorkspaceMapResponse(BaseModel):
    """Workspace impact map data."""
    nodes: list[WorkspaceNode] = []
    edges: list[WorkspaceEdge] = []
    conflicts: list[WorkspaceConflict] = []
    metrics: WorkspaceMapMetrics = WorkspaceMapMetrics()
