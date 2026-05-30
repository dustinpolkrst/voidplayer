from __future__ import annotations

from ffmpeg_pywrapper import format_timestamp
from ffmpeg_pywrapper.anime import AnimeEpisode
from ffmpeg_pywrapper.media import MediaSource
from ffmpeg_pywrapper.player.config_store import AnimeHistoryItem, anime_history_progress

HistoryKey = tuple[str, str, str]


def anime_history_key(episode: AnimeEpisode) -> HistoryKey:
    return (episode.show_id, episode.number, episode.mode)


def episode_history_map(items: list[AnimeHistoryItem]) -> dict[HistoryKey, AnimeHistoryItem]:
    return {(item.show_id, item.episode, item.mode): item for item in items}


def selected_episode_history(
    episode: AnimeEpisode,
    history: dict[HistoryKey, AnimeHistoryItem],
) -> AnimeHistoryItem | None:
    return history.get(anime_history_key(episode))


def episode_row_text(episode: AnimeEpisode, history_item: AnimeHistoryItem | None) -> str:
    if history_item is None:
        return f"Episode {episode.number}    Not watched"
    progress = anime_history_progress(history_item)
    progress_text = f"    {progress}" if progress else ""
    if history_item.position > 0:
        return f"Episode {episode.number}    Resume {format_timestamp(history_item.position)}{progress_text}"
    return f"Episode {episode.number}    Watched{progress_text}"


def episode_source_with_resume(source: MediaSource, history_item: AnimeHistoryItem | None) -> MediaSource:
    if history_item is None or history_item.position <= 0:
        return source
    metadata = dict(source.metadata or {})
    metadata["resume_position"] = f"{history_item.position:.6f}"
    return MediaSource(
        location=source.location,
        title=source.title,
        headers=source.headers,
        subtitle_url=source.subtitle_url or history_item.subtitle_url,
        metadata=metadata,
    )
