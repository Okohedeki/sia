import { useEffect, useState, useCallback } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

interface ToolCall {
  id: string
  tool_name: string
  tool_input: Record<string, unknown>
  tool_output: string
  duration_ms: number
  timestamp: string
}

interface Agent {
  id: string
  task: string
  name: string | null
  model: string | null
  source: 'mcp' | 'sdk' | 'unknown'
  state: 'pending' | 'running' | 'completed' | 'failed'
  response: string | null
  error: string | null
  tool_calls: ToolCall[]
  created_at: string
  started_at: string | null
  completed_at: string | null
}

function App() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting')
  const [agents, setAgents] = useState<Agent[]>([])
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

  // Poll agents every second for real-time updates
  useEffect(() => {
    fetchAgents()
    const interval = setInterval(fetchAgents, 1000)
    return () => clearInterval(interval)
  }, [fetchAgents])

  const getStateBadgeClass = (state: Agent['state']) => {
    switch (state) {
      case 'pending': return 'badge-pending'
      case 'running': return 'badge-running'
      case 'completed': return 'badge-completed'
      case 'failed': return 'badge-failed'
    }
  }

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts)
    return date.toLocaleTimeString()
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
                <p className="hint">Connect Claude Code via MCP to see agents here</p>
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
                    <span className={`badge ${getStateBadgeClass(agent.state)}`}>
                      {agent.state}
                    </span>
                  </div>
                  <p className="agent-task-preview">
                    {agent.task.length > 50 ? agent.task.slice(0, 50) + '...' : agent.task}
                  </p>
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
                <pre>{`# 1. Start control plane
sia start

# 2. Add to Claude Code config (~/.claude.json)
{
  "mcpServers": {
    "sia": {
      "command": "sia",
      "args": ["mcp"]
    }
  }
}

# 3. Use Claude Code normally - sia_* tools available`}</pre>
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

              <div className="detail-row">
                <span className="detail-label">Source</span>
                <span className="detail-value">{selectedAgent.source === 'mcp' ? 'Claude Code (MCP)' : selectedAgent.source}</span>
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

              {selectedAgent.tool_calls.length > 0 && (
                <div className="detail-section">
                  <h3>Tool Executions</h3>
                  <div className="tool-calls-list">
                    {selectedAgent.tool_calls.map((tc) => (
                      <div key={tc.id} className="tool-call-item">
                        <div className="tool-call-header">
                          <span className="tool-name">{tc.tool_name}</span>
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
      </div>
    </div>
  )
}

export default App
