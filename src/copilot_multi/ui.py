from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from copilot_multi.constants import PERSONAS


_SGR_CODES: dict[str, str] = {
    "reset": "0",
    "bold": "1",
    "dim": "2",
    "underline": "4",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "bright_black": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
}


def _read_toml(path: Path) -> dict:
    try:
        import tomllib  # py>=3.11

        return tomllib.loads(path.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        try:
            import tomli  # type: ignore

            return tomli.loads(path.read_text(encoding="utf-8"))
        except ModuleNotFoundError:
            return {}
    except OSError:
        return {}
    except Exception:
        return {}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except Exception:
        return {}


def _read_config_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".toml":
        return _read_toml(path)
    if suffix == ".json":
        return _read_json(path)
    # Unknown extension: try JSON first.
    data = _read_json(path)
    if data:
        return data
    return _read_toml(path)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _split_style(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        tokens = [str(x).strip() for x in value]
        return [t for t in tokens if t]
    if isinstance(value, str):
        tokens = [t.strip() for t in value.replace(",", " ").split()]
        return [t for t in tokens if t]
    return [str(value).strip()] if str(value).strip() else []


def _sgr_seq(tokens: list[str]) -> str:
    if not tokens:
        return ""
    codes: list[str] = []
    for t in tokens:
        code = _SGR_CODES.get(t)
        if code:
            codes.append(code)
    if not codes:
        return ""
    return "\x1b[" + ";".join(codes) + "m"


@dataclass(frozen=True)
class UiTheme:
    color: bool = True
    header: list[str] = field(default_factory=lambda: ["bold", "cyan"])
    prompt_delim: list[str] = field(default_factory=lambda: ["dim", "white"])
    tips: list[str] = field(default_factory=lambda: ["dim"])
    local: list[str] = field(default_factory=lambda: ["dim", "cyan"])
    error: list[str] = field(default_factory=lambda: ["bold", "red"])
    persona_prompt: dict[str, list[str]] = field(
        default_factory=lambda: {
            "pm": ["bold", "magenta"],
            "impl": ["bold", "blue"],
            "review": ["bold", "green"],
            "docs": ["bold", "yellow"],
        }
    )


@dataclass(frozen=True)
class UiConfig:
    theme: UiTheme

    @staticmethod
    def load(*, repo_root: Path) -> "UiConfig":
        default_theme = UiTheme()
        defaults = {
            "ui": {
                "color": True,
                "styles": {
                    "header": "bold cyan",
                    "prompt_delim": "dim white",
                    "tips": "dim",
                    "local": "dim cyan",
                    "error": "bold red",
                },
                "persona_prompt": {
                    "pm": "bold magenta",
                    "impl": "bold blue",
                    "review": "bold green",
                    "docs": "bold yellow",
                },
            }
        }

        merged = defaults

        # Global user config (XDG).
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            global_dir = Path(xdg_config_home) / "copilot-multi"
        else:
            global_dir = Path.home() / ".config" / "copilot-multi"

        candidates: list[Path] = [
            global_dir / "config.toml",
            global_dir / "config.json",
            repo_root / "copilot-multi.toml",
            repo_root / "copilot-multi.json",
            repo_root / ".copilot-multi" / "config.toml",
            repo_root / ".copilot-multi" / "config.json",
        ]

        # Optional explicit config path (highest precedence).
        explicit = os.environ.get("COPILOT_MULTI_CONFIG")
        if explicit:
            candidates.append(Path(explicit))

        for path in candidates:
            try:
                if not path.exists() or not path.is_file():
                    continue
            except OSError:
                continue
            data = _read_config_file(path)
            if not isinstance(data, dict) or not data:
                continue
            merged = _deep_merge(merged, data)

        ui = merged.get("ui", {}) if isinstance(merged, dict) else {}
        if not isinstance(ui, dict):
            ui = {}

        styles = ui.get("styles", {}) if isinstance(ui.get("styles"), dict) else {}
        persona_prompt = (
            ui.get("persona_prompt", {}) if isinstance(ui.get("persona_prompt"), dict) else {}
        )

        persona_prompt_styles = dict(default_theme.persona_prompt)
        for k, v in persona_prompt.items():
            if not isinstance(k, str) or k not in PERSONAS:
                continue
            tokens = _split_style(v)
            if tokens:
                persona_prompt_styles[k] = tokens

        theme = UiTheme(
            color=bool(ui.get("color", True)),
            header=_split_style(styles.get("header")) or default_theme.header,
            prompt_delim=_split_style(styles.get("prompt_delim")) or default_theme.prompt_delim,
            tips=_split_style(styles.get("tips")) or default_theme.tips,
            local=_split_style(styles.get("local")) or default_theme.local,
            error=_split_style(styles.get("error")) or default_theme.error,
            persona_prompt=persona_prompt_styles,
        )

        return UiConfig(theme=theme)


class Ansi:
    def __init__(self, *, theme: UiTheme, use_readline_markers: bool) -> None:
        self._theme = theme
        self._use_readline_markers = use_readline_markers

    def _wrap_nonprinting(self, s: str) -> str:
        # GNU readline uses \001 and \002 to ignore non-printing sequences.
        if not s:
            return ""
        if not self._use_readline_markers:
            return s
        return "\001" + s + "\002"

    def _style(self, text: str, tokens: list[str]) -> str:
        if not self._theme.color:
            return text
        start = _sgr_seq(tokens)
        if not start:
            return text
        reset = _sgr_seq(["reset"])
        return f"{self._wrap_nonprinting(start)}{text}{self._wrap_nonprinting(reset)}"

    def header_line(self, text: str) -> str:
        return self._style(text, self._theme.header)

    def tip_line(self, text: str) -> str:
        return self._style(text, self._theme.tips)

    def local_prefix(self, text: str = "(local)") -> str:
        return self._style(text, self._theme.local)

    def error_text(self, text: str) -> str:
        return self._style(text, self._theme.error)

    def prompt(self, persona: str) -> str:
        persona_tokens = self._theme.persona_prompt.get(persona) or ["bold", "white"]
        left = self._style(persona, persona_tokens)
        delim = self._style(">", self._theme.prompt_delim)
        return f"{left}{delim} "
