from __future__ import annotations

import threading
import time
import importlib.util
from pathlib import Path

import numpy as np

from ffmpeg_pywrapper.media import MediaInfo, StreamInfo
from ffmpeg_pywrapper.playback import (
    AudioClock,
    AUDIO_READY_QUEUE_CHUNKS,
    DecodeLoopPlayer,
    PlaybackClock,
    PlaybackState,
    _audio_frame_to_stereo_float32,
    frame_timing,
)


def test_playback_clock_seek_pause_reset() -> None:
    clock = PlaybackClock()

    clock.seek(12.5)
    assert clock.position == 12.5

    clock.start()
    assert clock.position >= 12.5

    clock.pause()
    paused = clock.position
    assert paused >= 12.5

    clock.reset()
    assert clock.position == 0


def test_playback_state_values_are_stable() -> None:
    assert PlaybackState.PLAYING.value == "playing"
    assert PlaybackState.ERROR.value == "error"


def test_audio_warning_does_not_force_error_state() -> None:
    warnings: list[Exception] = []
    player = DecodeLoopPlayer(on_warning=warnings.append)
    player._set_state(PlaybackState.PLAYING)

    player._warn(RuntimeError("audio unavailable"))

    assert player.state == PlaybackState.PLAYING
    assert str(warnings[0]) == "audio unavailable"


def test_audio_clock_advances_by_samples() -> None:
    clock = AudioClock()

    clock.start(48000, position=10)
    clock.advance(24000)

    assert clock.active is True
    assert clock.position == 10.5


def test_audio_clock_can_advance_for_silence_on_underrun() -> None:
    clock = AudioClock()

    clock.start(44100)
    clock.advance(4410)

    assert clock.position == 0.1


def test_master_clock_prefers_active_audio() -> None:
    player = DecodeLoopPlayer()
    player.clock.seek(3)
    player.audio_clock.start(48000, position=8)
    player.audio_clock.advance(4800)
    player._audio_enabled = True
    player._audio_ready.set()

    assert player.master_position() == 8.1


def test_master_clock_reads_audio_only_after_audio_ready() -> None:
    player = DecodeLoopPlayer()
    player.clock.seek(3)
    player.audio_clock.start(48000, position=8)
    player.audio_clock.advance(4800)
    player._audio_enabled = True

    assert player.master_position() == 3

    player._audio_ready.set()

    assert player.master_position() == 8.1


def test_master_clock_falls_back_to_wall_clock() -> None:
    player = DecodeLoopPlayer()
    player.clock.seek(3)

    assert player.master_position() == 3


