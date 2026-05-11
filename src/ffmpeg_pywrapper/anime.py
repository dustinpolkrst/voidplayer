from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from .media import MediaSource

AnimeMode = Literal["sub", "dub"]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
ALLANIME_REFERER = "https://allmanga.to"
ALLANIME_BASE = "allanime.day"
ALLANIME_API = f"https://api.{ALLANIME_BASE}"
ALLANIME_KEY = hashlib.sha256(b"Xot36i3lK3:v1").digest()
EPISODE_PERSISTED_HASH = "d405d0edd690624b66baba3068e0edc3ac90f1597d898a1ec8db4e5c43c00fec"

SEARCH_QUERY = """
query( $search: SearchInput $limit: Int $page: Int $translationType: VaildTranslationTypeEnumType $countryOrigin: VaildCountryOriginEnumType ) {
  shows( search: $search limit: $limit page: $page translationType: $translationType countryOrigin: $countryOrigin ) {
    edges { _id name availableEpisodes __typename }
  }
}
"""

EPISODES_QUERY = """
query ($showId: String!) {
  show( _id: $showId ) { _id availableEpisodesDetail }
}
"""

EPISODE_QUERY = """
query ($showId: String!, $translationType: VaildTranslationTypeEnumType!, $episodeString: String!) {
  episode( showId: $showId translationType: $translationType episodeString: $episodeString ) {
    episodeString sourceUrls
  }
}
"""


@dataclass(frozen=True, slots=True)
class AnimeSearchResult:
    show_id: str
    title: str
    episode_count: int | None = None


@dataclass(frozen=True, slots=True)
class AnimeEpisode:
    show_id: str
    title: str
    number: str
    mode: AnimeMode = "sub"


@dataclass(frozen=True, slots=True)
class AnimeStream:
    url: str
    quality: str
    title: str
    episode: str
    show_id: str | None = None
    mode: AnimeMode = "sub"
    referrer: str | None = None
    subtitle_url: str | None = None

    def to_media_source(self) -> MediaSource:
        headers = {"User-Agent": USER_AGENT}
        if self.referrer:
            headers["Referer"] = self.referrer
        metadata = {
            "kind": "anime",
            "title": self.title,
            "episode": self.episode,
            "mode": self.mode,
        }
        if self.show_id:
            metadata["show_id"] = self.show_id
        return MediaSource(
            location=self.url,
            title=f"{self.title} - Episode {self.episode}",
            headers=headers,
            subtitle_url=self.subtitle_url,
            metadata=metadata,
        )


class AnimeProviderStage(str, Enum):
    SEARCH = "search"
    EPISODES = "episodes"
    EPISODE_SOURCES = "episode_sources"
    FAST_PROVIDER = "fast_provider"
    SLOW_PROVIDER = "slow_provider"
    M3U8_PARSE = "m3u8_parse"
    PLAYBACK_LOAD = "playback_load"


