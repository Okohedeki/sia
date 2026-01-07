1. Distributed Tracing for Agent Runs (Non-negotiable)
Feature: Agent Run Traces

One trace per run

Root span = run

Child spans = agents / subagents

Leaf spans = steps, tool calls, workspace mutations

Why it matters
This is the backbone. Without traces, everything else is UI noise.

UI

APM-style trace waterfall

Expand/collapse agents

Duration, status, error markers

2. Temporal Visualization (Time Is the Primary Axis)
Feature: Unified Timeline

All agents aligned on a single time axis

Visible concurrency

Gaps = waiting / blocked / idle

Color-coded by agent or state

Why
This answers:

“What happened when?”

Most agent UIs hide time completely — that’s fatal for debugging.

3. Plan ↔ Execution Visualization (But Not Judging)
Feature: Plan Overlay

Display declared plan steps (if available)

Overlay actual execution steps on the same timeline

Highlight:

skipped steps

reordered steps

inserted steps

Important
You are not scoring correctness.
You are showing divergence.

This is observation, not evaluation.

4. Agent Interaction Graph (This Is Big)
Feature: Agent Dependency & Interaction Graph

Nodes = agents / subagents

Edges = spawn, delegation, dependency, blocking

Temporal context (edge shows when it happened)

Why
Multi-agent systems fail because interactions are invisible.

This lets users see:

fan-out

bottlenecks

critical agents

cascade failures

5. Shared Workspace Visualization (Not Enforcement)
Feature: Workspace Impact Map

Files / directories as nodes

Agents as nodes

Edges = read / write / modify

Temporal layering

This answers

“Which agents touched the same things?”

Even without locking, this is hugely valuable.

6. Contention & Blocking Visualization
Feature: Blocking & Waiting States

Explicit “blocked” spans in traces

Who is blocking whom

What resource caused the block

How long it lasted

UI

Blocked spans in red / amber

Hover to see “waiting on X”

This is execution observability, not orchestration.

7. Artifact-Aware Trace Inspection
Feature: Trace → Artifact Linking

From any span, users can open:

file diffs

command output

errors

logs at that moment in time

Why
Observability without artifacts forces users back to terminals.

This keeps debugging in one place.

8. Replay / Scrub Mode (Datadog-Level UX)
Feature: Time Scrubber

Drag a cursor across the timeline

UI updates to show:

active agents

workspace state

last known artifacts

Important
Replay ≠ re-execution.
You’re replaying state, not rerunning agents.

This is forensics, not automation.

9. Metrics Derived From Traces (Only Structural Metrics)

You should include metrics, but only those derivable from traces, not judgments.

Examples:

run duration

agent active vs blocked time

concurrency level

steps per run

files touched per run

error frequency

retry counts

These are descriptive, not evaluative.

10. Visualization-Driven Alerts (Optional but Powerful)

Alerts based on observable structure, not correctness:

“Run exceeded historical duration”

“Agent blocked > N seconds”

“More than X agents touched same file”

“Plan drift occurred”

“Unexpected fan-out depth”

This keeps you aligned with observability, not policy.