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
  status: 'pending' | 'in_progress' | 'completed' | 'skipped'
  files: string[]
  logs: StepLog[]
  started_at: string | null
  completed_at: string | null
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
  source: 'hooks' | 'sdk' | 'unknown'
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

function App() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [agents, setAgents] = useState<Agent[]>([])
  const [workUnits, setWorkUnits] = useState<WorkUnit[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)

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

  // Poll agents and work units every second
  useEffect(() => {
    fetchAgents()
    fetchWorkUnits()
    const interval = setInterval(() => {
      fetchAgents()
      fetchWorkUnits()
    }, 1000)
    return () => clearInterval(interval)
  }, [fetchAgents, fetchWorkUnits])

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
          <div className="sidebar-header">
            <h2>Agents</h2>
            <span className="agent-count">{agents.length}</span>
          </div>
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
                  {agent.working_directory && (
                    <p className="agent-directory" title={agent.working_directory}>
                      {agent.working_directory.replace(/\\/g, '/').split('/').pop()}
                    </p>
                  )}
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
        </aside>

        <main className="main">
          {!selectedAgent ? (
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
                <span className="detail-value">{selectedAgent.source === 'hooks' ? 'Claude Code (Hooks)' : selectedAgent.source}</span>
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

              {/* Plan Section */}
              {selectedAgent.plan && (
                <div className="detail-section plan-section">
                  <h3>Execution Plan</h3>
                  <div className="plan-steps">
                    {selectedAgent.plan.steps.map((step) => (
                      <div
                        key={step.id}
                        className={`plan-step ${getStepStatusClass(step.status)} ${selectedAgent.plan?.current_step_index === step.index ? 'current' : ''}`}
                      >
                        <div className="step-header">
                          <span className="step-index">{step.index}</span>
                          <span className="step-description">{step.description}</span>
                          <span className={`step-status-badge ${getStepStatusClass(step.status)}`}>
                            {step.status.replace('_', ' ')}
                          </span>
                        </div>

                        {step.files.length > 0 && (
                          <div className="step-files">
                            <span className="files-label">Files:</span>
                            {step.files.map((file, i) => (
                              <span key={i} className="file-tag" title={file}>
                                {getFileName(file)}
                              </span>
                            ))}
                          </div>
                        )}

                        {step.logs.length > 0 && (
                          <div className="step-logs">
                            {step.logs.map((log) => (
                              <div key={log.id} className={`step-log ${getLogLevelClass(log.level)}`}>
                                <span className="log-time">{formatTimestamp(log.timestamp)}</span>
                                <span className="log-level">[{log.level}]</span>
                                <span className="log-message">{log.message}</span>
                              </div>
                            ))}
                          </div>
                        )}

                        {step.status === 'in_progress' && (
                          <div className="step-running-indicator">
                            <span className="spinner small"></span>
                            <span>In progress...</span>
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
