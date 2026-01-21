# Per-Persona Agent Instructions Guide

## Overview

Copilot-multi supports per-persona custom instructions that enforce role-based boundaries. Each persona (PM, Impl, Review, Docs) operates with specific capabilities and constraints defined in instruction files.

## How It Works

### The Mechanism

When you start copilot-multi, each persona pane:
1. Changes to its own directory (`.copilot-persona-dirs/{persona}/`)
2. Loads custom instructions from `AGENTS.md` in that directory
3. Copilot CLI reads the `AGENTS.md` file automatically from the current working directory

This leverages copilot CLI's built-in feature for loading custom instructions from the working directory.

### Directory Structure

```
.copilot-persona-dirs/          # Auto-generated when you run copilot-multi start
├── pm/
│   ├── AGENTS.md → ../../.agent/pm-persona.md      # Symlink to source file
│   └── repo → ../..                                 # Symlink to repository root
├── impl/
│   ├── AGENTS.md → ../../.agent/impl-persona.md
│   └── repo → ../..
├── review/
│   ├── AGENTS.md → ../../.agent/review-persona.md
│   └── repo → ../..
└── docs/
    ├── AGENTS.md → ../../.agent/docs-persona.md
    └── repo → ../..
```

**Note**: `.copilot-persona-dirs/` is gitignored and auto-generated. You don't need to create it manually.

## Persona Roles

### PM (Project Manager)
- **Can**: Write specifications, plans, requirements, implementation strategies
- **Cannot**: Modify code files, run builds, install dependencies
- **File**: `.agent/pm-persona.md`

### Impl (Implementation Engineer)
- **Can**: Write/edit code, fix bugs, run tests, install dependencies
- **Cannot**: Write project plans (that's PM's job)
- **File**: `.agent/impl-persona.md`

### Review (Code Review Engineer)
- **Can**: Read all files, provide feedback, run analysis tools
- **Cannot**: Modify any files, auto-fix issues, commit changes
- **File**: `.agent/review-persona.md`

### Docs (Technical Writer / Documentor)
- **Can**: Write/edit documentation files (.md, .txt, .rst)
- **Cannot**: Modify source code, tests, or build configurations
- **File**: `.agent/docs-persona.md`

## Usage

### Starting with Persona Instructions (Default)

```bash
uv run copilot-multi start
```

Each persona will automatically load its custom instructions.

### Starting without Persona Instructions

```bash
uv run copilot-multi start --no-persona-agents
```

All personas behave the same, using only repository-level `AGENTS.md` (if it exists).

### Customizing Persona Instructions

1. **Edit the source file**:
   ```bash
   # Edit PM persona instructions
   nano .agent/pm-persona.md
   
   # Or use your preferred editor
   code .agent/impl-persona.md
   ```

2. **Restart the session** for changes to take effect:
   ```bash
   uv run copilot-multi stop
   uv run copilot-multi start
   ```

**Note**: Because files are symlinked, your edits to `.agent/*.md` are immediately reflected in `.copilot-persona-dirs/*/AGENTS.md`.

## Accessing Repository Files

When working from a persona directory, use these methods to access repository files:

### Method 1: Relative Paths
```
../../src/app.py
../../README.md
```

### Method 2: Repo Symlink (Recommended)
```
repo/src/app.py
repo/README.md
```

### Method 3: Absolute Paths
```
/workspaces/your-repo/src/app.py
```

Most file operations work automatically regardless of method. The pane REPL handles path resolution.

## Troubleshooting

### Issue: Persona instructions not being loaded

**Symptoms**: Persona behaves generically, doesn't follow role constraints

**Solutions**:
1. Verify source files exist:
   ```bash
   ls -la .agent/
   # Should show pm-persona.md, impl-persona.md, review-persona.md, docs-persona.md
   ```

2. Check that persona directories were created:
   ```bash
   ls -la .copilot-persona-dirs/
   # Should show pm/, impl/, review/, docs/ directories
   ```

3. Verify symlinks are correct:
   ```bash
   ls -la .copilot-persona-dirs/pm/
   # Should show: AGENTS.md -> ../../.agent/pm-persona.md
   ```

4. Restart the session:
   ```bash
   uv run copilot-multi stop
   uv run copilot-multi start
   ```

### Issue: Cannot access repository files

