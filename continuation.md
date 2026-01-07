1. Explicit Plan View (Not Chat)

A dedicated panel that shows:

ordered steps

step status: pending / running / done / skipped / failed

step owner (agent or subagent)

required resources (files, processes)

expected artifacts

Think:

Task graph, not conversation.

2. Plan vs Execution Diff

A simple comparison:

Planned: edit A → edit B → run tests

Executed: edit A → edit C → run tests → edit B

This alone would eliminate 50% of “the agent surprised me” complaints.

3. Live “Why This Step” Inspector

Click any step and see:

why it was chosen

what alternatives existed

what signal triggered it

This doesn’t require deep introspection — just structured metadata.

4. Agent Responsibility Map

Show:

which agent proposed each step

which agent executed it

which agent approved or modified it

This matters enormously in shared workspaces.

5. Parallelism Awareness

Expose:

steps that could run in parallel

steps currently blocked

steps waiting on other agents

This turns multi-agent work from “chaos” into “coordination.”

6. Uncertainty / Confidence Indicators

Per step:

high confidence

medium confidence

exploratory / speculative

Users instinctively know how to act when this is visible.

7. Shared Workspace Impact Summary

For a given plan:

which files will be touched

which files were actually touched

which agents touched them

in what order

This bridges plan management with your work-unit concept perfectly.