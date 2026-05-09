from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

TIMING_PATTERN = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)


class SubtitleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SubtitleCue:
    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    source: Path
    cues: tuple[SubtitleCue, ...]

    def text_at(self, timestamp: float) -> str:
        for cue in self.cues:
            if cue.start <= timestamp <= cue.end:
                return cue.text
        return ""


def load_subtitles(path: str | Path) -> SubtitleTrack:
    source = Path(path)
    text = source.read_text(encoding="utf-8-sig")
    suffix = source.suffix.lower()
    if suffix == ".srt":
        cues = parse_srt(text)
    elif suffix == ".vtt":
        cues = parse_vtt(text)
    elif suffix == ".ass":
        cues = parse_ass(text)
    else:
        raise SubtitleError(f"Unsupported subtitle file: {source}")
    if not cues:
        raise SubtitleError(f"No subtitle cues found: {source}")
    return SubtitleTrack(source=source, cues=tuple(cues))


def parse_srt(text: str) -> list[SubtitleCue]:
    return _parse_timed_blocks(text)


def parse_vtt(text: str) -> list[SubtitleCue]:
    lines = [line for line in text.splitlines() if not line.strip().startswith(("WEBVTT", "NOTE"))]
    return _parse_timed_blocks("\n".join(lines))


def parse_ass(text: str) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        fields = line.split(",", 9)
        if len(fields) < 10:
            continue
        start = _parse_ass_time(fields[1])
        end = _parse_ass_time(fields[2])
        body = re.sub(r"\{[^}]*\}", "", fields[9]).replace(r"\N", "\n")
        cues.append(SubtitleCue(start=start, end=end, text=_clean_text(body)))
    return cues


def _parse_timed_blocks(text: str) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_index = next((index for index, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIMING_PATTERN.search(lines[timing_index])
        if match is None:
            continue
        body = "\n".join(lines[timing_index + 1 :])
        cues.append(
            SubtitleCue(
                start=_parse_timestamp(match.group("start")),
                end=_parse_timestamp(match.group("end")),
                text=_clean_text(body),
            )
        )
    return cues


def _parse_timestamp(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)


def _parse_ass_time(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)


def _clean_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return html.unescape(without_tags).strip()
