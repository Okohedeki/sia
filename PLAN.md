# Sia Build Plan

## Tech Stack
- Backend: Python + FastAPI + Claude Agent SDK
- Frontend: React + TypeScript + Vite
- Real-time: WebSockets

---

## Step 1: Project Setup
**Backend:** Python project, FastAPI app, health endpoint, CORS
**Frontend:** React app, header, connection status indicator
**Verify:** Frontend shows "Connected" to backend

---

## Step 2: Basic Agent Runner
**Backend:** Create SiaAgent class with Claude SDK, `/agents/run` endpoint
**Frontend:** Task input, Run button, response display
**Verify:** Type task → Run → See agent response

---

## Step 3: Agent Registry & States
**Backend:** Agent ID generation, states (pending/running/completed/failed), `/agents` endpoints
**Frontend:** Agent list sidebar, status badges, click to view details
**Verify:** Multiple agents visible with live status

---

## Step 4: WebSocket Updates
**Backend:** `/ws` endpoint, broadcast agent state changes
**Frontend:** Real-time agent list updates, event toasts
**Verify:** No polling, instant updates

---

## Step 5: Work Unit Model
**Backend:** WorkUnit class (id, type, path, locked_by, queue), registry, `/work-units` endpoints
**Frontend:** Work Units tab, table view with status colors
**Verify:** See tracked files/processes

---

## Step 6: Lock Service
**Backend:** LockService class with claim/release/TTL expiration
**Frontend:** Lock status on work units, queue display, TTL countdown
**Verify:** Locks acquired and expire correctly

---

## Step 7: Sia Claim Tool
**Backend:** `sia_claim` and `sia_release` tools for agents
**Frontend:** Show agent claims, visual links between agents and resources
**Verify:** Agent claims resource via tool call

---

## Step 8: Blocking & Queuing
**Backend:** Agents queue when resource locked, `blocked` state, auto-resume on release
**Frontend:** Blocked status badge, "Waiting for" display, queue order
**Verify:** Second agent waits, runs when first releases

---

## Step 9: Sia Read Tool
**Backend:** `sia_read` tool (no lock required), artifact logging
**Frontend:** Artifacts panel, file read entries with preview
**Verify:** Agent reads file, UI shows what was read

---

## Step 10: Sia Write Tool
**Backend:** `sia_write` tool (requires lock), diff generation
**Frontend:** Diff view with syntax highlighting
**Verify:** Agent writes file, UI shows before/after diff

---

## Step 11: Sia Run Tool
**Backend:** Process resources, `sia_run` tool, command capture
**Frontend:** Command artifacts with exit code, stdout/stderr
**Verify:** Agent runs command, UI shows output

---

## Step 12: Sia Spawn Tool
**Backend:** `sia_spawn` tool creates child agent, parent-child tracking
**Frontend:** Agent hierarchy tree view, collapsible
**Verify:** Parent spawns child, tree shows relationship

---

## Step 13: Subagent Lifecycle
**Backend:** `sia_check_agent`, `sia_wait_agent` tools, child completion flow
**Frontend:** Child status inline, aggregate progress
**Verify:** Parent waits for child, gets result

---

## Step 14: Resource Delegation
**Backend:** Claims transfer from parent to child, return on completion
**Frontend:** Delegation flow visualization
**Verify:** Parent delegates claim, child uses it, returns on done

---

## Step 15: Execution Timeline
**Backend:** Event log per agent, `/agents/{id}/timeline` endpoint
**Frontend:** Timeline view with event cards, filtering
**Verify:** See complete execution history

---

## Step 16: Global Activity View
**Backend:** Cross-agent timeline, streaming
**Frontend:** Activity tab, all events interleaved, live updates
**Verify:** Watch all agents in real-time

---

## Step 17: Execution Replay
**Backend:** State snapshots, `/agents/{id}/replay` endpoint
**Frontend:** Replay controls, timeline scrubber
**Verify:** Step through past execution

---

## Step 18: Execution Plans
**Backend:** `sia_plan` tool for declaring intent
**Frontend:** Plan view before execution, approve/reject
**Verify:** Agent declares resources upfront

---

## Step 19: Priority Scheduling
**Backend:** Agent priorities, scheduling policies
**Frontend:** Priority selector, queue reordering
**Verify:** High priority agent jumps queue

---

## Step 20: Deadlock Detection
**Backend:** Cycle detection, victim selection, forced release
**Frontend:** Deadlock warning, cycle visualization
**Verify:** System recovers from deadlock

---

## After Each Step
1. Run backend + frontend together
2. Test the new feature end-to-end
3. Commit working code
4. Move to next step