**Symptoms**: "File not found" errors when trying to view/edit files

**Solutions**:
1. Use the `repo/` symlink:
   ```
   view repo/src/app.py
   ```

2. Or use relative paths:
   ```
   view ../../src/app.py
   ```

3. Check if repo symlink exists:
   ```bash
   ls -la .copilot-persona-dirs/pm/repo
   # Should show: repo -> ../..
   ```

4. If symlink is missing, restart the session:
   ```bash
   uv run copilot-multi stop
   uv run copilot-multi start
   ```

### Issue: Persona boundaries not enforced

**Symptoms**: PM persona can edit code, Review persona can modify files

**Solutions**:
1. Check that you didn't use `--no-persona-agents` flag

2. Verify persona instructions are clear:
   ```bash
   head -30 .agent/pm-persona.md
   # Should show role, responsibilities, and restrictions
   ```

3. Test if instructions are loaded:
   - In any pane, ask: "What are your instructions?"
   - Ask: "Can you edit code files?"
   - PM should say NO, Impl should say YES

4. Review persona instruction files for clarity:
   - Ensure "Restricted Operations" section is explicit
   - Check that role boundaries are clear
   - Verify examples are provided

### Issue: Symlinks not working (Windows)

**Symptoms**: AGENTS.md files are regular files, not symlinks

**Impact**: Low - copies work fine, but require manual sync when editing

**Solutions**:
1. This is expected on Windows without developer mode
2. The implementation falls back to copying files
3. To update persona instructions:
   - Edit `.agent/{persona}-persona.md`
   - Restart copilot-multi session
   - Files will be recopied automatically

**Alternative**: Enable Windows developer mode for symlink support

### Issue: Want to verify which instructions are active

**Solution**: Ask in any pane:
```
What are your role and responsibilities? What can and cannot you do?
```

The persona should respond with details from its AGENTS.md file.

## Advanced Topics

### Multiple Repositories

Each repository gets its own `.copilot-persona-dirs/`. Persona instructions are repository-specific.

### Custom Persona Instructions

You can modify the instruction files to:
- Change role boundaries
- Add new capabilities
- Restrict additional operations
- Customize tone or style

Just edit `.agent/{persona}-persona.md` and restart the session.

### Sharing Persona Instructions

To share your persona configurations with team members:

1. **Commit source files** (already in git):
   ```bash
   git add .agent/*-persona.md
   git commit -m "Update persona instructions"
   git push
   ```

2. **Don't commit generated directories**:
   - `.copilot-persona-dirs/` is already gitignored
   - It's auto-generated on each machine

3. Team members just need to:
   ```bash
   git pull
   uv run copilot-multi start
   ```

### Disabling Specific Personas

Currently, you cannot disable individual personas. You can either:
- Use all personas with instructions (`copilot-multi start`)
- Use all personas without instructions (`copilot-multi start --no-persona-agents`)

To customize which personas have instructions, edit their source files to remove restrictions.

## FAQ

**Q: Do I need to create `.copilot-persona-dirs/` manually?**  
A: No, it's auto-generated when you run `copilot-multi start`.

**Q: Can I customize the directory location?**  
A: Not currently. The directory is always `.copilot-persona-dirs/` in the repository root.

**Q: What happens if I delete `.copilot-persona-dirs/`?**  
A: It will be recreated automatically next time you run `copilot-multi start`.

**Q: Can I use different persona instructions per project?**  
A: Yes! Each repository has its own `.agent/` directory. Customize as needed per project.

**Q: Do persona instructions work with the GitHub Copilot extension in VS Code?**  
A: No, this feature is specific to copilot-multi. The VS Code extension uses different configuration.

**Q: Can I add more personas?**  
A: Not without modifying copilot-multi source code. The four personas (PM, Impl, Review, Docs) are built-in.

**Q: Performance impact?**  
A: Negligible (< 10ms overhead). Symlink creation is instant, directory changes are fast.

## See Also

- [Main README](../README.md) - copilot-multi overview
- [AGENTS.md](../AGENTS.md) - Repository-level custom instructions
- Individual persona files:
  - [PM Persona](.agent/pm-persona.md)
  - [Impl Persona](.agent/impl-persona.md)
  - [Review Persona](.agent/review-persona.md)
  - [Docs Persona](.agent/docs-persona.md)
