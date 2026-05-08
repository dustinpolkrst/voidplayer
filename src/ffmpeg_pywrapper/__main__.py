from __future__ import annotations

import argparse
import json
from pathlib import Path

from .probe import probe


def main() -> int:
    parser = argparse.ArgumentParser(prog="ffmpeg-pywrapper")
    parser.add_argument("input", nargs="?", type=Path, help="Media file to probe")
    args = parser.parse_args()

    if args.input is None:
        parser.print_help()
        return 0

    result = probe(args.input)
    print(json.dumps(result.data, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
