# Pushing Sia to GitHub

## Step-by-Step Instructions

### 1. Initialize Git Repository (if not already done)

```bash
cd H:\Sia
git init
```

### 2. Create a GitHub Repository

1. Go to https://github.com/new
2. Repository name: `sia` (or `sia-claude`)
3. Description: "Work Unit Coordination for Claude Code multi-agent workflows"
4. Choose Public or Private
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

### 3. Add All Files

```bash
# Add all files
git add .

# Check what will be committed
git status
```

### 4. Create Initial Commit

```bash
git commit -m "Initial commit: Sia - Work Unit Coordination for Claude Code"
```

### 5. Add GitHub Remote

Replace `YOUR_USERNAME` with your GitHub username:

```bash
git remote add origin https://github.com/YOUR_USERNAME/sia.git
```

Or if you prefer SSH:

```bash
git remote add origin git@github.com:YOUR_USERNAME/sia.git
```

### 6. Push to GitHub

```bash
# Push to main branch
git branch -M main
git push -u origin main
```

## Complete Command Sequence

```bash
cd H:\Sia

# Initialize git (if needed)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Sia - Work Unit Coordination for Claude Code"

# Add remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/sia.git

# Push
git branch -M main
git push -u origin main
```

## After Pushing

### Update README with Your GitHub URL

Edit `README.md` and `pyproject.toml` to replace placeholder URLs:

```markdown
# In README.md
git clone https://github.com/YOUR_USERNAME/sia.git
```

```toml
# In pyproject.toml
[project.urls]
Homepage = "https://github.com/YOUR_USERNAME/sia"
Documentation = "https://github.com/YOUR_USERNAME/sia#readme"
Repository = "https://github.com/YOUR_USERNAME/sia"
```

Then commit and push again:

```bash
git add README.md pyproject.toml
git commit -m "Update GitHub URLs"
git push
```

## Future Updates

After making changes:

```bash
git add .
git commit -m "Description of changes"
git push
```

## Publishing to PyPI (Optional)

Once on GitHub, you can publish to PyPI:

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Upload to PyPI (requires PyPI account)
twine upload dist/*
```

Or use GitHub Actions for automatic publishing on releases.