class AnimeClientError(RuntimeError):
    def __init__(self, message: str, *, stage: AnimeProviderStage | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.debug_detail = message

    def __str__(self) -> str:
        if self.stage is None:
            return self.debug_detail
        return f"{_stage_summary(self.stage)}. {self.debug_detail} {_stage_retry_hint(self.stage)}"


class AnimeResolvedCache:
    def __init__(
        self,
        path: Path,
        *,
        now=time.time,
        metadata_ttl: float = 60 * 60 * 24 * 7,
        stream_ttl: float = 60 * 30,
    ) -> None:
        self.path = path
        self._now = now
        self.metadata_ttl = metadata_ttl
        self.stream_ttl = stream_ttl
        self._data = self._load()

    def search_results(self, query: str, mode: AnimeMode) -> list[AnimeSearchResult] | None:
        record = self._fresh_record("search", _search_cache_key(query, mode), self.metadata_ttl)
        if record is None:
            return None
        items = record.get("items")
        if not isinstance(items, list):
            return None
        results = [_search_result_from_dict(item) for item in items if isinstance(item, dict)]
        return [item for item in results if item is not None]

    def set_search_results(self, query: str, mode: AnimeMode, results: list[AnimeSearchResult]) -> None:
        self._set_record("search", _search_cache_key(query, mode), [asdict(item) for item in results])

    def episodes(self, show_id: str, mode: AnimeMode) -> list[AnimeEpisode] | None:
        record = self._fresh_record("episodes", _episodes_cache_key(show_id, mode), self.metadata_ttl)
        if record is None:
            return None
        items = record.get("items")
        if not isinstance(items, list):
            return None
        episodes = [_episode_from_dict(item) for item in items if isinstance(item, dict)]
        return [item for item in episodes if item is not None]

    def set_episodes(self, show_id: str, mode: AnimeMode, episodes: list[AnimeEpisode]) -> None:
        self._set_record("episodes", _episodes_cache_key(show_id, mode), [asdict(item) for item in episodes])

    def streams(self, show_id: str, mode: AnimeMode, episode: str) -> list[AnimeStream] | None:
        record = self._fresh_record("streams", _streams_cache_key(show_id, mode, episode), self.stream_ttl)
        if record is None:
            return None
        items = record.get("items")
        if not isinstance(items, list):
            return None
        streams = [_stream_from_dict(item) for item in items if isinstance(item, dict)]
        return [item for item in streams if item is not None]

    def set_streams(self, show_id: str, mode: AnimeMode, episode: str, streams: list[AnimeStream]) -> None:
        self._set_record("streams", _streams_cache_key(show_id, mode, episode), [asdict(item) for item in streams])

    def _fresh_record(self, bucket: str, key: str, ttl: float) -> dict[str, Any] | None:
        records = self._data.get(bucket)
        if not isinstance(records, dict):
            return None
        record = records.get(key)
        if not isinstance(record, dict):
            return None
        saved_at = _optional_float(record.get("saved_at"))
        if saved_at is None or self._now() - saved_at > ttl:
            return None
        return record

    def _set_record(self, bucket: str, key: str, items: list[dict[str, Any]]) -> None:
        records = self._data.setdefault(bucket, {})
        if not isinstance(records, dict):
            records = {}
            self._data[bucket] = records
        records[key] = {"saved_at": self._now(), "items": items}
        self._save()

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")


class AnimeClient:
    def __init__(
        self,
        *,
        api_url: str = ALLANIME_API,
        referer: str = ALLANIME_REFERER,
        base_host: str = ALLANIME_BASE,
        api_timeout: float = 8.0,
        provider_timeout: float = 2.0,
        cache_path: Path | None = None,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency message
            raise AnimeClientError("Install anime support with: uv sync --extra anime") from exc
        self._httpx = httpx
        self._client = httpx.Client(timeout=api_timeout, follow_redirects=True)
        self.api_url = api_url.rstrip("/")
        self.referer = referer
        self.base_host = base_host
        self.api_timeout = api_timeout
        self.provider_timeout = provider_timeout
        self._resolved_cache = AnimeResolvedCache(cache_path) if cache_path is not None else None
        self._search_cache: dict[tuple[str, AnimeMode], list[AnimeSearchResult]] = {}
        self._episodes_cache: dict[tuple[str, AnimeMode], list[AnimeEpisode]] = {}
        self._streams_cache: dict[tuple[str, AnimeMode, str], list[AnimeStream]] = {}

    def search(self, query: str, *, mode: AnimeMode = "sub") -> list[AnimeSearchResult]:
        cache_key = (query.strip().casefold(), mode)
        if cache_key in self._search_cache:
            return list(self._search_cache[cache_key])
        if self._resolved_cache is not None:
            cached = self._resolved_cache.search_results(query, mode)
            if cached is not None:
                self._search_cache[cache_key] = list(cached)
                return cached
        payload = {
            "variables": {
                "search": {"allowAdult": False, "allowUnknown": False, "query": query},
                "limit": 40,
                "page": 1,
                "translationType": mode,
                "countryOrigin": "ALL",
            },
            "query": SEARCH_QUERY,
        }
        data = self._post_graphql(payload)
        edges = data.get("data", {}).get("shows", {}).get("edges", [])
        results: list[AnimeSearchResult] = []
        for edge in edges if isinstance(edges, list) else []:
            if not isinstance(edge, dict):
                continue
            episodes = edge.get("availableEpisodes", {})
            count = _optional_int(episodes.get(mode) if isinstance(episodes, dict) else None)
            show_id = edge.get("_id")
            title = edge.get("name")
            if isinstance(show_id, str) and isinstance(title, str) and count:
                results.append(AnimeSearchResult(show_id=show_id, title=title, episode_count=count))
        self._search_cache[cache_key] = list(results)
        if self._resolved_cache is not None:
            self._resolved_cache.set_search_results(query, mode, results)
        return results

    def episodes(self, show: AnimeSearchResult, *, mode: AnimeMode = "sub") -> list[AnimeEpisode]:
        cache_key = (show.show_id, mode)
        if cache_key in self._episodes_cache:
            return list(self._episodes_cache[cache_key])
        if self._resolved_cache is not None:
            cached = self._resolved_cache.episodes(show.show_id, mode)
            if cached is not None:
                self._episodes_cache[cache_key] = list(cached)
                return cached
        data = self._post_graphql({"variables": {"showId": show.show_id}, "query": EPISODES_QUERY})
        detail = data.get("data", {}).get("show", {}).get("availableEpisodesDetail", {})
        numbers = detail.get(mode) if isinstance(detail, dict) else None
        if not isinstance(numbers, list):
            return []
        episodes = [AnimeEpisode(show_id=show.show_id, title=show.title, number=str(number), mode=mode) for number in sorted(numbers, key=_episode_sort_key)]
        self._episodes_cache[cache_key] = list(episodes)
        if self._resolved_cache is not None:
            self._resolved_cache.set_episodes(show.show_id, mode, episodes)
        return episodes

    def streams(self, episode: AnimeEpisode) -> list[AnimeStream]:
        cache_key = (episode.show_id, episode.mode, episode.number)
        if cache_key in self._streams_cache:
            return list(self._streams_cache[cache_key])
        if self._resolved_cache is not None:
            cached = self._resolved_cache.streams(episode.show_id, episode.mode, episode.number)
            if cached is not None:
                self._streams_cache[cache_key] = list(cached)
                return cached
        streams = self._resolve_streams(episode, fast_only=False)
        self._streams_cache[cache_key] = list(streams)
        if self._resolved_cache is not None:
            self._resolved_cache.set_streams(episode.show_id, episode.mode, episode.number, streams)
        return streams

    def fast_streams(self, episode: AnimeEpisode) -> list[AnimeStream]:
        cache_key = (episode.show_id, episode.mode, episode.number)
        if cache_key in self._streams_cache:
            return list(self._streams_cache[cache_key])
        if self._resolved_cache is not None:
            cached = self._resolved_cache.streams(episode.show_id, episode.mode, episode.number)
            if cached is not None:
                self._streams_cache[cache_key] = list(cached)
                return cached
        streams = self._resolve_streams(episode, fast_only=True)
        if streams:
            self._streams_cache[cache_key] = list(streams)
            if self._resolved_cache is not None:
                self._resolved_cache.set_streams(episode.show_id, episode.mode, episode.number, streams)
        return streams

    def next_episode(self, episode: AnimeEpisode) -> AnimeEpisode | None:
        episodes = self.episodes(AnimeSearchResult(show_id=episode.show_id, title=episode.title), mode=episode.mode)
        numbers = [item.number for item in episodes]
        try:
            index = numbers.index(episode.number)
        except ValueError:
            return None
        return episodes[index + 1] if index + 1 < len(episodes) else None

    def fast_stream_for_episode(self, episode: AnimeEpisode) -> AnimeStream | None:
        return select_quality(self.fast_streams(episode), "best")

    def _resolve_streams(self, episode: AnimeEpisode, *, fast_only: bool) -> list[AnimeStream]:
        provider_links, data = self._episode_provider_links(episode)
        streams: list[AnimeStream] = []
        slow_links: list[str] = []
        for provider_link in provider_links:
            stream = self._fast_provider_stream(provider_link, episode)
            if stream is not None:
                streams.append(stream)
            else:
                slow_links.append(provider_link)
        if streams and fast_only:
            return sorted(_dedupe_streams(streams), key=lambda item: _quality_sort_key(item.quality), reverse=True)
        if slow_links and not fast_only:
            streams.extend(self._resolve_slow_providers(slow_links, episode))
        if not streams:
            message = _graphql_error_message(data) if data is not None else None
            stage = AnimeProviderStage.FAST_PROVIDER if fast_only else AnimeProviderStage.SLOW_PROVIDER
            raise AnimeClientError(message or "No playable streams resolved.", stage=stage)
        return sorted(_dedupe_streams(streams), key=lambda item: _quality_sort_key(item.quality), reverse=True)

    def _episode_provider_links(self, episode: AnimeEpisode) -> tuple[list[str], dict[str, Any] | None]:
        data: dict[str, Any] | None = self._get_episode_persisted(episode)
        episode_data = _episode_data(data)
        provider_links: list[str] = []
        encrypted = _find_value(data, "tobeparsed") if data is not None else None
        if isinstance(encrypted, str):
            provider_links = decode_tobeparsed(encrypted)
        if episode_data is None:
            payload = {
                "variables": {
                    "showId": episode.show_id,
                    "translationType": episode.mode,
                    "episodeString": episode.number,
                },
                "query": EPISODE_QUERY,
            }
            data = self._post_graphql(payload)
            episode_data = _episode_data(data)
        if episode_data is None and not provider_links:
            raise AnimeClientError(_graphql_error_message(data) or "Episode source data is unavailable.", stage=AnimeProviderStage.EPISODE_SOURCES)
        sources = episode_data.get("sourceUrls", []) if episode_data is not None else []
        provider_links = provider_links or parse_source_urls(sources)
        if not provider_links:
            encrypted = _find_value(episode_data, "tobeparsed") or _find_value(data, "tobeparsed")
            if isinstance(encrypted, str):
                provider_links = decode_tobeparsed(encrypted)
        return provider_links, data

    def _fast_provider_stream(self, provider_link: str, episode: AnimeEpisode) -> AnimeStream | None:
        url = self._provider_url(provider_link)
        if "tools.fast4speed.rsvp" not in url:
            return None
        return AnimeStream(
            url=url,
            quality="direct",
            title=episode.title,
            episode=episode.number,
            show_id=episode.show_id,
            mode=episode.mode,
            referrer=self.referer,
        )

    def _resolve_slow_providers(self, provider_links: list[str], episode: AnimeEpisode) -> list[AnimeStream]:
        streams: list[AnimeStream] = []
        with ThreadPoolExecutor(max_workers=min(4, len(provider_links))) as executor:
            futures = [executor.submit(self._resolve_provider, provider_link, episode) for provider_link in provider_links]
            for future in as_completed(futures):
                try:
                    streams.extend(future.result())
                except Exception:
                    continue
        return streams

    def _resolve_provider(self, provider_link: str, episode: AnimeEpisode) -> list[AnimeStream]:
        url = self._provider_url(provider_link)
        response = self._client.get(url, headers={"User-Agent": USER_AGENT, "Referer": self.referer}, timeout=self.provider_timeout)
        response.raise_for_status()
        return parse_provider_response(response.text, title=episode.title, episode=episode.number, default_referrer=self.referer)

    def _provider_url(self, provider_link: str) -> str:
        if provider_link.startswith("//"):
            return f"https:{provider_link}"
        if provider_link.startswith("/"):
            return f"https://{self.base_host}{provider_link}"
        return provider_link

    def _post_graphql(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post(
            f"{self.api_url}/api",
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, "Referer": self.referer},
            json=payload,
            timeout=self.api_timeout,
        )
        response.raise_for_status()
        return response.json()

    def _get_episode_persisted(self, episode: AnimeEpisode) -> dict[str, Any]:
        url = build_persisted_query_url(episode.show_id, episode.mode, episode.number, EPISODE_PERSISTED_HASH, api_url=self.api_url)
        response = self._client.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://youtu-chan.com",
                "Origin": "https://youtu-chan.com",
            },
            timeout=self.api_timeout,
        )
        response.raise_for_status()
        return response.json()


