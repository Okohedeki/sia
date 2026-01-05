# Source Directory vs Pip Installation: Pros & Cons

## Current Issue

The current code uses:
```python
SIA_ROOT = Path(__file__).parent.parent.absolute()
HOOKS_SOURCE_DIR = SIA_ROOT / "hooks"
```

This **only works in source directory** because it assumes:
- `cli/main.py` → `parent` = `cli/` → `parent.parent` = repo root
- In pip install: `site-packages/sia_claude/cli/main.py` → `parent.parent` = `site-packages/` ❌

---

## Source Directory Approach

### Installation
```bash
git clone https://github.com/yourorg/sia.git
cd sia
pip install -e .
```

### Pros ✅
1. **Simple Development**: Easy to modify and test changes
2. **Direct Access**: Hooks are in predictable location (`repo/hooks/`)
3. **No Path Resolution**: Works with current `Path(__file__).parent.parent` approach
4. **Version Control**: Users can see/modify source code
5. **Easy Updates**: `git pull` to update
6. **Works for Contributors**: Developers can contribute easily

### Cons ❌
1. **Not Standard**: Users expect `pip install` to work globally
2. **Requires Git**: Users need git installed
3. **Manual Setup**: Users must clone repo first
4. **Multiple Installations**: Each user needs their own clone
5. **Harder Distribution**: Can't publish to PyPI easily
6. **Path Assumptions**: Breaks if repo structure changes

---

## Pip Installation Approach

### Installation
```bash
pip install sia-claude
# or
pip install git+https://github.com/yourorg/sia.git
```

### Pros ✅
1. **Standard Python Way**: Familiar to Python developers
2. **Global Installation**: Install once, use everywhere
3. **Easy Distribution**: Can publish to PyPI
4. **Version Management**: `pip install --upgrade sia-claude`
5. **Virtual Environments**: Works with venv/conda
6. **Professional**: Standard tooling and practices
7. **Dependency Management**: pip handles dependencies automatically

### Cons ❌
1. **Path Resolution Needed**: Must find hooks in installed package
2. **Harder Development**: Need to reinstall after changes
3. **Less Transparent**: Source code in site-packages (but still accessible)
4. **Requires Fix**: Current code doesn't work with pip install

---

## Hybrid Approach (Recommended)

**Best of both worlds**: Support both source directory AND pip installation.

### Implementation Strategy

```python
import importlib.resources
from pathlib import Path

def get_hooks_source_dir() -> Path:
    """Get hooks directory, works for both source and pip install."""
    # Try pip-installed location first
    try:
        # Python 3.9+ way
        with importlib.resources.path('hooks', 'pre_tool_guard.py') as hook_path:
            return hook_path.parent
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    
    # Fallback to source directory (development)
    cli_dir = Path(__file__).parent.absolute()
    hooks_dir = cli_dir.parent / "hooks"
    if hooks_dir.exists():
        return hooks_dir
    
    # Last resort: check if we're in site-packages
    # This shouldn't happen if package is properly installed
    raise FileNotFoundError("Could not find hooks directory")
```

### Alternative: Use `importlib.resources` (Python 3.9+)

```python
import importlib.resources
from pathlib import Path

def get_hooks_source_dir() -> Path:
    """Get hooks directory using importlib.resources."""
    try:
        # Works for pip-installed packages
        package = importlib.resources.files('hooks')
        return Path(str(package))
    except (ModuleNotFoundError, TypeError):
        # Fallback for source directory
        return Path(__file__).parent.parent / "hooks"
```

### Alternative: Copy Hooks at Install Time

**Option A**: Copy hooks to a global location during `sia init`
- Store hooks in `~/.sia/hooks/` or `%APPDATA%/Sia/hooks/`
- `sia init` copies from package to project

**Option B**: Use `pkg_resources` (older but more compatible)

