from __future__ import annotations

import importlib.util
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from .errors import AudioOutputError, DecodeError, UnsupportedMediaError
from .media import MediaInfo, describe_media, seconds_from_timestamp

FrameCallback = Callable[["VideoFrame"], None]
StateCallback = Callable[["PlaybackState"], None]
ErrorCallback = Callable[[Exception], None]
WarningCallback = Callable[[Exception], None]

LOGGER = logging.getLogger(__name__)
DEBUG_ENABLED = os.environ.get("FFMPEG_PYWRAPPER_DEBUG") == "1"
MAX_VIDEO_SLEEP = 0.03
DROP_FRAME_AFTER = 0.12
AUDIO_READY_TIMEOUT = 0.75
AUDIO_READY_QUEUE_CHUNKS = 3
DRIFT_LOG_INTERVAL = 1.0
SEEK_DROP_TOLERANCE = 0.03


class PlaybackState(str, Enum):
    IDLE = "idle"
    LOADED = "loaded"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    CLOSED = "closed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class VideoFrame:
    image: object
    timestamp: float


class PlaybackClock:
    def __init__(self) -> None:
        self._base_position = 0.0
        self._started_at: float | None = None

    @property
    def position(self) -> float:
        if self._started_at is None:
            return self._base_position
        return self._base_position + (time.monotonic() - self._started_at)

    @property
    def active(self) -> bool:
        return self._started_at is not None

    def start(self) -> None:
        if self._started_at is None:
            self._started_at = time.monotonic()

    def pause(self) -> None:
        if self._started_at is not None:
            self._base_position = self.position
            self._started_at = None

    def seek(self, seconds: float) -> None:
        self._base_position = max(0.0, seconds)
        self._started_at = time.monotonic() if self._started_at is not None else None

    def reset(self) -> None:
        self._base_position = 0.0
        self._started_at = None


class AudioClock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._base_position = 0.0
        self._played_samples = 0
        self._sample_rate = 48000
        self._active = False

    @property
    def active(self) -> bool:
        with self._lock:
            return self._active

    @property
    def position(self) -> float:
        with self._lock:
            return self._base_position + (self._played_samples / self._sample_rate)

    def start(self, sample_rate: int, position: float = 0.0) -> None:
        with self._lock:
            self._sample_rate = sample_rate
            self._base_position = max(0.0, position)
            self._played_samples = 0
            self._active = True

    def advance(self, samples: int) -> None:
        with self._lock:
            if self._active:
                self._played_samples += max(0, samples)

    def seek(self, position: float) -> None:
        with self._lock:
            self._base_position = max(0.0, position)
            self._played_samples = 0

    def stop(self) -> None:
        with self._lock:
            self._active = False

    def reset(self) -> None:
        with self._lock:
            self._base_position = 0.0
            self._played_samples = 0
            self._active = False


@dataclass(frozen=True, slots=True)
class FrameTiming:
    delay: float
    should_drop: bool


def frame_timing(frame_timestamp: float, clock_position: float) -> FrameTiming:
    delta = frame_timestamp - clock_position
    return FrameTiming(delay=max(0.0, delta), should_drop=delta < -DROP_FRAME_AFTER)