def parse_source_urls(source_urls: object) -> list[str]:
    if not isinstance(source_urls, list):
        return []
    links: list[str] = []
    for item in source_urls:
        if not isinstance(item, dict):
            continue
        source_url = item.get("sourceUrl") or item.get("sourceURL")
        if isinstance(source_url, str):
            links.append(decode_source_url(source_url))
    return links


def parse_provider_response(text: str, *, title: str, episode: str, default_referrer: str = ALLANIME_REFERER) -> list[AnimeStream]:
    streams: list[AnimeStream] = []
    subtitle_url = _first_match(text, r'"subtitles":\[\{"lang":"en","label":"English","default":"default","src":"([^"]+)"')
    referrer = _first_match(text, r'"Referer":"([^"]+)"') or default_referrer
    for url, quality in re.findall(r'"link":"([^"]+)".*?"resolutionStr":"([^"]+)"', text):
        streams.append(AnimeStream(url=_json_unescape(url), quality=_json_unescape(quality), title=title, episode=episode, referrer=default_referrer))
    for url in re.findall(r'"hls","url":"([^"]+)".*?"hardsub_lang":"en-US"', text):
        streams.append(AnimeStream(url=_json_unescape(url), quality="hls", title=title, episode=episode, referrer=referrer, subtitle_url=subtitle_url))
    if "master.m3u8" in text:
        streams.extend(parse_m3u8_master(text, title=title, episode=episode, referrer=referrer, subtitle_url=subtitle_url))
    return streams


