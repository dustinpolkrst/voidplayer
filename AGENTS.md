# Agent Instructions

## Graphify

- After code changes, update the graphify map before finishing:
  `python -m graphify update . --force`
- If the module entrypoint is unavailable, use the installed `graphify` CLI with `graphify update . --force` or rerun the graphify pipeline for `.`.
- Keep generated graph outputs under `graphify-out/`.
- Do not manually edit generated graphify artifacts unless explicitly requested.
