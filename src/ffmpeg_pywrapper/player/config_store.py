from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MediaState:
    position: float = 0.0
    audio_stream_index: int | None = None
    subtitle_source: str | int | None = None
    subtitle_delay: float = 0.0
    volume: float = 1.0
    playback_speed: float = 1.0
    updated_at: float = 0.0


def normalize_media_key(path: str | Path) -> str:
    value = Path(path)
    try:
        return str(value.resolve())
    except OSError:
        return str(value)


def load_config(config_path: Path) -> dict[str, Any]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config_path: Path, config: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def recent_files_from_config(config: dict[str, Any]) -> list[Path]:
    recent = config.get("recent_files", [])
    if not isinstance(recent, list):
        return []
    return [Path(item) for item in recent if isinstance(item, str)]


def set_recent_files(config: dict[str, Any], recent_files: list[Path], *, limit: int = 10) -> dict[str, Any]:
    updated = dict(config)
    unique: list[str] = []
    for item in recent_files:
        value = str(Path(item))
        if value not in unique:
            unique.append(value)
    updated["recent_files"] = unique[:limit]
    return updated


def media_state_from_config(config: dict[str, Any], path: str | Path) -> MediaState | None:
    states = config.get("media_state", {})
    if not isinstance(states, dict):
        return None
    raw = states.get(normalize_media_key(path))
    if not isinstance(raw, dict):
        return None
    return MediaState(
        position=_float(raw.get("position"), 0.0),
        audio_stream_index=_optional_int(raw.get("audio_stream_index")),
        subtitle_source=_subtitle_source(raw.get("subtitle_source")),
        subtitle_delay=_float(raw.get("subtitle_delay"), 0.0),
        volume=_float(raw.get("volume"), 1.0),
        playback_speed=_float(raw.get("playback_speed"), 1.0),
        updated_at=_float(raw.get("updated_at"), 0.0),
    )


def set_media_state(config: dict[str, Any], path: str | Path, state: MediaState) -> dict[str, Any]:
    updated = dict(config)
    states = updated.get("media_state", {})
    if not isinstance(states, dict):
        states = {}
    payload = asdict(state)
    payload["updated_at"] = payload["updated_at"] or time.time()
    states[normalize_media_key(path)] = payload
    updated["media_state"] = states
    return updated


def resumable_position(state: MediaState | None, duration: float | None, *, edge_seconds: float = 5.0) -> float | None:
    if state is None or duration is None or duration <= edge_seconds * 2:
        return None
    position = min(max(0.0, state.position), duration)
    if position < edge_seconds or duration - position < edge_seconds:
        return None
    return position


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _subtitle_source(value: object) -> str | int | None:
    return value if isinstance(value, (str, int)) else None
