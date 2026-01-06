authentication 
terraform 
vim
kubernetes/docker yaml files

  1. Start the control plane:
  conda activate Sia
  cd H:/Sia/backend
  sia start
  2. In another project with .mcp.json configured, use Claude Code:
  Use sia_set_plan to create a plan with these steps:
  1. Read the config file
  2. Update the settings
  3. Save changes

  Then use sia_update_step to mark step 1 as in_progress with files ["config.json"]
  Then use sia_log_step to add a log "Found 3 settings to update"
  3. Check the UI at http://localhost:8000 - you should see:
    - The plan with step-by-step progress
    - Work units appearing in the right sidebar
    - Logs under each step

  Let me know what you see and if anything needs adjustment!

    - API endpoints: DELETE /api/agents/{id} and DELETE /api/sessions/{session_id}

  To test:
  1. Restart the Sia server: sia start
  2. Start a new Claude session in intro-to-C
  3. The agent should show the working directory
  4. When you exit Claude, the agent will auto-disappear after ~60 seconds (or click × to remove immediately)