```python
import pkg_resources

def get_hooks_source_dir() -> Path:
    """Get hooks directory using pkg_resources."""
    try:
        hooks_path = pkg_resources.resource_filename('hooks', '')
        return Path(hooks_path)
    except:
        # Fallback to source directory
        return Path(__file__).parent.parent / "hooks"
```

---

## Recommendation: Hybrid with `importlib.resources`

### Why?
1. ✅ Works for both source and pip install
2. ✅ Standard Python approach (Python 3.9+)
3. ✅ No assumptions about directory structure
4. ✅ Proper package resource handling
5. ✅ Fallback to source directory for development

### Implementation

```python
# cli/main.py
import importlib.resources
from pathlib import Path
import sys

def get_hooks_source_dir() -> Path:
    """Get hooks directory, works for both source and pip install."""
    # Method 1: Try pip-installed package (Python 3.9+)
    try:
        if sys.version_info >= (3, 9):
            package = importlib.resources.files('hooks')
            hooks_path = Path(str(package))
            if hooks_path.exists() and (hooks_path / "pre_tool_guard.py").exists():
                return hooks_path
    except (ModuleNotFoundError, TypeError, AttributeError):
        pass
    
    # Method 2: Fallback to source directory (development)
    cli_dir = Path(__file__).parent.absolute()
    hooks_dir = cli_dir.parent / "hooks"
    if hooks_dir.exists() and (hooks_dir / "pre_tool_guard.py").exists():
        return hooks_dir
    
    # Method 3: Try pkg_resources (older Python)
    try:
        import pkg_resources
        hooks_path = Path(pkg_resources.resource_filename('hooks', ''))
        if hooks_path.exists():
            return hooks_path
    except:
        pass
    
    raise FileNotFoundError(
        "Could not find hooks directory. "
        "Make sure sia-claude is properly installed: pip install sia-claude"
    )

# Update the constant
HOOKS_SOURCE_DIR = get_hooks_source_dir()
```

---

## User Experience Comparison

### Source Directory
```bash
# User workflow
git clone https://github.com/yourorg/sia.git
cd sia
pip install -e .
cd /path/to/my-project
sia init
sia start
```

### Pip Installation
```bash
# User workflow
pip install sia-claude
cd /path/to/my-project
sia init
sia start
```

**Pip is simpler for end users!**

---

## Decision Matrix

| Factor | Source Directory | Pip Install | Winner |
|--------|-----------------|------------|--------|
| **Ease of Use** | Requires git clone | One command | 🏆 Pip |
| **Development** | Easy to modify | Need reinstall | 🏆 Source |
| **Distribution** | Manual | PyPI | 🏆 Pip |
| **Standard Practice** | Non-standard | Standard | 🏆 Pip |
| **Version Updates** | git pull | pip upgrade | 🏆 Pip |
| **Code Transparency** | Full access | Still accessible | 🏆 Source |
| **Path Resolution** | Simple | Needs fix | 🏆 Source |

**Winner: Hybrid approach** - Support both, but optimize for pip install.

---

## Recommended Solution

1. **Fix path resolution** to work with pip install (use `importlib.resources`)
2. **Keep source directory support** for development
3. **Publish to PyPI** for easy distribution
4. **Document both methods** in README

### Updated Installation Instructions

```markdown
## Installation

### Option 1: Pip Install (Recommended)
```bash
pip install sia-claude
```

### Option 2: Development Install
```bash
git clone https://github.com/yourorg/sia.git
cd sia
pip install -e .
```

### Setup Your Project
```bash
cd /path/to/your-project
sia init      # Sets up hooks
sia start     # Starts daemon
```

Then open http://localhost:7432 in your browser!
```

---

## Summary

**Best Approach**: Hybrid with `importlib.resources`
- ✅ Works for both source and pip install
- ✅ Standard Python practices
- ✅ Easy distribution via PyPI
- ✅ Still supports development workflow
- ✅ Requires fixing current path resolution code

