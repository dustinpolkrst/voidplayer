from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any


DEFAULT_THEME = "default"
PACKAGED_THEMES = {
    "default": "VoidPlayer",
    "catppuccin-frappe": "Catppuccin Frappe",
    "catppuccin-macchiato": "Catppuccin Macchiato",
    "catppuccin-mocha": "Catppuccin Mocha",
}
TOKEN_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")


class ThemeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    path: str
    tokens: dict[str, str]
    template: str


def load_theme(name: str = DEFAULT_THEME, theme_path: Path | None = None) -> Theme:
    if theme_path is not None:
        path = theme_path.resolve()
        token_path = path / "theme.toml"
        template_path = path / "style.qss"
        if not token_path.exists():
            raise ThemeError(f"Theme token file not found: {token_path}")
        if not template_path.exists():
            raise ThemeError(f"Theme stylesheet template not found: {template_path}")
        token_text = token_path.read_text(encoding="utf-8")
        template = template_path.read_text(encoding="utf-8")
        source = str(path)
    else:
        path = files(__package__).joinpath("themes", name)
        token_path = path.joinpath("theme.toml")
        template_path = path.joinpath("style.qss")
        if not token_path.is_file():
            raise ThemeError(f"Theme token file not found: {token_path}")
        if not template_path.is_file():
            raise ThemeError(f"Theme stylesheet template not found: {template_path}")
        token_text = token_path.read_text(encoding="utf-8")
        template = template_path.read_text(encoding="utf-8")
        source = str(path)

    try:
        raw_tokens = tomllib.loads(token_text)
    except tomllib.TOMLDecodeError as exc:
        raise ThemeError(f"Theme token file is invalid TOML: {source}") from exc

    tokens = _flatten_tokens(raw_tokens)
    tokens.setdefault("asset.chevron_down", _qss_url(files(__package__).joinpath("assets", "chevron-down.svg")))
    _validate_tokens(tokens, template, source)
    return Theme(name=name, path=source, tokens=tokens, template=template)


def render_stylesheet(theme: Theme) -> str:
    def replace_token(match: re.Match[str]) -> str:
        token_name = match.group(1)
        try:
            return theme.tokens[token_name]
        except KeyError as exc:
            raise ThemeError(f"Theme '{theme.name}' is missing token '{token_name}'") from exc

    return TOKEN_PATTERN.sub(replace_token, theme.template)


def _flatten_tokens(raw_tokens: dict[str, Any], prefix: str = "") -> dict[str, str]:
    tokens: dict[str, str] = {}
    for key, value in raw_tokens.items():
        token_name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            tokens.update(_flatten_tokens(value, token_name))
        elif isinstance(value, (str, int, float)):
            tokens[token_name] = str(value)
        else:
            raise ThemeError(f"Theme token '{token_name}' must be a string or number")
    return tokens


def _validate_tokens(tokens: dict[str, str], template: str, source: str) -> None:
    required = set(TOKEN_PATTERN.findall(template))
    missing = sorted(required - tokens.keys())
    if missing:
        joined = ", ".join(missing)
        raise ThemeError(f"Theme token file {source} is missing required token(s): {joined}")


def _qss_url(path: Any) -> str:
    return str(path).replace("\\", "/")
