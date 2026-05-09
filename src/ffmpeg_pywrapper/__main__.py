from __future__ import annotations

import argparse
import json
from pathlib import Path

from .commands import convert, thumbnail, trim
from .errors import FFmpegError
from .media import MediaInfo, StreamInfo, describe_media
from .probe import probe


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    try:
        return args.handler(args)
    except FFmpegError as exc:
        parser.exit(1, f"{exc}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ffmpeg-pywrapper")
    subparsers = parser.add_subparsers(dest="command")

    probe_parser = subparsers.add_parser("probe", help="Print ffprobe metadata")
    probe_parser.add_argument("input", type=Path)
    probe_parser.add_argument("--json", action="store_true", help="Emit JSON metadata")
    probe_parser.set_defaults(handler=_probe_command)

    describe_parser = subparsers.add_parser("describe", help="Print a typed media summary")
    describe_parser.add_argument("input", type=Path)
    describe_parser.set_defaults(handler=_describe_command)

    convert_parser = subparsers.add_parser("convert", help="Convert media")
    convert_parser.add_argument("input", type=Path)
    convert_parser.add_argument("output", type=Path)
    convert_parser.add_argument("--video-codec")
    convert_parser.add_argument("--audio-codec")
    convert_parser.add_argument("--overwrite", action="store_true")
    convert_parser.set_defaults(handler=_convert_command)

    trim_parser = subparsers.add_parser("trim", help="Trim media")
    trim_parser.add_argument("input", type=Path)
    trim_parser.add_argument("output", type=Path)
    trim_parser.add_argument("--start")
    trim_parser.add_argument("--duration")
    trim_parser.add_argument("--overwrite", action="store_true")
    trim_parser.set_defaults(handler=_trim_command)

    thumbnail_parser = subparsers.add_parser("thumbnail", help="Extract a video thumbnail")
    thumbnail_parser.add_argument("input", type=Path)
    thumbnail_parser.add_argument("output", type=Path)
    thumbnail_parser.add_argument("--timestamp", required=True)
    thumbnail_parser.add_argument("--overwrite", action="store_true")
    thumbnail_parser.set_defaults(handler=_thumbnail_command)
    return parser


def _probe_command(args: argparse.Namespace) -> int:
    result = probe(args.input)
    print(json.dumps(result.data, indent=2))
    return 0


def _describe_command(args: argparse.Namespace) -> int:
    print(_format_media_info(describe_media(args.input)))
    return 0


def _convert_command(args: argparse.Namespace) -> int:
    convert(args.input, args.output, video_codec=args.video_codec, audio_codec=args.audio_codec, overwrite=args.overwrite)
    return 0


def _trim_command(args: argparse.Namespace) -> int:
    trim(args.input, args.output, start=args.start, duration=args.duration, overwrite=args.overwrite)
    return 0


def _thumbnail_command(args: argparse.Namespace) -> int:
    thumbnail(args.input, args.output, timestamp=args.timestamp, overwrite=args.overwrite)
    return 0


def _format_media_info(info: MediaInfo) -> str:
    lines = [f"path: {info.path}", f"duration: {info.duration}", f"streams: {len(info.streams)}"]
    for stream in info.streams:
        lines.append(f"  {_format_stream(stream)}")
    return "\n".join(lines)


def _format_stream(stream: StreamInfo) -> str:
    details = [f"#{stream.index}", stream.codec_type, stream.codec_name or "unknown"]
    if stream.language:
        details.append(f"lang={stream.language}")
    if stream.width and stream.height:
        details.append(f"{stream.width}x{stream.height}")
    if stream.sample_rate:
        details.append(f"{stream.sample_rate}Hz")
    if stream.channels:
        details.append(f"{stream.channels}ch")
    return " ".join(details)


if __name__ == "__main__":
    raise SystemExit(main())