def parse_m3u8_master(text: str, *, title: str, episode: str, referrer: str, subtitle_url: str | None = None) -> list[AnimeStream]:
    streams: list[AnimeStream] = []
    for resolution, url in re.findall(r'#EXT-X-STREAM.*?RESOLUTION=\d+x(\d+).*?\n([^#\n]+)', text):
        streams.append(AnimeStream(url=_json_unescape(url.strip()), quality=f"{resolution}p", title=title, episode=episode, referrer=referrer, subtitle_url=subtitle_url))
    return streams


def decode_tobeparsed(value: str) -> list[str]:
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:  # pragma: no cover - dependency message
        raise AnimeClientError("Install anime support with: uv sync --extra anime") from exc
    raw = base64.b64decode(value)
    if len(raw) < 30:
        raise AnimeClientError("Encrypted provider payload is too short.")
    iv = raw[1:13] + b"\x00\x00\x00\x02"
    ciphertext = raw[13:-16]
    decryptor = Cipher(algorithms.AES(ALLANIME_KEY), modes.CTR(iv)).decryptor()
    plaintext = (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8", errors="replace")
    return parse_source_urls_from_text(plaintext)


def parse_source_urls_from_text(text: str) -> list[str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if parsed is not None:
        source_urls = _find_value(parsed, "sourceUrls")
        return parse_source_urls(source_urls)
    return [decode_source_url(match) for match in re.findall(r'"sourceUrl":"([^"]+)"', text)]


def decode_source_url(source_url: str) -> str:
    value = source_url.removeprefix("--")
    if value == source_url:
        return value
    try:
        pairs = [value[index : index + 2] for index in range(0, len(value), 2)]
        decoded = "".join(_ENCODED_SOURCE_MAP.get(pair, "") for pair in pairs)
    except Exception:
        return value
    return decoded.replace("/clock", "/clock.json") or value


def build_persisted_query_url(show_id: str, mode: AnimeMode, episode: str, query_hash: str, *, api_url: str = ALLANIME_API) -> str:
    variables = quote(json.dumps({"showId": show_id, "translationType": mode, "episodeString": episode}, separators=(",", ":")))
    extensions = quote(json.dumps({"persistedQuery": {"version": 1, "sha256Hash": query_hash}}, separators=(",", ":")))
    return f"{api_url.rstrip('/')}/api?variables={variables}&extensions={extensions}"


def select_quality(streams: list[AnimeStream], quality: str = "best") -> AnimeStream | None:
    if not streams:
        return None
    ordered = sorted(streams, key=lambda item: _quality_sort_key(item.quality), reverse=True)
    if quality == "best":
        return ordered[0]
    if quality == "worst":
        return ordered[-1]
    return next((stream for stream in ordered if stream.quality == quality), ordered[0])


def _dedupe_streams(streams: list[AnimeStream]) -> list[AnimeStream]:
    seen: set[tuple[str, str]] = set()
    unique: list[AnimeStream] = []
    for stream in streams:
        key = (stream.quality, stream.url)
        if key not in seen:
            seen.add(key)
            unique.append(stream)
    return unique


def _episode_sort_key(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _quality_sort_key(value: str) -> int:
    match = re.search(r"(\d{3,4})", value)
    return int(match.group(1)) if match else 0


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _search_cache_key(query: str, mode: AnimeMode) -> str:
    return f"{mode}:{query.strip().casefold()}"


def _episodes_cache_key(show_id: str, mode: AnimeMode) -> str:
    return f"{mode}:{show_id}"


def _streams_cache_key(show_id: str, mode: AnimeMode, episode: str) -> str:
    return f"{mode}:{show_id}:{episode}"


def _search_result_from_dict(data: dict[str, Any]) -> AnimeSearchResult | None:
    show_id = data.get("show_id")
    title = data.get("title")
    if not isinstance(show_id, str) or not isinstance(title, str):
        return None
    return AnimeSearchResult(show_id=show_id, title=title, episode_count=_optional_int(data.get("episode_count")))


def _episode_from_dict(data: dict[str, Any]) -> AnimeEpisode | None:
    show_id = data.get("show_id")
    title = data.get("title")
    number = data.get("number")
    mode = data.get("mode", "sub")
    if not isinstance(show_id, str) or not isinstance(title, str) or not isinstance(number, str) or mode not in ("sub", "dub"):
        return None
    return AnimeEpisode(show_id=show_id, title=title, number=number, mode=mode)


def _stream_from_dict(data: dict[str, Any]) -> AnimeStream | None:
    url = data.get("url")
    quality = data.get("quality")
    title = data.get("title")
    episode = data.get("episode")
    show_id = data.get("show_id")
    mode = data.get("mode", "sub")
    referrer = data.get("referrer")
    subtitle_url = data.get("subtitle_url")
    if not isinstance(url, str) or not isinstance(quality, str) or not isinstance(title, str) or not isinstance(episode, str) or mode not in ("sub", "dub"):
        return None
    return AnimeStream(
        url=url,
        quality=quality,
        title=title,
        episode=episode,
        show_id=show_id if isinstance(show_id, str) else None,
        mode=mode,
        referrer=referrer if isinstance(referrer, str) else None,
        subtitle_url=subtitle_url if isinstance(subtitle_url, str) else None,
    )


def _stage_summary(stage: AnimeProviderStage) -> str:
    return {
        AnimeProviderStage.SEARCH: "Could not search anime",
        AnimeProviderStage.EPISODES: "Could not load episodes",
        AnimeProviderStage.EPISODE_SOURCES: "Could not load episode sources",
        AnimeProviderStage.FAST_PROVIDER: "Could not use the fast stream source",
        AnimeProviderStage.SLOW_PROVIDER: "Could not use fallback stream sources",
        AnimeProviderStage.M3U8_PARSE: "Could not parse the stream playlist",
        AnimeProviderStage.PLAYBACK_LOAD: "Could not load playback",
    }[stage]


def _stage_retry_hint(stage: AnimeProviderStage) -> str:
    if stage in {AnimeProviderStage.SEARCH, AnimeProviderStage.EPISODES, AnimeProviderStage.EPISODE_SOURCES}:
        return "Try again or choose another episode."
    if stage in {AnimeProviderStage.FAST_PROVIDER, AnimeProviderStage.SLOW_PROVIDER, AnimeProviderStage.M3U8_PARSE}:
        return "Try again or use another source."
    return "Try again or choose another stream."


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text)
    return _json_unescape(match.group(1)) if match else None


def _episode_data(data: dict[str, Any]) -> dict[str, Any] | None:
    episode = data.get("data", {}).get("episode") if isinstance(data.get("data"), dict) else None
    return episode if isinstance(episode, dict) else None


def _graphql_error_message(data: dict[str, Any]) -> str | None:
    errors = data.get("errors")
    if not isinstance(errors, list):
        return None
    messages = [item.get("message") for item in errors if isinstance(item, dict) and isinstance(item.get("message"), str)]
    return "; ".join(messages) if messages else None


def _find_value(data: object, key: str) -> object | None:
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = _find_value(value, key)
            if found is not None:
                return found
    if isinstance(data, list):
        for value in data:
            found = _find_value(value, key)
            if found is not None:
                return found
    return None


def _json_unescape(value: str) -> str:
    return value.replace("\\/", "/").replace("\\u002F", "/").replace("\\u0026", "&").replace("\\u003D", "=")


_ENCODED_SOURCE_MAP = {
    "79": "A",
    "7a": "B",
    "7b": "C",
    "7c": "D",
    "7d": "E",
    "7e": "F",
    "7f": "G",
    "70": "H",
    "71": "I",
    "72": "J",
    "73": "K",
    "74": "L",
    "75": "M",
    "76": "N",
    "77": "O",
    "68": "P",
    "69": "Q",
    "6a": "R",
    "6b": "S",
    "6c": "T",
    "6d": "U",
    "6e": "V",
    "6f": "W",
    "60": "X",
    "61": "Y",
    "62": "Z",
    "59": "a",
    "5a": "b",
    "5b": "c",
    "5c": "d",
    "5d": "e",
    "5e": "f",
    "5f": "g",
    "50": "h",
    "51": "i",
    "52": "j",
    "53": "k",
    "54": "l",
    "55": "m",
    "56": "n",
    "57": "o",
    "48": "p",
    "49": "q",
    "4a": "r",
    "4b": "s",
    "4c": "t",
    "4d": "u",
    "4e": "v",
    "4f": "w",
    "40": "x",
    "41": "y",
    "42": "z",
    "08": "0",
    "09": "1",
    "0a": "2",
    "0b": "3",
    "0c": "4",
    "0d": "5",
    "0e": "6",
    "0f": "7",
    "00": "8",
    "01": "9",
    "15": "-",
    "16": ".",
    "67": "_",
    "46": "~",
    "02": ":",
    "17": "/",
    "07": "?",
    "1b": "#",
    "63": "[",
    "65": "]",
    "78": "@",
    "19": "!",
    "1c": "$",
    "1e": "&",
    "10": "(",
    "11": ")",
    "12": "*",
    "13": "+",
    "14": ",",
    "03": ";",
    "05": "=",
    "1d": "%",
}
