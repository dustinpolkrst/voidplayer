# Rust Core Migration

VoidPlayer now has an initial Rust extension crate in `rust/` named `voidplayer_core`.

## Scope in this increment

Implemented native foundations for:

- FFmpeg option normalization and command building.
- Tokio-backed FFmpeg-family process execution helper.
- Timestamp parsing/formatting helpers.
- Timeline preview timestamp generation.
- Thumbnail cache key hashing.

Python wrappers remain source-compatible and fall back to the original Python implementations when the native extension is not installed.

## Development

From the repository root:

```powershell
uv sync --dev
cd rust
cargo check
maturin develop
cd ..
uv run pytest
```

The Rust process runner uses `tokio::process::Command` and a Tokio runtime. Synchronous Python entrypoints block on the Tokio future so existing Python APIs can stay unchanged while async internals are available for later expansion.

## Migration order

1. Keep expanding `voidplayer_core` behind Python fallbacks.
2. Move `run_ffmpeg` error mapping/progress parsing next.
3. Move `probe` JSON parsing and typed stream models.
4. Move thumbnail batch generation.
5. Move config/history schemas and migrations.
6. Move playback clock/state classes, leaving PyAV/Qt rendering in Python.
