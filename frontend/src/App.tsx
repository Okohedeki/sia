import { useEffect, useState, useCallback } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

interface StepLog {
  id: string
  message: string
  level: string
  timestamp: string
}

interface PlanStep {
  id: string
  index: number
  description: string
  status: 'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed'
  files: string[]
  logs: StepLog[]
  started_at: string | null
  completed_at: string | null
  // Extended fields for detailed plan view
  owner?: string  // agent or subagent that owns this step
  resources?: string[]  // required resources (files, processes)
  artifacts?: string[]  // expected outputs
  reason?: string  // why this step was chosen
  confidence?: 'high' | 'medium' | 'low' | 'exploratory'
  blocked_by?: number[]  // step indices this is blocked by
  can_parallel?: boolean  // can run in parallel with other steps
}

interface Plan {
  steps: PlanStep[]
  current_step_index: number | null
  created_at: string
}

interface ToolCall {
  id: string
  tool_name: string
  tool_input: Record<string, unknown>
  tool_output: string
  duration_ms: number
  step_index: number | null
  timestamp: string
}

interface Agent {
  id: string
  task: string
  name: string | null
  model: string | null
  source: 'hooks' | 'cursor' | 'sdk' | 'unknown'
  state: 'pending' | 'running' | 'completed' | 'failed'
  response: string | null
  error: string | null
  plan: Plan | null
  tool_calls: ToolCall[]
  created_at: string
  started_at: string | null
  completed_at: string | null
  session_id: string | null
  working_directory: string | null
  last_activity: string | null
}

interface WorkUnit {
  id: string
  path: string
  agent_id: string
  step_index: number | null
  operation: string
  created_at: string
}

// Tracing types
type SpanKind = 'run' | 'agent' | 'step' | 'tool' | 'workspace'
type SpanStatus = 'running' | 'completed' | 'failed' | 'blocked'

interface Span {
  id: string
  trace_id: string
  parent_id: string | null
  kind: SpanKind
  name: string
  status: SpanStatus
  start_time: string
  end_time: string | null
  duration_ms: number | null
  agent_id: string | null
  step_index: number | null
  blocked_by_span_id: string | null
  blocked_by_resource: string | null
  blocked_duration_ms: number | null
  attributes: Record<string, unknown>
  error_message: string | null
  file_path: string | null
  operation: string | null
  children: Span[]
}

interface Run {
  id: string
  trace_id: string
  name: string
  status: SpanStatus
  start_time: string
  end_time: string | null
  duration_ms: number | null
  root_agent_id: string | null
  agent_ids: string[]
  total_spans: number
  completed_spans: number
  failed_spans: number
  blocked_spans: number
  max_concurrency: number
  files_touched: string[]
  planned_steps: string[]
  executed_steps: string[]
}

interface RunWithSpans {
  run: Run
  spans: Span[]
  root_span: Span | null
}

interface PlanDivergence {
  step_description: string
  planned_index: number | null
  executed_index: number | null
  status: 'executed' | 'skipped' | 'reordered' | 'inserted'
}

interface PlanComparison {
  planned_steps: string[]
  executed_steps: string[]
  divergences: PlanDivergence[]
  has_divergence: boolean
}

// Agent Graph types
type AgentState = 'pending' | 'running' | 'completed' | 'failed'
type AgentSourceType = 'hooks' | 'cursor' | 'sdk' | 'unknown'
type GraphEdgeType = 'spawn' | 'delegate' | 'blocking'

