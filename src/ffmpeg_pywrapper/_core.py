from __future__ import annotations

try:
    import voidplayer_core as rust_core  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - depends on optional native build
    rust_core = None


def rust_available() -> bool:
    return rust_core is not None
