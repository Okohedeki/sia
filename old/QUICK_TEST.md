# Quick Test Guide

## Ready to Test! 🚀

Your package is built and ready. Here's how to test it on another repo:

### Step 1: Install the Package

```bash
# From H:\Sia directory
pip install dist/sia_claude-0.1.0-py3-none-any.whl
```

### Step 2: Test in Another Project

```bash
# Navigate to your test project
cd /path/to/your/test-project

# Initialize Sia (creates .claude/hooks/ and settings.json)
sia init

# Start the daemon
sia start

# Check it's running
sia status

# Open dashboard (or visit http://localhost:7432)
sia ui
```

### Step 3: Verify Everything Works

```bash
# Check hooks were created
ls .claude/hooks/
# Should see: pre_tool_guard.py, post_tool_telemetry.py

# Check settings.json
cat .claude/settings.json
# Should have PreToolUse and PostToolUse hooks

# Test API
curl http://127.0.0.1:7432/health
# Should return: {"status":"healthy","agents_count":0,"work_units_count":0}
```

### What's Included

✅ **Backend daemon** - FastAPI server on port 7432  
✅ **CLI tool** - `sia` command with init/start/stop/status/ui  
✅ **Hooks** - PreToolUse and PostToolUse for Claude Code  
✅ **Pip install support** - Works from installed package  

### Files Created by `sia init`

```
your-project/
└── .claude/
    ├── settings.json          # Hook configuration
    └── hooks/
        ├── pre_tool_guard.py  # Claims work units
        └── post_tool_telemetry.py  # Releases work units
```

### Next Steps

1. Test in a real project with Claude Code
2. Use multiple agents/subagents to see coordination
3. Check the dashboard at http://localhost:7432
4. Monitor work units and queues

### Troubleshooting

**"sia: command not found"**
- Make sure pip install completed: `pip show sia-claude`
- Try: `python -m cli.main init`

**"Could not find hooks directory"**
- Reinstall: `pip install --force-reinstall dist/sia_claude-0.1.0-py3-none-any.whl`

**Port 7432 already in use**
- Stop existing daemon: `sia stop`
- Or use different port (requires code change)


