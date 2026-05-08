from __future__ import annotations

from ffmpeg_pywrapper.errors import FFmpegInvalidCommand, FFmpegProcessError, FFmpegUnsupportedCodec, classify_process_error


def test_classifies_unsupported_codec() -> None:
    error = classify_process_error(["ffmpeg"], 1, "", "Unknown encoder 'wat'")

    assert isinstance(error, FFmpegUnsupportedCodec)


def test_classifies_invalid_command() -> None:
    error = classify_process_error(["ffmpeg"], 1, "", "Unrecognized option 'bad'")

    assert isinstance(error, FFmpegInvalidCommand)


def test_falls_back_to_process_error() -> None:
    error = classify_process_error(["ffmpeg"], 1, "out", "Something failed")

    assert isinstance(error, FFmpegProcessError)