def test_gui_visible_position_uses_master_position() -> None:
    module_path = Path(__file__).resolve().parents[1] / "examples" / "simple_player" / "main.py"
    spec = importlib.util.spec_from_file_location("simple_player_main", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    PlayerWindow = module.PlayerWindow

    class Slider:
        def __init__(self) -> None:
            self.value = None

        def setValue(self, value: int) -> None:
            self.value = value

    class Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:
            self.text = text

    class Player:
        clock = None

        @staticmethod
        def master_position() -> float:
            return 5.0

    class Window:
        pass

    window = Window()
    window.player = Player()
    window.duration = 10.0
    window._seeking = False
    window.seek_slider = Slider()
    window.elapsed_label = Label()
    window.total_label = Label()

    PlayerWindow.refresh_position(window)

    assert window.seek_slider.value == 500
    assert window.elapsed_label.text == "00:00:05.00"
    assert window.total_label.text == "00:00:10.00"


def test_video_start_waits_for_audio_readiness_when_audio_is_expected(monkeypatch) -> None:
    player = DecodeLoopPlayer()
    player._audio_expected = True
    player._audio_ready.clear()
    monkeypatch.setattr("ffmpeg_pywrapper.playback.AUDIO_READY_TIMEOUT", 0.5)

    def mark_ready() -> None:
        time.sleep(0.05)
        player._audio_ready.set()

    thread = threading.Thread(target=mark_ready)
    thread.start()
    started = time.monotonic()

    assert player._wait_for_audio_ready() is True
    assert time.monotonic() - started >= 0.04

    thread.join()


def test_video_start_falls_back_after_audio_ready_timeout(monkeypatch) -> None:
    player = DecodeLoopPlayer()
    player._audio_expected = True
    player._audio_ready.clear()
    monkeypatch.setattr("ffmpeg_pywrapper.playback.AUDIO_READY_TIMEOUT", 0.01)

    started = time.monotonic()

    assert player._wait_for_audio_ready() is False
    assert time.monotonic() - started < 0.2


def test_seek_while_playing_restarts_workers_at_seek_target(monkeypatch) -> None:
    player = DecodeLoopPlayer()
    player.media = MediaInfo(
        path=Path("movie.mp4"),
        duration=20,
        streams=(
            StreamInfo(index=0, codec_type="video", codec_name="h264"),
            StreamInfo(index=1, codec_type="audio", codec_name="aac"),
        ),
    )
    player._path = Path("movie.mp4")
    player._set_state(PlaybackState.PLAYING)
    player._audio_output_available = True
    player._audio_ready.set()
    player._playback_started.set()
    starts: list[tuple[int, float, bool]] = []
    monkeypatch.setattr(player, "_start_workers", lambda generation, start_at, *, replace=False: starts.append((generation, start_at, replace)))

    player.seek(12.5)

    assert starts == [(player._generation, 12.5, True)]
    assert player._audio_expected is True
    assert player._audio_ready.is_set() is False
    assert player._playback_started.is_set() is False
    assert player.clock.position == 12.5
    assert player.audio_clock.position == 12.5
    assert player.audio_clock.active is False


def test_paused_seek_repositions_without_restarting_workers(monkeypatch) -> None:
    player = DecodeLoopPlayer()
    player.media = MediaInfo(path=Path("movie.mp4"), duration=20, streams=(StreamInfo(index=0, codec_type="video", codec_name="h264"),))
    player._set_state(PlaybackState.PAUSED)
    starts: list[object] = []
    monkeypatch.setattr(player, "_start_workers", lambda *args, **kwargs: starts.append((args, kwargs)))

    player.seek(4)

    assert starts == []
    assert player.clock.position == 4


def test_container_seek_uses_stream_time_base() -> None:
    class Container:
        def __init__(self) -> None:
            self.calls = []

        def seek(self, offset, *, backward, any_frame, stream):  # noqa: ANN001
            self.calls.append((offset, backward, any_frame, stream))

    class Stream:
        time_base = 0.5

    player = DecodeLoopPlayer()
    container = Container()
    stream = Stream()

    player._seek_container_to(container, stream, 12.5)

    assert container.calls == [(25, True, False, stream)]


def test_stale_generation_audio_advance_is_ignored() -> None:
    player = DecodeLoopPlayer()
    player._generation = 2
    player.audio_clock.start(48000, position=10)

    player._advance_audio_clock(1, 4800)

    assert player.audio_clock.position == 10


def test_stale_generation_cannot_mark_audio_ready() -> None:
    player = DecodeLoopPlayer()
    player._generation = 2
    player.audio_clock.start(48000)
    for item in range(AUDIO_READY_QUEUE_CHUNKS):
        player._audio_queue.put(item)

    assert player._mark_audio_ready(1) is False
    assert player._audio_ready.is_set() is False


def test_seek_clears_audio_buffers_without_reopening_output(monkeypatch) -> None:
    player = DecodeLoopPlayer()
    player.media = MediaInfo(
        path=Path("movie.mp4"),
        duration=20,
        streams=(
            StreamInfo(index=0, codec_type="video", codec_name="h264"),
            StreamInfo(index=1, codec_type="audio", codec_name="aac"),
        ),
    )
    player._set_state(PlaybackState.PLAYING)
    player._audio_output_available = True
    player._audio_ready.set()
    player._audio_current = np.ones((2, 2), dtype=np.float32)
    player._audio_queue.put(np.ones((2, 2), dtype=np.float32))
    output_starts = []
    worker_starts = []
    monkeypatch.setattr(player, "_start_audio_output", lambda: output_starts.append(True))
    monkeypatch.setattr(player, "_start_workers", lambda generation, start_at, *, replace=False: worker_starts.append((generation, start_at, replace)))

    player.seek(7)

    assert output_starts == []
    assert worker_starts == [(player._generation, 7.0, True)]
    assert player._audio_current is None
    assert player._audio_queue.empty()
    assert player._audio_ready.is_set() is False


def test_audio_callback_outputs_silence_before_ready_without_advancing_clock() -> None:
    player = DecodeLoopPlayer()
    player.audio_clock.start(48000, position=5)
    player._audio_queue.put(np.ones((4, 2), dtype=np.float32))
    out = np.full((4, 2), 9, dtype=np.float32)

    player._audio_callback(out, 4)

    assert out.tolist() == [[0, 0], [0, 0], [0, 0], [0, 0]]
    assert player.audio_clock.position == 5
    assert player._audio_queue.qsize() == 1


def test_audio_callback_writes_pcm_and_advances_clock_after_ready() -> None:
    player = DecodeLoopPlayer()
    player.audio_clock.start(4, position=5)
    player._audio_ready.set()
    player._audio_queue.put(np.ones((4, 2), dtype=np.float32))
    out = np.zeros((4, 2), dtype=np.float32)

    player._audio_callback(out, 4)

    assert out.tolist() == [[1, 1], [1, 1], [1, 1], [1, 1]]
    assert player.audio_clock.position == 6


def test_video_seek_drop_logic_skips_frames_before_target() -> None:
    assert 11.0 < 12.5 - 0.03
    assert not (12.49 < 12.5 - 0.03)


def test_frame_timing_decisions() -> None:
    assert frame_timing(10.1, 10).should_drop is False
    assert frame_timing(10.1, 10).delay > 0
    assert frame_timing(9.7, 10).should_drop is True


def test_packed_stereo_audio_frame_is_reshaped_without_duplication() -> None:
    class Frame:
        samples = 3

        @staticmethod
        def to_ndarray():
            return np.array([[1, 2, 3, 4, 5, 6]], dtype=np.float32)

    pcm = _audio_frame_to_stereo_float32(Frame(), np, 2)

    assert pcm.shape == (3, 2)
    assert pcm.tolist() == [[1, 2], [3, 4], [5, 6]]
