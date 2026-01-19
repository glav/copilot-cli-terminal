<!-- markdownlint-disable-file -->
# Copilot CLI Multi-Persona UI Input Color - Feature Specification
Version 0.1 | Status Draft | Owner TBD | Team TBD | Target Next | Lifecycle Proposed

## 1. Executive Summary
### Context
The pane REPL currently renders prompts in persona-specific colors, but user-entered input appears in the terminal default color. This makes it harder to visually distinguish user input from Copilot responses, especially in long sessions.

### Goals
- Make user input render in a light gray color distinct from Copilot output.
- Ensure the input color is configurable through the existing UI config system.

## 2. Scope
### In Scope
- Add a configurable `ui.styles.input` token list in `copilot-multi` configuration (TOML/JSON).
- Default input style uses a light gray (e.g., `bright_black`).
- Apply the style to the REPL input line so typed input is visually distinct.

### Out of Scope
- Changing Copilot response colors (handled by Copilot CLI).
- Adding theming support outside the existing config files.

## 3. Requirements
| ID | Requirement | Priority |
|----|-------------|----------|
| R-001 | Provide a default input color that is light gray (e.g., ANSI `bright_black`). | P0 |
| R-002 | Expose input color via `ui.styles.input` in config files. | P0 |
| R-003 | Keep behavior consistent when `ui.color` is disabled (no ANSI). | P0 |

## 4. UX Notes
- Input text should remain readable on dark terminals; default `bright_black` should be validated.
- If the terminal theme renders `bright_black` too dark, users can override via config.

## 5. Configuration Example
```toml
[ui]
color = true

[ui.styles]
input = "bright_black"
```

## 6. Implementation Notes (Non-binding)
- Extend `UiTheme` with an `input` style token list.
- Extend `Ansi` with a method to style input or provide a wrapper for prompt/input rendering.
- Apply the style in the REPL loop when reading input (e.g., prefix using Readline safe markers).

