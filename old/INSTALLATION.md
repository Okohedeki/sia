# Installation Guide

## Quick Install (Pip)

```bash
pip install sia-claude
```

## Development Install

```bash
git clone https://github.com/yourorg/sia.git
cd sia
pip install -e .
```

## Setup Your Project

After installation, set up Sia for your project:

```bash
cd /path/to/your-project
sia init      # Creates .claude/hooks/ and .claude/settings.json
sia start     # Starts the coordination daemon
sia ui        # Opens dashboard in browser (http://localhost:7432)
```

## Verify Installation

```bash
# Check if sia command is available
sia --help

# Check if hooks were installed correctly
ls .claude/hooks/
# Should show: pre_tool_guard.py, post_tool_telemetry.py

# Check daemon status
sia status
```

## Troubleshooting

### "Could not find hooks directory"

If you see this error, the package may not be installed correctly:

```bash
# Reinstall
pip uninstall sia-claude
pip install sia-claude

# Or if installing from source
pip install -e .
```

### "Command 'sia' not found"

Make sure the installation added `sia` to your PATH:

```bash
# Check where it's installed
python -m pip show sia-claude

# On Linux/Mac, you may need to add to PATH
# On Windows, pip should handle this automatically
```

### Hooks not working in Claude Code

1. Verify `.claude/settings.json` exists and has hooks configured
2. Check that hook files are executable:
   ```bash
   chmod +x .claude/hooks/*.py
   ```
3. Make sure the daemon is running: `sia status`

## Building for Distribution

To build a wheel for PyPI:

```bash
pip install build
python -m build
```

This creates `dist/sia_claude-0.1.0-py3-none-any.whl` which can be uploaded to PyPI.

