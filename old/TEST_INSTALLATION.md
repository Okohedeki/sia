# Testing Sia Installation

## Quick Test Steps

### 1. Install from Local Build

```bash
# From the Sia directory
cd H:\Sia
pip install dist/sia_claude-0.1.0-py3-none-any.whl
```

### 2. Test in a New Project

```bash
# Create a test project directory
cd /path/to/some/other/project
# or
mkdir C:\temp\sia-test-project
cd C:\temp\sia-test-project

# Initialize Sia
sia init

# Verify hooks were created
ls .claude/hooks/
# Should show: pre_tool_guard.py, post_tool_telemetry.py

# Check settings.json
cat .claude/settings.json
# Should have PreToolUse and PostToolUse hooks configured

# Start the daemon
sia start

# Check status
sia status

# Open UI (if frontend is ready)
sia ui
# Or manually: http://localhost:7432
```

### 3. Test Hook Path Resolution

The hooks should be able to find the daemon. Test by checking the hook files:

```bash
# Check that hooks reference the correct paths
cat .claude/hooks/pre_tool_guard.py | head -30
```

### 4. Test Daemon API

```bash
# Health check
curl http://127.0.0.1:7432/health

# Get state
curl http://127.0.0.1:7432/work-units/state
```

## Uninstall for Clean Test

```bash
pip uninstall sia-claude -y
```

## Rebuild After Changes

```bash
cd H:\Sia
python -m build
pip install --force-reinstall dist/sia_claude-0.1.0-py3-none-any.whl
```

## Common Issues

### "Command 'sia' not found"
- Make sure pip install completed successfully
- Check: `python -m pip show sia-claude`
- Try: `python -m cli.main init` (if entry point didn't work)

### "Could not find hooks directory"
- Make sure hooks package is installed: `python -c "import hooks; print(hooks.__file__)"`
- Reinstall the package

### "Daemon won't start"
- Check if port 7432 is already in use
- Check logs: `sia logs`
- Try: `sia stop` then `sia start`


