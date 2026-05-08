from __future__ import annotations

from collections.abc import Mapping, Sequence
from os import PathLike
from typing import TypeAlias

OptionValue: TypeAlias = str | int | float | bool | None | PathLike[str]
Options: TypeAlias = Mapping[str, OptionValue | Sequence[OptionValue]]


def normalize_options(options: Options | None) -> list[str]:
    """Convert a mapping of FFmpeg options to argv tokens.

    Keys may be written with or without the leading dash. Boolean true emits
    only the option flag, while false and None omit the option.
    """

    if not options:
        return []

    args: list[str] = []
    for key, value in options.items():
        flag = key if key.startswith("-") else f"-{key}"
        if value is None or value is False:
            continue
        if value is True:
            args.append(flag)
            continue
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for item in value:
                args.extend([flag, _stringify(item)])
            continue
        args.extend([flag, _stringify(value)])
    return args


def _stringify(value: OptionValue) -> str:
    if value is None:
        return ""
    return str(value)