interface AgentGraphNode {
  id: string
  name: string
  state: AgentState
  source: AgentSourceType
  is_root: boolean
  depth: number
  tool_calls_count: number
  duration_ms: number | null
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

interface AgentGraphEdge {
  source_id: string
  target_id: string
  edge_type: GraphEdgeType
  timestamp: string
  label: string | null
}

interface AgentGraphMetrics {
  total_agents: number
  max_depth: number
  fan_out: number
  failed_agents: number
  blocked_agents: number
  bottleneck_agents: string[]
}

interface AgentGraph {
  nodes: AgentGraphNode[]
  edges: AgentGraphEdge[]
  metrics: AgentGraphMetrics
  root_agent_id: string | null
}

// Workspace Impact Map types
type WorkspaceNodeType = 'file' | 'directory' | 'agent'
type WorkspaceEdgeType = 'read' | 'write' | 'modify'

interface WorkspaceNode {
  id: string
  node_type: WorkspaceNodeType
  name: string
  path: string | null
  agent_id: string | null
  read_count: number
  write_count: number
  touched_by: string[]
}

interface WorkspaceEdge {
  source_id: string
  target_id: string
  edge_type: WorkspaceEdgeType
  timestamp: string
  step_index: number | null
}

interface WorkspaceConflict {
  file_path: string
  file_id: string
  agents: string[]
  operations: string[]
}

interface WorkspaceMapMetrics {
  total_files: number
  total_agents: number
  files_with_conflicts: number
  most_touched_file: string | null
  most_active_agent: string | null
}

interface WorkspaceMap {
  nodes: WorkspaceNode[]
  edges: WorkspaceEdge[]
  conflicts: WorkspaceConflict[]
  metrics: WorkspaceMapMetrics
}

type SidebarTab = 'agents' | 'plans' | 'traces'

function App() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [agents, setAgents] = useState<Agent[]>([])
  const [workUnits, setWorkUnits] = useState<WorkUnit[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>('agents')
  // Tracing state
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [selectedRunData, setSelectedRunData] = useState<RunWithSpans | null>(null)
  const [planComparison, setPlanComparison] = useState<PlanComparison | null>(null)
  const [agentGraph, setAgentGraph] = useState<AgentGraph | null>(null)
  const [workspaceMap, setWorkspaceMap] = useState<WorkspaceMap | null>(null)

  const selectedAgent = agents.find(a => a.id === selectedAgentId)

  // Health check
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_URL}/health`)
        setConnectionStatus(response.ok ? 'connected' : 'disconnected')
      } catch {
        setConnectionStatus('disconnected')
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 5000)
    return () => clearInterval(interval)
  }, [])

  // Fetch agents list
  const fetchAgents = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/agents`)
      if (response.ok) {
        const data = await response.json()
        setAgents(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Fetch work units
  const fetchWorkUnits = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/work-units`)
      if (response.ok) {
        const data = await response.json()
        setWorkUnits(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Fetch runs list
  const fetchRuns = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/runs`)
      if (response.ok) {
        const data = await response.json()
        setRuns(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Fetch selected run data
  const fetchSelectedRun = useCallback(async (runId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/runs/${runId}`)
      if (response.ok) {
        const data = await response.json()
        setSelectedRunData(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Fetch plan comparison for selected run
  const fetchPlanComparison = useCallback(async (runId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/runs/${runId}/plan-comparison`)
      if (response.ok) {
        const data = await response.json()
        setPlanComparison(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Fetch agent graph for selected run
  const fetchAgentGraph = useCallback(async (runId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/runs/${runId}/agent-graph`)
      if (response.ok) {
        const data = await response.json()
        setAgentGraph(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Fetch workspace map for selected run
  const fetchWorkspaceMap = useCallback(async (runId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/runs/${runId}/workspace-map`)
      if (response.ok) {
        const data = await response.json()
        setWorkspaceMap(data)
      }
    } catch {
      // Ignore fetch errors
    }
  }, [])

  // Delete an agent
  const deleteAgent = useCallback(async (agentId: string) => {
    try {
      const response = await fetch(`${API_URL}/api/agents/${agentId}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        // Clear selection if deleted agent was selected
        if (selectedAgentId === agentId) {
          setSelectedAgentId(null)
        }
        // Refresh agents list
        fetchAgents()
      }
    } catch {
      // Ignore errors
    }
  }, [selectedAgentId, fetchAgents])

  // Poll agents, work units, and runs every second
  useEffect(() => {
    fetchAgents()
    fetchWorkUnits()
    fetchRuns()
    const interval = setInterval(() => {
      fetchAgents()
      fetchWorkUnits()
      fetchRuns()
    }, 1000)
    return () => clearInterval(interval)
  }, [fetchAgents, fetchWorkUnits, fetchRuns])

  // Fetch selected run data when selection changes
  useEffect(() => {
    if (selectedRunId) {
      fetchSelectedRun(selectedRunId)
      fetchPlanComparison(selectedRunId)
      fetchAgentGraph(selectedRunId)
      fetchWorkspaceMap(selectedRunId)
      // Also poll the selected run for updates
      const interval = setInterval(() => {
        fetchSelectedRun(selectedRunId)
        fetchPlanComparison(selectedRunId)
        fetchAgentGraph(selectedRunId)
        fetchWorkspaceMap(selectedRunId)
      }, 1000)
      return () => clearInterval(interval)
    } else {
      setSelectedRunData(null)
      setPlanComparison(null)
      setAgentGraph(null)
      setWorkspaceMap(null)
    }
  }, [selectedRunId, fetchSelectedRun, fetchPlanComparison, fetchAgentGraph, fetchWorkspaceMap])

  const getStateBadgeClass = (state: Agent['state']) => {
    switch (state) {
      case 'pending': return 'badge-pending'
      case 'running': return 'badge-running'
      case 'completed': return 'badge-completed'
      case 'failed': return 'badge-failed'
    }
  }

  const getStepStatusClass = (status: PlanStep['status']) => {
    switch (status) {
      case 'pending': return 'step-pending'
      case 'in_progress': return 'step-in-progress'
      case 'completed': return 'step-completed'
      case 'skipped': return 'step-skipped'
      case 'failed': return 'step-failed'
    }
  }

  const getConfidenceClass = (confidence?: PlanStep['confidence']) => {
    switch (confidence) {
      case 'high': return 'confidence-high'
      case 'medium': return 'confidence-medium'
      case 'low': return 'confidence-low'
      case 'exploratory': return 'confidence-exploratory'
      default: return ''
    }
  }

  const getLogLevelClass = (level: string) => {
    switch (level) {
      case 'error': return 'log-error'
      case 'warning': return 'log-warning'
      case 'debug': return 'log-debug'
      default: return 'log-info'
    }
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleTimeString()
  }

  const getFileName = (path: string) => {
    const parts = path.replace(/\\/g, '/').split('/')
    return parts[parts.length - 1]
  }

  const getAgentName = (agentId: string) => {
    const agent = agents.find(a => a.id === agentId)
    return agent?.name || agentId
  }

  // Span helper functions
  const getSpanStatusClass = (status: SpanStatus) => {
    switch (status) {
      case 'running': return 'span-running'
      case 'completed': return 'span-completed'
      case 'failed': return 'span-failed'
      case 'blocked': return 'span-blocked'
    }
  }

  const getSpanKindIcon = (kind: SpanKind) => {
    switch (kind) {
      case 'run': return '🚀'
      case 'agent': return '🤖'
      case 'step': return '📋'
      case 'tool': return '🔧'
      case 'workspace': return '📁'
    }
  }

  const formatDuration = (ms: number | null) => {
    if (ms === null) return '-'
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60000).toFixed(1)}m`
  }

  // Get agents that have plans
  const agentsWithPlans = agents.filter(a => a.plan && a.plan.steps.length > 0)

  return (
    <div className="app">
      <header className="header">
        <h1 className="title">Sia Control Plane</h1>
        <div className="connection-status">
          <span className={`status-dot ${connectionStatus}`} title={connectionStatus} />
          <span className="status-text">
            {connectionStatus === 'connected' && 'Connected'}
            {connectionStatus === 'connecting' && 'Connecting...'}
            {connectionStatus === 'disconnected' && 'Disconnected'}
          </span>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-tabs">
            <button
              className={`sidebar-tab ${sidebarTab === 'agents' ? 'active' : ''}`}
              onClick={() => setSidebarTab('agents')}
            >
              Agents
              <span className="tab-count">{agents.length}</span>
            </button>
            <button
              className={`sidebar-tab ${sidebarTab === 'plans' ? 'active' : ''}`}
              onClick={() => setSidebarTab('plans')}
            >
              Plans
              <span className="tab-count">{agentsWithPlans.length}</span>
            </button>
            <button
              className={`sidebar-tab ${sidebarTab === 'traces' ? 'active' : ''}`}
              onClick={() => setSidebarTab('traces')}
            >
              Traces
              <span className="tab-count">{runs.length}</span>
            </button>
          </div>

          {sidebarTab === 'agents' && (
            <div className="agent-list">
              {agents.length === 0 ? (
                <div className="no-agents">
                  <p>No agents connected</p>
                  <p className="hint">Run 'sia init' in your project to start tracking agents</p>
                </div>
              ) : (
                agents.map(agent => (
                  <div
                    key={agent.id}
                    className={`agent-item ${selectedAgentId === agent.id ? 'selected' : ''}`}
                    onClick={() => setSelectedAgentId(agent.id)}
                  >
                    <div className="agent-item-header">
                      <span className="agent-id">{agent.name || agent.id}</span>
                      <div className="agent-item-actions">
                        <span className={`badge ${getStateBadgeClass(agent.state)}`}>
                          {agent.state}
                        </span>
                        <button
                          className="delete-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteAgent(agent.id)
                          }}
                          title="Remove agent"
                        >
                          ×
                        </button>
                      </div>
                    </div>
                    <div className="agent-meta-row">
                      {agent.working_directory && (
                        <span className="agent-directory" title={agent.working_directory}>
                          {agent.working_directory.replace(/\\/g, '/').split('/').pop()}
                        </span>
                      )}
                      <span className={`source-indicator source-${agent.source}`}>
                        {agent.source === 'hooks' && 'Claude'}
                        {agent.source === 'cursor' && 'Cursor'}
                        {agent.source === 'sdk' && 'SDK'}
                      </span>
                    </div>
                    <p className="agent-task-preview">
                      {agent.task.length > 50 ? agent.task.slice(0, 50) + '...' : agent.task}
                    </p>
                    {agent.plan && (
                      <div className="agent-plan-preview">
                        <span className="plan-progress">
                          {agent.plan.steps.filter(s => s.status === 'completed').length}/{agent.plan.steps.length} steps
                        </span>
                        {agent.plan.current_step_index && (
                          <span className="current-step">
                            Step {agent.plan.current_step_index}
                          </span>
                        )}
                      </div>
                    )}
                    {agent.tool_calls.length > 0 && (
                      <span className="tool-count">{agent.tool_calls.length} tool calls</span>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {sidebarTab === 'plans' && (
            <div className="plans-list">
              {agentsWithPlans.length === 0 ? (
                <div className="no-plans">
                  <p>No active plans</p>
                  <p className="hint">Plans will appear when agents start executing tasks</p>
                </div>
              ) : (
                agentsWithPlans.map(agent => (
                  <div
                    key={agent.id}
                    className={`plan-item ${selectedAgentId === agent.id ? 'selected' : ''}`}
                    onClick={() => setSelectedAgentId(agent.id)}
                  >
                    <div className="plan-item-header">
                      <span className="plan-agent-name">{agent.name || agent.id}</span>
                      <span className={`badge ${getStateBadgeClass(agent.state)}`}>
                        {agent.state}
                      </span>
                    </div>
                    <div className="plan-item-progress">
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${(agent.plan!.steps.filter(s => s.status === 'completed').length / agent.plan!.steps.length) * 100}%`
                          }}
                        />
                      </div>
                      <span className="progress-text">
                        {agent.plan!.steps.filter(s => s.status === 'completed').length}/{agent.plan!.steps.length}
                      </span>
                    </div>
                    <div className="plan-item-steps">
                      {agent.plan!.steps.map(step => (
                        <div
                          key={step.id}
                          className={`plan-step-mini ${getStepStatusClass(step.status)}`}
                        >
                          <span className="step-num">{step.index}</span>
                          <span className="step-desc">
                            {step.description.length > 40 ? step.description.slice(0, 40) + '...' : step.description}
                          </span>
                          {step.status === 'in_progress' && <span className="step-active-dot" />}
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {sidebarTab === 'traces' && (
            <div className="traces-list">
              {runs.length === 0 ? (
                <div className="no-traces">
                  <p>No traces recorded</p>
                  <p className="hint">Traces will appear when agents run tasks</p>
                </div>
              ) : (
                runs.map(run => (
                  <div
                    key={run.id}
                    className={`trace-item ${selectedRunId === run.id ? 'selected' : ''}`}
                    onClick={() => {
                      setSelectedRunId(run.id)
                      setSelectedAgentId(null)
                    }}
                  >
                    <div className="trace-item-header">
                      <span className="trace-name">
                        {run.name.length > 35 ? run.name.slice(0, 35) + '...' : run.name}
                      </span>
                      <span className={`span-status-badge ${getSpanStatusClass(run.status)}`}>
                        {run.status}
                      </span>
                    </div>
                    <div className="trace-item-stats">
                      <span className="trace-stat">
                        <span className="stat-icon">📊</span>
                        {run.total_spans} spans
                      </span>
                      <span className="trace-stat">
                        <span className="stat-icon">⏱️</span>
                        {formatDuration(run.duration_ms)}
                      </span>
                    </div>
                    <div className="trace-item-meta">
                      <span className="trace-time">{formatTimestamp(run.start_time)}</span>
                      {run.agent_ids.length > 1 && (
                        <span className="trace-agents">{run.agent_ids.length} agents</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </aside>

        <main className="main">
          {/* Trace Waterfall View */}
          {sidebarTab === 'traces' && selectedRunData ? (
            <div className="trace-waterfall">
              <div className="waterfall-header">
                <h2>{selectedRunData.run.name}</h2>
                <div className="waterfall-stats">
                  <span className={`span-status-badge large ${getSpanStatusClass(selectedRunData.run.status)}`}>
                    {selectedRunData.run.status}
                  </span>
                  <span className="waterfall-stat">
                    Duration: {formatDuration(selectedRunData.run.duration_ms)}
                  </span>
                  <span className="waterfall-stat">
                    Spans: {selectedRunData.run.total_spans}
                  </span>
                  <span className="waterfall-stat">
                    Max Concurrency: {selectedRunData.run.max_concurrency}
                  </span>
                </div>
              </div>

              <div className="waterfall-content">
                {selectedRunData.spans.length === 0 ? (
                  <div className="no-spans">
                    <p>No spans recorded yet</p>
                  </div>
                ) : (
                  <div className="span-list">
                    {selectedRunData.spans.map((span) => {
                      // Calculate position relative to run start
                      const runStart = new Date(selectedRunData.run.start_time).getTime()
                      const runEnd = selectedRunData.run.end_time
                        ? new Date(selectedRunData.run.end_time).getTime()
                        : Date.now()
                      const totalDuration = runEnd - runStart
                      const spanStart = new Date(span.start_time).getTime()
                      const spanEnd = span.end_time ? new Date(span.end_time).getTime() : Date.now()
                      const leftPercent = totalDuration > 0 ? ((spanStart - runStart) / totalDuration) * 100 : 0
                      const widthPercent = totalDuration > 0 ? ((spanEnd - spanStart) / totalDuration) * 100 : 100
                      const depth = span.parent_id ? 1 : 0 // Simple depth calculation

                      return (
                        <div key={span.id} className={`waterfall-row ${getSpanStatusClass(span.status)}`}>
                          <div className="span-info" style={{ paddingLeft: `${depth * 20}px` }}>
                            <span className="span-kind-icon">{getSpanKindIcon(span.kind)}</span>
                            <span className="span-name">{span.name}</span>
                            <span className="span-duration">{formatDuration(span.duration_ms)}</span>
                          </div>
                          <div className="span-timeline">
                            <div
                              className={`span-bar ${getSpanStatusClass(span.status)}`}
                              style={{
                                left: `${Math.min(leftPercent, 100)}%`,
                                width: `${Math.max(Math.min(widthPercent, 100 - leftPercent), 1)}%`,
                              }}
                            >
                              {span.status === 'blocked' && (
                                <span className="blocked-indicator" title={span.blocked_by_resource || 'Blocked'}>⏸</span>
                              )}
                              {span.status === 'failed' && (
                                <span className="error-indicator" title={span.error_message || 'Error'}>⚠</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Unified Timeline View */}
              {selectedRunData.spans.length > 0 && (
                <div className="unified-timeline">
                  <div className="timeline-header">
                    <h3>Unified Timeline</h3>
                    <span className="timeline-info">
                      {selectedRunData.run.agent_ids.length} agent(s) | Max concurrency: {selectedRunData.run.max_concurrency}
                    </span>
                  </div>

                  {/* Time axis */}
                  <div className="time-axis">
                    {(() => {
                      const runStart = new Date(selectedRunData.run.start_time).getTime()
                      const runEnd = selectedRunData.run.end_time
                        ? new Date(selectedRunData.run.end_time).getTime()
                        : Date.now()
                      const totalDuration = runEnd - runStart
                      const markers = [0, 25, 50, 75, 100]
                      return markers.map(pct => (
                        <div key={pct} className="time-marker" style={{ left: `${pct}%` }}>
                          <span className="time-label">{formatDuration(Math.round(totalDuration * pct / 100))}</span>
                        </div>
                      ))
                    })()}
                  </div>

                  {/* Agent swimlanes */}
                  <div className="swimlanes">
                    {selectedRunData.run.agent_ids.map(agentId => {
                      const agentSpans = selectedRunData.spans.filter(s => s.agent_id === agentId)
                      const runStart = new Date(selectedRunData.run.start_time).getTime()
                      const runEnd = selectedRunData.run.end_time
                        ? new Date(selectedRunData.run.end_time).getTime()
                        : Date.now()
                      const totalDuration = runEnd - runStart

                      return (
                        <div key={agentId} className="swimlane">
                          <div className="swimlane-label">
                            <span className="agent-icon">🤖</span>
                            <span className="agent-name">{getAgentName(agentId)}</span>
                          </div>
                          <div className="swimlane-track">
                            {agentSpans.map(span => {
                              const spanStart = new Date(span.start_time).getTime()
                              const spanEnd = span.end_time ? new Date(span.end_time).getTime() : Date.now()
                              const leftPct = totalDuration > 0 ? ((spanStart - runStart) / totalDuration) * 100 : 0
                              const widthPct = totalDuration > 0 ? ((spanEnd - spanStart) / totalDuration) * 100 : 1

                              return (
                                <div
                                  key={span.id}
                                  className={`timeline-span ${getSpanStatusClass(span.status)} kind-${span.kind}`}
                                  style={{
                                    left: `${Math.min(leftPct, 100)}%`,
                                    width: `${Math.max(Math.min(widthPct, 100 - leftPct), 0.5)}%`,
                                  }}
                                  title={`${span.name} (${formatDuration(span.duration_ms)})`}
                                >
                                  {span.status === 'blocked' && <span className="block-mark">⏸</span>}
                                </div>
                              )
                            })}

                            {/* Gap indicators (idle time) */}
                            {(() => {
                              const gaps: { start: number; end: number }[] = []
                              const sortedSpans = [...agentSpans].sort(
                                (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
                              )
                              let lastEnd = runStart
                              for (const span of sortedSpans) {
                                const spanStart = new Date(span.start_time).getTime()
                                if (spanStart > lastEnd + 100) { // Gap > 100ms
                                  gaps.push({ start: lastEnd, end: spanStart })
                                }
                                const spanEnd = span.end_time ? new Date(span.end_time).getTime() : Date.now()
                                lastEnd = Math.max(lastEnd, spanEnd)
                              }
                              return gaps.map((gap, i) => {
                                const leftPct = ((gap.start - runStart) / totalDuration) * 100
                                const widthPct = ((gap.end - gap.start) / totalDuration) * 100
                                if (widthPct < 1) return null
                                return (
                                  <div
                                    key={`gap-${i}`}
                                    className="timeline-gap"
                                    style={{
                                      left: `${leftPct}%`,
                                      width: `${widthPct}%`,
                                    }}
                                    title={`Idle: ${formatDuration(gap.end - gap.start)}`}
                                  />
                                )
                              })
                            })()}
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {/* Concurrency indicator */}
                  <div className="concurrency-chart">
                    <div className="concurrency-label">Concurrency</div>
                    <div className="concurrency-track">
                      {(() => {
                        const runStart = new Date(selectedRunData.run.start_time).getTime()
                        const runEnd = selectedRunData.run.end_time
                          ? new Date(selectedRunData.run.end_time).getTime()
                          : Date.now()
                        const totalDuration = runEnd - runStart
                        const buckets = 50 // Number of time buckets
                        const bucketDuration = totalDuration / buckets
                        const concurrency: number[] = new Array(buckets).fill(0)

                        for (const span of selectedRunData.spans) {
                          const spanStart = new Date(span.start_time).getTime()
                          const spanEnd = span.end_time ? new Date(span.end_time).getTime() : Date.now()
                          const startBucket = Math.floor((spanStart - runStart) / bucketDuration)
                          const endBucket = Math.floor((spanEnd - runStart) / bucketDuration)
                          for (let i = Math.max(0, startBucket); i <= Math.min(buckets - 1, endBucket); i++) {
                            concurrency[i]++
                          }
                        }

                        const maxConc = Math.max(...concurrency, 1)
                        return concurrency.map((c, i) => (
                          <div
                            key={i}
                            className="concurrency-bar"
                            style={{ height: `${(c / maxConc) * 100}%` }}
                            title={`${c} concurrent spans`}
                          />
                        ))
                      })()}
                    </div>
                  </div>
                </div>
              )}

              {/* Run Metrics */}
              <div className="waterfall-metrics">
                <div className="metrics-row">
                  <div className="metric-card">
                    <span className="metric-value">{selectedRunData.run.completed_spans}</span>
                    <span className="metric-label">Completed</span>
                  </div>
                  <div className="metric-card failed">
                    <span className="metric-value">{selectedRunData.run.failed_spans}</span>
                    <span className="metric-label">Failed</span>
                  </div>
                  <div className="metric-card blocked">
                    <span className="metric-value">{selectedRunData.run.blocked_spans}</span>
                    <span className="metric-label">Blocked</span>
                  </div>
                  <div className="metric-card">
                    <span className="metric-value">{selectedRunData.run.files_touched.length}</span>
                    <span className="metric-label">Files Touched</span>
                  </div>
                </div>
              </div>

              {/* Plan vs Execution Comparison */}
              {planComparison && planComparison.planned_steps.length > 0 && (
                <div className="plan-comparison">
                  <div className="comparison-header">
                    <h3>Plan vs Execution</h3>
                    {planComparison.has_divergence ? (
                      <span className="divergence-badge has-divergence">Divergence Detected</span>
                    ) : (
                      <span className="divergence-badge no-divergence">On Track</span>
                    )}
                  </div>

                  <div className="comparison-columns">
                    {/* Planned Steps */}
                    <div className="comparison-column planned">
                      <div className="column-header">
                        <span className="column-title">Planned</span>
                        <span className="column-count">{planComparison.planned_steps.length} steps</span>
                      </div>
                      <div className="step-list">
                        {planComparison.planned_steps.map((step, idx) => {
                          const divergence = planComparison.divergences.find(
                            d => d.planned_index === idx
                          )
                          return (
                            <div
                              key={idx}
                              className={`comparison-step ${divergence?.status || 'pending'}`}
                            >
                              <span className="step-index">{idx + 1}</span>
                              <span className="step-text">{step}</span>
                              {divergence && divergence.status !== 'executed' && (
                                <span className={`step-badge ${divergence.status}`}>
                                  {divergence.status}
                                </span>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Divergence Arrow */}
                    <div className="comparison-arrow">
                      <span className="arrow-icon">→</span>
                    </div>

                    {/* Executed Steps */}
                    <div className="comparison-column executed">
                      <div className="column-header">
                        <span className="column-title">Executed</span>
                        <span className="column-count">{planComparison.executed_steps.length} steps</span>
                      </div>
                      <div className="step-list">
                        {planComparison.executed_steps.length === 0 ? (
                          <div className="no-steps">No steps executed yet</div>
                        ) : (
                          planComparison.executed_steps.map((step, idx) => {
                            const divergence = planComparison.divergences.find(
                              d => d.executed_index === idx && d.status === 'inserted'
                            )
                            const isInserted = divergence?.status === 'inserted'
                            return (
                              <div
                                key={idx}
                                className={`comparison-step ${isInserted ? 'inserted' : 'executed'}`}
                              >
                                <span className="step-index">{idx + 1}</span>
                                <span className="step-text">{step}</span>
                                {isInserted && (
                                  <span className="step-badge inserted">inserted</span>
                                )}
                              </div>
                            )
                          })
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Divergence Summary */}
                  {planComparison.has_divergence && (
                    <div className="divergence-summary">
                      <div className="summary-item">
                        <span className="summary-count">
                          {planComparison.divergences.filter(d => d.status === 'skipped').length}
                        </span>
                        <span className="summary-label">Skipped</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-count">
                          {planComparison.divergences.filter(d => d.status === 'reordered').length}
                        </span>
                        <span className="summary-label">Reordered</span>
                      </div>
                      <div className="summary-item">
                        <span className="summary-count">
                          {planComparison.divergences.filter(d => d.status === 'inserted').length}
                        </span>
                        <span className="summary-label">Inserted</span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Agent Interaction Graph */}
              {agentGraph && agentGraph.nodes.length > 0 && (
                <div className="agent-graph">
                  <div className="graph-header">
                    <h3>Agent Interaction Graph</h3>
                    <div className="graph-metrics">
                      <span className="graph-metric">
                        <span className="metric-value">{agentGraph.metrics.total_agents}</span>
                        <span className="metric-label">Agents</span>
                      </span>
                      <span className="graph-metric">
                        <span className="metric-value">{agentGraph.metrics.max_depth}</span>
                        <span className="metric-label">Depth</span>
                      </span>
                      <span className="graph-metric">
                        <span className="metric-value">{agentGraph.metrics.fan_out}</span>
                        <span className="metric-label">Fan-out</span>
                      </span>
                      {agentGraph.metrics.failed_agents > 0 && (
                        <span className="graph-metric failed">
                          <span className="metric-value">{agentGraph.metrics.failed_agents}</span>
                          <span className="metric-label">Failed</span>
                        </span>
                      )}
                      {agentGraph.metrics.bottleneck_agents.length > 0 && (
                        <span className="graph-metric bottleneck">
                          <span className="metric-value">{agentGraph.metrics.bottleneck_agents.length}</span>
                          <span className="metric-label">Bottlenecks</span>
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="graph-visualization">
                    {/* Render agent tree by depth levels */}
                    {(() => {
                      const maxDepth = agentGraph.metrics.max_depth
                      const levels: AgentGraphNode[][] = []
                      for (let d = 0; d <= maxDepth; d++) {
                        levels.push(agentGraph.nodes.filter(n => n.depth === d))
                      }
                      return levels.map((levelNodes, depth) => (
                        <div key={depth} className="graph-level">
                          <div className="level-label">Level {depth}</div>
                          <div className="level-nodes">
                            {levelNodes.map(node => {
                              const isBottleneck = agentGraph.metrics.bottleneck_agents.includes(node.id)
                              const childEdges = agentGraph.edges.filter(e => e.source_id === node.id && e.edge_type === 'spawn')
                              const blockingEdges = agentGraph.edges.filter(e => e.source_id === node.id && e.edge_type === 'blocking')
                              return (
                                <div
                                  key={node.id}
                                  className={`graph-node state-${node.state} ${node.is_root ? 'root' : ''} ${isBottleneck ? 'bottleneck' : ''}`}
                                >
                                  <div className="node-header">
                                    <span className="node-icon">
                                      {node.is_root ? '🏠' : '🤖'}
                                    </span>
                                    <span className="node-name">{node.name}</span>
                                    <span className={`node-state-badge state-${node.state}`}>
                                      {node.state}
                                    </span>
                                  </div>
                                  <div className="node-details">
                                    <span className="node-stat">
                                      <span className="stat-icon">🔧</span>
                                      {node.tool_calls_count} tools
                                    </span>
                                    {node.duration_ms && (
                                      <span className="node-stat">
                                        <span className="stat-icon">⏱️</span>
                                        {formatDuration(node.duration_ms)}
                                      </span>
                                    )}
                                    <span className={`node-source source-${node.source}`}>
                                      {node.source === 'hooks' && 'Claude'}
                                      {node.source === 'cursor' && 'Cursor'}
                                      {node.source === 'sdk' && 'SDK'}
                                    </span>
                                  </div>
                                  {childEdges.length > 0 && (
                                    <div className="node-children-info">
                                      <span className="children-icon">↓</span>
                                      {childEdges.length} child{childEdges.length > 1 ? 'ren' : ''}
                                    </div>
                                  )}
                                  {blockingEdges.length > 0 && (
                                    <div className="node-blocking-info">
                                      <span className="blocking-icon">⚠️</span>
                                      Blocking {blockingEdges.length} agent{blockingEdges.length > 1 ? 's' : ''}
                                    </div>
                                  )}
                                  {node.error_message && (
                                    <div className="node-error">
                                      <span className="error-icon">❌</span>
                                      <span className="error-text">{node.error_message.slice(0, 50)}...</span>
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                          {/* Render edges to next level */}
                          {depth < maxDepth && (
                            <div className="level-connectors">
                              {agentGraph.edges
                                .filter(e => e.edge_type === 'spawn' && levelNodes.some(n => n.id === e.source_id))
                                .map((edge, i) => (
                                  <div key={i} className="connector spawn">
                                    <span className="connector-line">│</span>
                                    <span className="connector-label">{edge.label}</span>
                                  </div>
                                ))
                              }
                            </div>
                          )}
                        </div>
                      ))
                    })()}
                  </div>

                  {/* Cascade failures view */}
                  {agentGraph.metrics.failed_agents > 0 && (
                    <div className="cascade-failures">
                      <h4>Cascade Failures</h4>
                      <div className="failure-chain">
                        {agentGraph.nodes
                          .filter(n => n.state === 'failed')
                          .map(node => (
                            <div key={node.id} className="failure-node">
                              <span className="failure-icon">💥</span>
                              <span className="failure-name">{node.name}</span>
                              {node.error_message && (
                                <span className="failure-msg" title={node.error_message}>
                                  {node.error_message.slice(0, 100)}
                                </span>
                              )}
                            </div>
                          ))
                        }
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Workspace Impact Map */}
              {workspaceMap && (workspaceMap.nodes.length > 0 || workspaceMap.conflicts.length > 0) && (
                <div className="workspace-map">
                  <div className="workspace-header">
                    <h3>Workspace Impact Map</h3>
                    <div className="workspace-metrics">
                      <span className="workspace-metric">
                        <span className="metric-value">{workspaceMap.metrics.total_files}</span>
                        <span className="metric-label">Files</span>
                      </span>
                      <span className="workspace-metric">
                        <span className="metric-value">{workspaceMap.metrics.total_agents}</span>
                        <span className="metric-label">Agents</span>
                      </span>
                      {workspaceMap.metrics.files_with_conflicts > 0 && (
                        <span className="workspace-metric conflict">
                          <span className="metric-value">{workspaceMap.metrics.files_with_conflicts}</span>
                          <span className="metric-label">Conflicts</span>
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Conflict Warning */}
                  {workspaceMap.conflicts.length > 0 && (
                    <div className="conflict-section">
                      <h4>Multi-Agent Conflicts</h4>
                      <p className="conflict-desc">Files touched by multiple agents</p>
                      <div className="conflict-list">
                        {workspaceMap.conflicts.map(conflict => (
                          <div key={conflict.file_id} className="conflict-item">
                            <div className="conflict-file">
                              <span className="file-icon">📄</span>
                              <span className="file-name" title={conflict.file_path}>
                                {conflict.file_path.split('/').pop()}
                              </span>
                              <span className="file-path">{conflict.file_path}</span>
                            </div>
                            <div className="conflict-agents">
                              <span className="agents-label">Touched by:</span>
                              {conflict.agents.map(agentId => (
                                <span key={agentId} className="conflict-agent">
                                  🤖 {getAgentName(agentId)}
                                </span>
                              ))}
                            </div>
                            <div className="conflict-ops">
                              {conflict.operations.map((op, i) => (
                                <span key={i} className={`op-badge op-${op}`}>
                                  {op}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* File Map Grid */}
                  <div className="workspace-grid">
                    <div className="grid-section files-section">
                      <h4>Files Touched</h4>
                      <div className="file-grid">
                        {workspaceMap.nodes
                          .filter(n => n.node_type === 'file')
                          .map(node => {
                            const hasConflict = workspaceMap.conflicts.some(c => c.file_id === node.id)
                            return (
                              <div
                                key={node.id}
                                className={`file-node ${hasConflict ? 'has-conflict' : ''}`}
                                title={node.path || node.name}
                              >
                                <div className="file-node-header">
                                  <span className="file-icon">📄</span>
                                  <span className="file-name">{node.name}</span>
                                </div>
                                <div className="file-node-stats">
                                  {node.read_count > 0 && (
                                    <span className="op-stat read">
                                      <span className="op-icon">👁</span> Read
                                    </span>
                                  )}
                                  {node.write_count > 0 && (
                                    <span className="op-stat write">
                                      <span className="op-icon">✏️</span> Write
                                    </span>
                                  )}
                                </div>
                                <div className="file-node-agents">
                                  {node.touched_by.length} agent{node.touched_by.length > 1 ? 's' : ''}
                                </div>
                                {hasConflict && (
                                  <div className="conflict-badge">⚠️ Conflict</div>
                                )}
                              </div>
                            )
                          })}
                      </div>
                    </div>

                    {/* Agent Activity Summary */}
                    <div className="grid-section agents-section">
                      <h4>Agent Activity</h4>
                      <div className="agent-activity-list">
                        {workspaceMap.nodes
                          .filter(n => n.node_type === 'agent')
                          .map(node => {
                            const edges = workspaceMap.edges.filter(e => e.source_id === node.id)
                            const reads = edges.filter(e => e.edge_type === 'read').length
                            const writes = edges.filter(e => e.edge_type === 'write' || e.edge_type === 'modify').length
                            return (
                              <div key={node.id} className="agent-activity-item">
                                <div className="agent-activity-header">
                                  <span className="agent-icon">🤖</span>
                                  <span className="agent-name">{node.name}</span>
                                </div>
                                <div className="agent-activity-stats">
                                  <span className="activity-stat read">
                                    <span className="stat-count">{reads}</span>
                                    <span className="stat-label">reads</span>
                                  </span>
                                  <span className="activity-stat write">
                                    <span className="stat-count">{writes}</span>
                                    <span className="stat-label">writes</span>
                                  </span>
                                </div>
                              </div>
                            )
                          })}
                      </div>
                    </div>
                  </div>

                  {/* Insights */}
                  {(workspaceMap.metrics.most_touched_file || workspaceMap.metrics.most_active_agent) && (
                    <div className="workspace-insights">
                      {workspaceMap.metrics.most_touched_file && (
                        <div className="insight-item">
                          <span className="insight-icon">🔥</span>
                          <span className="insight-label">Hotspot:</span>
                          <span className="insight-value">{workspaceMap.metrics.most_touched_file.split('/').pop()}</span>
                        </div>
                      )}
                      {workspaceMap.metrics.most_active_agent && (
                        <div className="insight-item">
                          <span className="insight-icon">⚡</span>
                          <span className="insight-label">Most Active:</span>
                          <span className="insight-value">{workspaceMap.metrics.most_active_agent}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : sidebarTab === 'traces' && !selectedRunData ? (
            <div className="empty-state">
              <h2>Trace Waterfall</h2>
              <p>Select a trace from the sidebar to view the span waterfall.</p>
            </div>
          ) : !selectedAgent ? (
            <div className="empty-state">
              <h2>Agent Observability Console</h2>
              <p>Select an agent from the sidebar to view its execution details.</p>
              <div className="usage-hint">
                <h3>Setup</h3>
                <pre>{`# 1. Install package
pip install -e path/to/sia/backend

# 2. Initialize hooks in your project
sia init

# 3. Start control plane
sia start

# 4. Use Claude Code normally
claude

# All activity is automatically tracked!`}</pre>
              </div>
            </div>
          ) : (
            <div className="agent-detail">
              <div className="agent-detail-header">
                <h2>{selectedAgent.name || `Agent ${selectedAgent.id}`}</h2>
                <span className={`badge ${getStateBadgeClass(selectedAgent.state)}`}>
                  {selectedAgent.state}
                </span>
              </div>

              <div className="detail-section">
                <h3>Task</h3>
                <p className="task-text">{selectedAgent.task}</p>
              </div>

              {selectedAgent.working_directory && (
                <div className="detail-row">
                  <span className="detail-label">Directory</span>
                  <span className="detail-value" title={selectedAgent.working_directory}>
                    {selectedAgent.working_directory}
                  </span>
                </div>
              )}

              <div className="detail-row">
                <span className="detail-label">Source</span>
                <span className={`source-badge source-${selectedAgent.source}`}>
                  {selectedAgent.source === 'hooks' && 'Claude Code'}
                  {selectedAgent.source === 'cursor' && 'Cursor'}
                  {selectedAgent.source === 'sdk' && 'SDK'}
                  {selectedAgent.source === 'unknown' && 'Unknown'}
                </span>
              </div>

              {selectedAgent.model && (
                <div className="detail-row">
                  <span className="detail-label">Model</span>
                  <span className="detail-value">{selectedAgent.model}</span>
                </div>
              )}

              <div className="detail-row">
                <span className="detail-label">Started</span>
                <span className="detail-value">
                  {selectedAgent.started_at ? formatTimestamp(selectedAgent.started_at) : '-'}
                </span>
              </div>

              {/* Plan Section - Detailed Task Graph View */}
              {selectedAgent.plan && (
                <div className="detail-section plan-section-full">
                  <div className="plan-header">
                    <h3>Execution Plan</h3>
                    <div className="plan-summary">
                      <span className="plan-stat">
                        <span className="stat-value">{selectedAgent.plan.steps.filter(s => s.status === 'completed').length}</span>
                        <span className="stat-label">Done</span>
                      </span>
                      <span className="plan-stat">
                        <span className="stat-value">{selectedAgent.plan.steps.filter(s => s.status === 'in_progress').length}</span>
                        <span className="stat-label">Running</span>
                      </span>
                      <span className="plan-stat">
                        <span className="stat-value">{selectedAgent.plan.steps.filter(s => s.status === 'pending').length}</span>
                        <span className="stat-label">Pending</span>
                      </span>
                      <span className="plan-stat">
                        <span className="stat-value">{selectedAgent.plan.steps.filter(s => s.status === 'failed').length}</span>
                        <span className="stat-label">Failed</span>
                      </span>
                    </div>
                  </div>

                  <div className="plan-steps-detailed">
                    {selectedAgent.plan.steps.map((step) => (
                      <div
                        key={step.id}
                        className={`plan-step-card ${getStepStatusClass(step.status)} ${selectedAgent.plan?.current_step_index === step.index ? 'current' : ''}`}
                      >
                        {/* Step Header */}
                        <div className="step-card-header">
                          <div className="step-identity">
                            <span className="step-number">{step.index}</span>
                            <div className="step-title-block">
                              <span className="step-title">{step.description}</span>
                              {step.owner && (
                                <span className="step-owner">
                                  <span className="owner-icon">@</span>
                                  {step.owner}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="step-badges">
                            {step.confidence && (
                              <span className={`confidence-badge ${getConfidenceClass(step.confidence)}`}>
                                {step.confidence}
                              </span>
                            )}
                            <span className={`status-badge ${getStepStatusClass(step.status)}`}>
                              {step.status.replace('_', ' ')}
                            </span>
                          </div>
                        </div>

                        {/* Step Details */}
                        <div className="step-card-body">
                          {/* Resources */}
                          {(step.resources && step.resources.length > 0) || step.files.length > 0 ? (
                            <div className="step-detail-row">
                              <span className="detail-icon">📁</span>
                              <div className="detail-content">
                                <span className="detail-title">Required Resources</span>
                                <div className="resource-tags">
                                  {step.files.map((file, i) => (
                                    <span key={`file-${i}`} className="resource-tag file" title={file}>
                                      {getFileName(file)}
                                    </span>
                                  ))}
                                  {step.resources?.map((res, i) => (
                                    <span key={`res-${i}`} className="resource-tag process" title={res}>
                                      {res}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            </div>
                          ) : null}

                          {/* Expected Artifacts */}
                          {step.artifacts && step.artifacts.length > 0 && (
                            <div className="step-detail-row">
                              <span className="detail-icon">📦</span>
                              <div className="detail-content">
                                <span className="detail-title">Expected Artifacts</span>
                                <div className="artifact-tags">
                                  {step.artifacts.map((artifact, i) => (
                                    <span key={i} className="artifact-tag" title={artifact}>
                                      {getFileName(artifact)}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Why This Step */}
                          {step.reason && (
                            <div className="step-detail-row">
                              <span className="detail-icon">💡</span>
                              <div className="detail-content">
                                <span className="detail-title">Why This Step</span>
                                <p className="step-reason">{step.reason}</p>
                              </div>
                            </div>
                          )}

                          {/* Parallelism & Dependencies */}
                          {(step.blocked_by && step.blocked_by.length > 0) || step.can_parallel ? (
                            <div className="step-detail-row">
                              <span className="detail-icon">🔗</span>
                              <div className="detail-content">
                                <span className="detail-title">Dependencies</span>
                                <div className="dependency-info">
                                  {step.blocked_by && step.blocked_by.length > 0 && (
                                    <span className="blocked-by">
                                      Blocked by: {step.blocked_by.map(idx => `Step ${idx}`).join(', ')}
                                    </span>
                                  )}
                                  {step.can_parallel && (
                                    <span className="can-parallel">Can run in parallel</span>
                                  )}
                                </div>
                              </div>
                            </div>
                          ) : null}

                          {/* Logs */}
                          {step.logs.length > 0 && (
                            <div className="step-detail-row logs-row">
                              <span className="detail-icon">📋</span>
                              <div className="detail-content">
                                <span className="detail-title">Execution Logs</span>
                                <div className="step-logs">
                                  {step.logs.map((log) => (
                                    <div key={log.id} className={`step-log ${getLogLevelClass(log.level)}`}>
                                      <span className="log-time">{formatTimestamp(log.timestamp)}</span>
                                      <span className="log-level">[{log.level}]</span>
                                      <span className="log-message">{log.message}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}

                          {/* Timing */}
                          {(step.started_at || step.completed_at) && (
                            <div className="step-timing">
                              {step.started_at && (
                                <span className="timing-item">
                                  Started: {formatTimestamp(step.started_at)}
                                </span>
                              )}
                              {step.completed_at && (
                                <span className="timing-item">
                                  Completed: {formatTimestamp(step.completed_at)}
                                </span>
                              )}
                            </div>
                          )}
                        </div>

                        {/* Running Indicator */}
                        {step.status === 'in_progress' && (
                          <div className="step-running-bar">
                            <span className="spinner small"></span>
                            <span>Executing...</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedAgent.tool_calls.length > 0 && (
                <div className="detail-section">
                  <h3>Tool Executions</h3>
                  <div className="tool-calls-list">
                    {selectedAgent.tool_calls.map((tc) => (
                      <div key={tc.id} className="tool-call-item">
                        <div className="tool-call-header">
                          <span className="tool-name">{tc.tool_name}</span>
                          {tc.step_index && (
                            <span className="tool-step">Step {tc.step_index}</span>
                          )}
                          <span className="tool-duration">{tc.duration_ms}ms</span>
                        </div>
                        <div className="tool-call-body">
                          <div className="tool-input">
                            <span className="label">Input:</span>
                            <pre>{JSON.stringify(tc.tool_input, null, 2)}</pre>
                          </div>
                          <div className="tool-output">
                            <span className="label">Output:</span>
                            <pre>{tc.tool_output}</pre>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedAgent.state === 'completed' && selectedAgent.response && (
                <div className="detail-section">
                  <h3>Final Response</h3>
                  <pre className="response-text">{selectedAgent.response}</pre>
                </div>
              )}

              {selectedAgent.state === 'failed' && selectedAgent.error && (
                <div className="detail-section error">
                  <h3>Error</h3>
                  <pre className="error-text">{selectedAgent.error}</pre>
                </div>
              )}

              {selectedAgent.state === 'running' && (
                <div className="running-indicator">
                  <span className="spinner"></span>
                  <span>Agent is executing...</span>
                </div>
              )}
            </div>
          )}
        </main>

        {/* Work Units Sidebar */}
        <aside className="sidebar-right">
          <div className="sidebar-header">
            <h2>Work Units</h2>
            <span className="agent-count">{workUnits.length}</span>
          </div>
          <div className="work-units-list">
            {workUnits.length === 0 ? (
              <div className="no-work-units">
                <p>No active work units</p>
                <p className="hint">Files being worked on will appear here</p>
              </div>
            ) : (
              workUnits.map(wu => (
                <div
                  key={wu.id}
                  className={`work-unit-item ${wu.agent_id === selectedAgentId ? 'highlighted' : ''}`}
                  onClick={() => setSelectedAgentId(wu.agent_id)}
                >
                  <div className="work-unit-header">
                    <span className="work-unit-file" title={wu.path}>
                      {getFileName(wu.path)}
                    </span>
                    <span className={`work-unit-op op-${wu.operation}`}>
                      {wu.operation}
                    </span>
                  </div>
                  <div className="work-unit-details">
                    <span className="work-unit-agent">{getAgentName(wu.agent_id)}</span>
                    {wu.step_index && (
                      <span className="work-unit-step">Step {wu.step_index}</span>
                    )}
                  </div>
                  <div className="work-unit-path" title={wu.path}>
                    {wu.path}
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

export default App