class DecodeLoopPlayer:
    """Small FFmpeg-backed playback engine for local files.

    The engine decodes on worker threads and emits video frames through a
    callback. It is intentionally minimal so the example GUI owns rendering.
    """

    def __init__(
        self,
        *,
        on_frame: FrameCallback | None = None,
        on_state: StateCallback | None = None,
        on_error: ErrorCallback | None = None,
        on_warning: WarningCallback | None = None,
    ) -> None:
        self.on_frame = on_frame
        self.on_state = on_state
        self.on_error = on_error
        self.on_warning = on_warning
        self.media: MediaInfo | None = None
        self.state = PlaybackState.IDLE
        self.clock = PlaybackClock()
        self.audio_clock = AudioClock()
        self.volume = 1.0
        self._lifecycle_lock = threading.RLock()
        self._path: Path | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._generation = 0
        self._audio_enabled = False
        self._audio_expected = False
        self._audio_output_available = False
        self._audio_ready = threading.Event()
        self._playback_started = threading.Event()
        self._audio_queue: queue.Queue[object] = queue.Queue(maxsize=24)
        self._audio_current: object | None = None
        self._audio_sample_rate = 48000
        self._audio_channels = 2
        self._audio_output_thread: threading.Thread | None = None
        self._video_thread: threading.Thread | None = None
        self._audio_thread: threading.Thread | None = None

    def load(self, path: str | Path) -> MediaInfo:
        self.close()
        self._ensure_decode_dependency()
        media = describe_media(path)
        if not media.has_video:
            raise UnsupportedMediaError("No video stream found in media file.")
        with self._lifecycle_lock:
            self._path = Path(path)
            self.media = media
            self.clock.reset()
            self.audio_clock.reset()
            self._reset_playback_flags(reset_audio_output=True)
            self._reset_audio_buffers()
            self._next_generation()
        LOGGER.info(
            "loaded media path=%s duration=%s video=%s audio=%s",
            self._path,
            media.duration,
            media.primary_video,
            media.primary_audio,
        )
        self._set_state(PlaybackState.LOADED)
        return media

    def play(self) -> None:
        with self._lifecycle_lock:
            if self._path is None or self.media is None:
                raise UnsupportedMediaError("Load a media file before playing.")
            if self.state == PlaybackState.PLAYING:
                return
            self._stop_event.clear()
            self._pause_event.clear()
            if self.state == PlaybackState.PAUSED:
                self.clock.start()
                resume_only = True
                audio_expected = False
            else:
                resume_only = False
                self._audio_ready.clear()
                self._playback_started.clear()
                self._audio_expected = self.media.has_audio
                audio_expected = self._audio_expected
                generation = self._generation
                start_at = self.clock.position
        if resume_only:
            self._set_state(PlaybackState.PLAYING)
            return
        if audio_expected:
            audio_expected = self._start_audio_output()
            with self._lifecycle_lock:
                self._audio_expected = audio_expected
        self._set_state(PlaybackState.PLAYING)
        self._start_workers(generation, start_at)

    def pause(self) -> None:
        with self._lifecycle_lock:
            if self.state != PlaybackState.PLAYING:
                return
            self._pause_event.set()
            self.clock.pause()
        self._set_state(PlaybackState.PAUSED)

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop_event.set()
            self._pause_event.clear()
            self.clock.reset()
            self.audio_clock.reset()
            self._reset_playback_flags(reset_audio_output=True)
            self._reset_audio_buffers()
            self._next_generation()
            should_set_stopped = self.state not in (PlaybackState.IDLE, PlaybackState.CLOSED)
        self._join_workers(timeout=0.5, include_audio_output=True)
        if should_set_stopped:
            self._set_state(PlaybackState.STOPPED)

    def seek(self, timestamp: str | float | int) -> None:
        seconds = seconds_from_timestamp(timestamp)
        with self._lifecycle_lock:
            was_playing = self.state == PlaybackState.PLAYING
            was_paused = self.state == PlaybackState.PAUSED
            generation = self._next_generation()
            self.clock.seek(seconds)
            self.audio_clock.seek(seconds)
            self.audio_clock.stop()
            self._audio_enabled = False
            self._audio_expected = bool(self.media is not None and self.media.has_audio and self._audio_output_available)
            self._audio_ready.clear()
            self._playback_started.clear()
            self._reset_audio_buffers()
        if was_playing:
            self._pause_event.clear()
            self._start_workers(generation, seconds, replace=True)
        elif was_paused:
            self._pause_event.set()

    def set_volume(self, volume: float) -> None:
        with self._lifecycle_lock:
            self.volume = min(1.0, max(0.0, volume))

    def close(self) -> None:
        with self._lifecycle_lock:
            self._stop_event.set()
            self._pause_event.clear()
            self.clock.reset()
            self.audio_clock.reset()
            self._reset_playback_flags(reset_audio_output=True)
            self._reset_audio_buffers()
            self._next_generation()
            should_set_closed = self.state != PlaybackState.IDLE
        self._join_workers(timeout=0.5, include_audio_output=True)
        with self._lifecycle_lock:
            self._path = None
            self.media = None
        if should_set_closed:
            self._set_state(PlaybackState.CLOSED)

    def master_position(self) -> float:
        with self._lifecycle_lock:
            use_audio = self._audio_enabled and self._audio_ready.is_set() and self.audio_clock.active
        if use_audio:
            return self.audio_clock.position
        return self.clock.position

    def _wait_for_audio_ready(self) -> bool:
        if not self._audio_expected:
            return False
        ready = self._audio_ready.wait(AUDIO_READY_TIMEOUT)
        if not ready:
            LOGGER.warning("audio was not ready after %.2fs; starting video on wall clock", AUDIO_READY_TIMEOUT)
        return ready

    def _start_presentation_clock(self, position: float) -> None:
        if self._playback_started.is_set():
            return
        self.clock.seek(position)
        self.clock.start()
        self._playback_started.set()

    def _start_workers(self, generation: int, start_at: float, *, replace: bool = False) -> None:
        if replace:
            self._join_workers(timeout=0.25)
        with self._lifecycle_lock:
            if self.media is None:
                return
            start_video = replace or self._video_thread is None or not self._video_thread.is_alive()
            start_audio = (
                self.media.has_audio
                and self._audio_output_available
                and (replace or self._audio_thread is None or not self._audio_thread.is_alive())
            )
            if start_video:
                self._video_thread = threading.Thread(target=self._run_video, args=(generation, start_at), daemon=True)
                self._video_thread.start()
            if start_audio:
                self._audio_thread = threading.Thread(target=self._run_audio, args=(generation, start_at), daemon=True)
                self._audio_thread.start()

    def _join_workers(self, timeout: float, *, include_audio_output: bool = False) -> None:
        current = threading.current_thread()
        workers = [self._video_thread, self._audio_thread]
        if include_audio_output:
            workers.append(self._audio_output_thread)
        for worker in workers:
            if worker is not None and worker is not current and worker.is_alive():
                worker.join(timeout=timeout)

    def _is_current_generation(self, generation: int) -> bool:
        with self._lifecycle_lock:
            return generation == self._generation

    def _next_generation(self) -> int:
        self._generation += 1
        return self._generation

    def _reset_playback_flags(self, *, reset_audio_output: bool = False) -> None:
        self._audio_enabled = False
        self._audio_expected = False
        if reset_audio_output:
            self._audio_output_available = False
        self._audio_ready.clear()
        self._playback_started.clear()

    def _seek_container_to(self, container: object, stream: object, start_at: float) -> None:
        if start_at > 0:
            container.seek(int(start_at / float(stream.time_base)), backward=True, any_frame=False, stream=stream)

    def _mark_audio_ready(self, generation: int) -> bool:
        if self._is_current_generation(generation) and self._audio_queue.qsize() >= AUDIO_READY_QUEUE_CHUNKS and self.audio_clock.active:
            self._audio_ready.set()
            LOGGER.debug("audio ready queue=%s clock=%.3f", self._audio_queue.qsize(), self.audio_clock.position)
            return True
        return False

    def _advance_audio_clock(self, generation: int, samples: int) -> None:
        if self._is_current_generation(generation):
            self.audio_clock.advance(samples)

    def _reset_audio_buffers(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        self._audio_current = None

    def _start_audio_output(self) -> bool:
        with self._lifecycle_lock:
            if self._audio_output_thread is not None and self._audio_output_thread.is_alive():
                return True
        try:
            import sounddevice
        except ImportError:
            with self._lifecycle_lock:
                self._audio_output_available = False
            self._warn(AudioOutputError("Install the player extra to enable audio output."))
            return False

        self._audio_sample_rate = _default_output_sample_rate(sounddevice)
        with self._lifecycle_lock:
            self._audio_output_available = True
            self._audio_output_thread = threading.Thread(target=self._run_audio_output, args=(sounddevice,), daemon=True)
            self._audio_output_thread.start()
        return True

    def _audio_callback(self, outdata, frames: int, time_info=None, status=None) -> None:  # noqa: ANN001
        outdata.fill(0)
        if self._pause_event.is_set() or self._stop_event.is_set() or not self._audio_ready.is_set():
            return
        written = 0
        while written < frames:
            if self._audio_current is None or len(self._audio_current) == 0:
                try:
                    self._audio_current = self._audio_queue.get_nowait()
                except queue.Empty:
                    break
            take = min(frames - written, len(self._audio_current))
            outdata[written : written + take] = self._audio_current[:take] * self.volume
            self._audio_current = self._audio_current[take:]
            written += take
        if written:
            self.audio_clock.advance(written)
        if DEBUG_ENABLED:
            LOGGER.debug("audio callback wrote=%s requested=%s queue=%s clock=%.3f", written, frames, self._audio_queue.qsize(), self.audio_clock.position)

    def _run_audio_output(self, sounddevice: object) -> None:
        try:
            with sounddevice.OutputStream(
                channels=self._audio_channels,
                samplerate=self._audio_sample_rate,
                dtype="float32",
                callback=self._audio_callback,
            ):
                while not self._stop_event.is_set() and self.media is not None:
                    time.sleep(0.05)
        except Exception as exc:  # pragma: no cover - device dependent
            self._audio_enabled = False
            self.audio_clock.stop()
            self._warn(AudioOutputError(f"Audio playback failed: {exc}"))

    def _run_video(self, generation: int, start_at: float) -> None:
        try:
            import av
        except ImportError as exc:
            self._fail(DecodeError("Install the player extra to decode video: uv sync --extra player --group player"), exc)
            return

        while not self._stop_event.is_set() and self._path is not None and generation == self._generation:
            try:
                with av.open(str(self._path)) as container:
                    video_stream = container.streams.video[0]
                    LOGGER.debug("video stream selected index=%s time_base=%s rate=%s", video_stream.index, video_stream.time_base, video_stream.average_rate)
                    self._seek_container_to(container, video_stream, start_at)
                    audio_ready = self._wait_for_audio_ready()
                    first_video_pts: float | None = None
                    first_displayed_pts: float | None = None
                    last_drift_log = 0.0
                    for frame in container.decode(video_stream):
                        if self._stop_event.is_set() or generation != self._generation:
                            break
                        self._wait_if_paused()
                        timestamp = float(frame.pts * frame.time_base) if frame.pts is not None else self.clock.position
                        if timestamp < start_at - SEEK_DROP_TOLERANCE:
                            continue
                        if first_video_pts is None:
                            first_video_pts = timestamp
                            LOGGER.debug("first video pts=%.3f requested=%.3f", first_video_pts, start_at)
                        if not self._playback_started.is_set():
                            self._start_presentation_clock(timestamp if not audio_ready else self.audio_clock.position)
                        master = self.master_position()
                        timing = frame_timing(timestamp, master)
                        if timing.should_drop:
                            LOGGER.debug("dropping late frame pts=%.3f master=%.3f av_delta=%.3f", timestamp, master, timestamp - master)
                            continue
                        while timing.delay > 0 and not self._stop_event.is_set() and generation == self._generation:
                            time.sleep(min(timing.delay, MAX_VIDEO_SLEEP))
                            master = self.master_position()
                            timing = frame_timing(timestamp, master)
                            if timing.should_drop:
                                break
                        if timing.should_drop:
                            continue
                        image = frame.to_image()
                        master = self.master_position()
                        if first_displayed_pts is None:
                            first_displayed_pts = timestamp
                            LOGGER.debug(
                                "first displayed video pts=%.3f master=%.3f av_delta=%.3f audio_ready=%s",
                                first_displayed_pts,
                                master,
                                first_displayed_pts - master,
                                self._audio_ready.is_set(),
                            )
                        if DEBUG_ENABLED and time.monotonic() - last_drift_log >= DRIFT_LOG_INTERVAL:
                            LOGGER.debug("video drift pts=%.3f master=%.3f delta=%.3f", timestamp, master, timestamp - master)
                            last_drift_log = time.monotonic()
                        if self.on_frame:
                            self.on_frame(VideoFrame(image=image, timestamp=timestamp))
                    else:
                        self.stop()
                        return
            except Exception as exc:  # pragma: no cover - exercised by integration/manual playback
                if generation != self._generation:
                    return
                self._fail(DecodeError(f"Video decode failed: {exc}"), exc)
                return

    def _run_audio(self, generation: int, start_at: float) -> None:
        try:
            import av
            import numpy as np
        except ImportError as exc:
            self._warn(AudioOutputError("Install the player extra to enable audio output."))
            return

        try:
            with av.open(str(self._path)) as container:
                stream = container.streams.audio[0]
                self._seek_container_to(container, stream, start_at)
                sample_rate = self._audio_sample_rate
                channels = self._audio_channels
                resampler = av.audio.resampler.AudioResampler(format="flt", layout="stereo", rate=sample_rate)
                self._audio_enabled = True
                LOGGER.debug("audio stream selected index=%s source_rate=%s output_rate=%s", stream.index, stream.rate, sample_rate)
                for frame in container.decode(stream):
                    if self._stop_event.is_set() or generation != self._generation:
                        break
                    self._wait_if_paused()
                    frame_pts = float(frame.pts * frame.time_base) if frame.pts is not None else self.clock.position
                    if frame_pts < start_at - SEEK_DROP_TOLERANCE:
                        continue
                    for resampled in resampler.resample(frame):
                        chunk = _audio_frame_to_stereo_float32(resampled, np, channels)
                        while not self._stop_event.is_set() and generation == self._generation:
                            try:
                                self._audio_queue.put(chunk, timeout=0.05)
                                if generation == self._generation and not self.audio_clock.active:
                                    self.audio_clock.start(sample_rate, frame_pts)
                                    LOGGER.debug("first audio pts=%.3f requested=%.3f", frame_pts, start_at)
                                if self._mark_audio_ready(generation):
                                    break
                                break
                            except queue.Full:
                                LOGGER.debug("audio queue full queue=%s", self._audio_queue.qsize())
                                if self._audio_ready.is_set():
                                    time.sleep(0.02)
                                continue
                        if generation != self._generation:
                            break
        except Exception as exc:  # pragma: no cover - device dependent
            if generation == self._generation:
                self._audio_enabled = False
                self.audio_clock.stop()
                self._warn(AudioOutputError(f"Audio playback failed: {exc}"))

    def _wait_if_paused(self) -> None:
        while self._pause_event.is_set() and not self._stop_event.is_set():
            time.sleep(0.03)

    def _set_state(self, state: PlaybackState) -> None:
        with self._lifecycle_lock:
            self.state = state
            callback = self.on_state
        if callback:
            callback(state)

    def _fail(self, error: Exception, cause: Exception | None = None) -> None:
        with self._lifecycle_lock:
            self._stop_event.set()
        self._set_state(PlaybackState.ERROR)
        if self.on_error:
            self.on_error(error)
        elif cause:
            raise error from cause
        else:
            raise error

    def _warn(self, warning: Exception) -> None:
        LOGGER.warning("%s", warning)
        if self.on_warning:
            self.on_warning(warning)
        elif self.on_error:
            self.on_error(warning)

    @staticmethod
    def _ensure_decode_dependency() -> None:
        if importlib.util.find_spec("av") is None:
            raise DecodeError("PyAV is required for playback. Install with: uv sync --extra player --group player")


def configure_debug_logging(enabled: bool = True) -> None:
    if enabled:
        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        LOGGER.setLevel(logging.DEBUG)


def _default_output_sample_rate(sounddevice_module: object) -> int:
    try:
        device_index = sounddevice_module.default.device[1]
        if device_index is not None and device_index >= 0:
            device = sounddevice_module.query_devices(device_index, "output")
        else:
            device = sounddevice_module.query_devices(kind="output")
        return int(device.get("default_samplerate") or 48000)
    except Exception:
        return 48000


def _audio_frame_to_stereo_float32(frame: object, np: object, channels: int = 2) -> object:
    chunk = frame.to_ndarray()
    if chunk.ndim == 2 and chunk.shape[0] == 1 and chunk.shape[1] == frame.samples * channels:
        chunk = chunk.reshape(frame.samples, channels)
    elif chunk.ndim == 1:
        chunk = np.column_stack((chunk, chunk))
    else:
        chunk = chunk.T
    if chunk.shape[1] == 1:
        chunk = np.repeat(chunk, channels, axis=1)
    return chunk[:, :channels].astype(np.float32, copy=False)
