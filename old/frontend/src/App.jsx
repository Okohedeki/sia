import { useState, useEffect, useCallback } from 'react'

const API_URL = '/api'
const POLL_INTERVAL = 2000 // 2 seconds

function App() {
  const [state, setState] = useState({ agents: [], work_units: [] })
  const [connected, setConnected] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  const fetchState = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/work-units/state`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const data = await response.json()
      setState(data)
      setConnected(true)
      setError(null)
      setLastUpdate(new Date())
    } catch (err) {
      setConnected(false)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchState()
    const interval = setInterval(fetchState, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchState])

  const totalQueued = state.work_units.reduce(
    (sum, wu) => sum + (wu.queue?.length || 0),
    0
  )

  return (
    <div className="app">
      <Header connected={connected} lastUpdate={lastUpdate} loading={loading} />

      {error && (
        <div className="error-banner">
          <span className="error-banner-icon">⚠️</span>
          <div className="error-banner-text">
            <strong>Cannot connect to Sia daemon</strong>
            <span>Make sure the daemon is running on port 7432. Run: sia start</span>
          </div>
        </div>
      )}

      <StatsBar
        agentCount={state.agents.length}
        workUnitCount={state.work_units.length}
        queuedCount={totalQueued}
      />

      <div className="main-grid">
        <AgentPanel agents={state.agents} />
        <WorkUnitPanel workUnits={state.work_units} />
      </div>
    </div>
  )
}

function Header({ connected, lastUpdate, loading }) {
  return (
    <header className="header">
      <h1>
        <span>🔄</span>
        Sia Dashboard
      </h1>
      <div className="header-right" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div className={`refresh-indicator ${loading ? 'loading' : ''}`}>
          {loading ? '↻ Refreshing...' : lastUpdate ? `Updated ${formatTime(lastUpdate)}` : ''}
        </div>
        <div className={`status-badge ${connected ? 'connected' : 'disconnected'}`}>
          <span className="status-dot"></span>
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </div>
    </header>
  )
}

function StatsBar({ agentCount, workUnitCount, queuedCount }) {
  return (
    <div className="stats-bar">
      <div className="stat-card agents">
        <div className="label">Active Agents</div>
        <div className="value">{agentCount}</div>
      </div>
      <div className="stat-card work-units">
        <div className="label">Work Units</div>
        <div className="value">{workUnitCount}</div>
      </div>
      <div className="stat-card queued">
        <div className="label">Queued Requests</div>
        <div className="value">{queuedCount}</div>
      </div>
    </div>
  )
}

function AgentPanel({ agents }) {
  return (
    <div className="panel">
      <div className="panel-header">Agents</div>
      <div className="panel-content">
        {agents.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">🤖</div>
            <div className="empty-state-text">No agents active</div>
          </div>
        ) : (
          agents.map(agent => (
            <AgentItem key={agent.agent_id} agent={agent} />
          ))
        )}
      </div>
    </div>
  )
}

function AgentItem({ agent }) {
  const isSubagent = agent.agent_type === 'subagent'
  const displayId = truncateId(agent.agent_id)

  return (
    <div className="agent-item">
      <div className={`agent-avatar ${isSubagent ? 'subagent' : ''}`}>
        {isSubagent ? '🔹' : '🤖'}
      </div>
      <div className="agent-info">
        <div className="agent-id" title={agent.agent_id}>{displayId}</div>
        <div className="agent-type">
          {isSubagent ? 'Subagent' : 'Main Agent'}
        </div>
      </div>
    </div>
  )
}

function WorkUnitPanel({ workUnits }) {
  return (
    <div className="panel">
      <div className="panel-header">Work Units</div>
      <div className="panel-content">
        {workUnits.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📁</div>
            <div className="empty-state-text">No work units claimed</div>
          </div>
        ) : (
          workUnits.map(wu => (
            <WorkUnitItem key={wu.id} workUnit={wu} />
          ))
        )}
      </div>
    </div>
  )
}

function WorkUnitItem({ workUnit }) {
  const hasQueue = workUnit.queue && workUnit.queue.length > 0
  const isAvailable = !workUnit.owner_agent_id

  let className = 'work-unit-item'
  if (isAvailable) className += ' available'
  if (hasQueue) className += ' has-queue'

  return (
    <div className={className}>
      <div className="work-unit-path">{workUnit.path}</div>
      <div className="work-unit-meta">
        <span className="work-unit-type">{workUnit.type}</span>
        <div className="work-unit-owner">
          <span className="dot"></span>
          {workUnit.owner_agent_id
            ? truncateId(workUnit.owner_agent_id)
            : 'Available'}
        </div>
        {workUnit.expires_at && (
          <span title={`Expires: ${workUnit.expires_at}`}>
            TTL: {formatTTL(workUnit.expires_at)}
          </span>
        )}
      </div>

      {hasQueue && (
        <div className="queue-section">
          <div className="queue-label">Queue ({workUnit.queue.length} waiting)</div>
          <div className="queue-list">
            {workUnit.queue.map((entry, idx) => (
              <div key={entry.agent_id} className="queue-item">
                <span className="queue-position">{idx + 1}</span>
                <span>{truncateId(entry.agent_id)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Utilities
function truncateId(id) {
  if (!id) return ''
  if (id.length <= 16) return id
  return id.slice(0, 8) + '...' + id.slice(-6)
}

function formatTime(date) {
  return date.toLocaleTimeString()
}

function formatTTL(expiresAt) {
  const now = new Date()
  const expires = new Date(expiresAt)
  const seconds = Math.max(0, Math.floor((expires - now) / 1000))

  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m`
}

export default App
