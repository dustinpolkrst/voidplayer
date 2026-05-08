# Graph Report - ffmpeg_pywrapper  (2026-05-08)

## Corpus Check
- 25 files · ~5,900 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 226 nodes · 457 edges · 15 communities (12 shown, 3 thin omitted)
- Extraction: 78% EXTRACTED · 22% INFERRED · 0% AMBIGUOUS · INFERRED: 102 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]

## God Nodes (most connected - your core abstractions)
1. `DecodeLoopPlayer` - 54 edges
2. `PlayerWindow` - 22 edges
3. `run_ffmpeg()` - 15 edges
4. `AudioClock` - 14 edges
5. `FFmpegConfig` - 13 edges
6. `MediaInfo` - 13 edges
7. `AudioOutputError` - 12 edges
8. `PlaybackClock` - 12 edges
9. `UnsupportedMediaError` - 11 edges
10. `DecodeError` - 11 edges

## Surprising Connections (you probably didn't know these)
- `PlayerSignals` --uses--> `DecodeLoopPlayer`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerSignals` --uses--> `PlaybackState`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerSignals` --uses--> `VideoFrame`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerWindow` --uses--> `DecodeLoopPlayer`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py
- `PlayerWindow` --uses--> `PlaybackState`  [INFERRED]
  examples/simple_player/main.py → src/ffmpeg_pywrapper/playback.py

## Communities (15 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (25): FFmpegConfig, Executable locations for system FFmpeg tools., _resolve_executable(), FFmpegExecutableNotFound, Raised when ffmpeg or ffprobe cannot be found., main(), describe_media(), format_timestamp() (+17 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (21): build_command(), convert(), Build a plain argv list for a single-output FFmpeg command., thumbnail(), trim(), FFmpegTimeoutError, Raised when a process exceeds its timeout., Typed helpers for running system FFmpeg and FFprobe. (+13 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (15): Enum, AudioOutputError, DecodeError, Raised when media decoding fails., Raised when audio output cannot be initialized., AudioClock, _ensure_decode_dependency(), frame_timing() (+7 more)

### Community 3 - "Community 3"
Cohesion: 0.15
Nodes (18): Exception, classify_process_error(), FFmpegError, FFmpegInvalidCommand, FFmpegProcessError, FFmpegUnsupportedCodec, _last_relevant_line(), _matches() (+10 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (16): DecodeLoopPlayer, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, Small FFmpeg-backed playback engine for local files.      The engine decodes on, test_audio_callback_outputs_silence_before_ready_without_advancing_clock(), test_audio_callback_writes_pcm_and_advances_clock_after_ready(), test_audio_warning_does_not_force_error_state() (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (6): configure_debug_logging(), QMainWindow, QObject, main(), PlayerSignals, PlayerWindow

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (10): code:powershell (uv sync --dev), code:powershell (uv sync --extra player --group player), code:python (from ffmpeg_pywrapper import convert, probe, thumbnail, trim), code:python (from ffmpeg_pywrapper import build_command), code:python (from ffmpeg_pywrapper import describe_media), Development, ffmpeg-pywrapper, Inspect Commands (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.39
Nodes (7): _parse_float(), _parse_int(), parse_progress_blocks(), _parse_time(), Progress, progress_from_mapping(), test_parse_progress_blocks()

### Community 9 - "Community 9"
Cohesion: 0.25
Nodes (3): _audio_frame_to_stereo_float32(), _default_output_sample_rate(), test_packed_stereo_audio_frame_is_reshaped_without_duplication()

### Community 13 - "Community 13"
Cohesion: 0.5
Nodes (3): code:powershell (uv sync --extra player --group player), code:powershell (uv run --extra player --group player python examples/simple_), Simple Player Example

## Knowledge Gaps
- **26 isolated node(s):** `Build a plain argv list for a single-output FFmpeg command.`, `Executable locations for system FFmpeg tools.`, `Base exception for wrapper errors.`, `Raised when ffmpeg or ffprobe cannot be found.`, `Raised when a process exceeds its timeout.` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DecodeLoopPlayer` connect `Community 4` to `Community 0`, `Community 2`, `Community 5`, `Community 7`, `Community 9`, `Community 10`, `Community 11`, `Community 12`?**
  _High betweenness centrality (0.283) - this node is a cross-community bridge._
- **Why does `PlayerWindow` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 10`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `run_ffmpeg()` connect `Community 1` to `Community 0`, `Community 8`, `Community 3`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 21 inferred relationships involving `DecodeLoopPlayer` (e.g. with `PlayerSignals` and `PlayerWindow`) actually correct?**
  _`DecodeLoopPlayer` has 21 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `PlayerWindow` (e.g. with `DecodeLoopPlayer` and `PlaybackState`) actually correct?**
  _`PlayerWindow` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `str` (e.g. with `.open_file()` and `.on_error()`) actually correct?**
  _`str` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `run_ffmpeg()` (e.g. with `str` and `test_media_flow_with_system_ffmpeg()`) actually correct?**
  _`run_ffmpeg()` has 4 INFERRED edges - model-reasoned connections that need verification._