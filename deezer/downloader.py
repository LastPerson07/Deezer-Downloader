"""One-track pipeline: resolve, fetch, decrypt, tag, publish."""

from __future__ import annotations

import warnings
from pathlib import Path

import requests

from .catalog import Catalog
from .errors import DeezerError
from .media import Media
from .models import Download, Episode, EpisodeDownload, Progress, Quality, Track
from .tagging import Tagger


class Downloader:
    def __init__(self, catalog: Catalog, media: Media, tagger: Tagger) -> None:
        self.catalog = catalog
        self.media = media
        self.tagger = tagger

    @staticmethod
    def _write_cover(folder: Path, artwork: bytes | None, enabled: bool) -> None:
        if enabled and artwork:
            cover = folder / "cover.jpg"
            if not cover.exists():
                cover.write_bytes(artwork)

    def download(
        self,
        track: Track,
        folder: Path,
        stem: str,
        wanted: Quality = Quality.FLAC_24,
        *,
        force: bool = False,
        cover: bool = True,
        lyrics: bool = True,
        progress: Progress | None = None,
        total_tracks: int = 0,
        save_cover: bool = False,
    ) -> Download:
        folder.mkdir(parents=True, exist_ok=True)
        order = list(Quality)
        for candidate in order[: order.index(wanted) + 1]:
            existing = folder / f"{stem}{candidate.suffix}"
            if existing.exists() and existing.stat().st_size > 0 and not force:
                # Only the extension is known here, so report the lowest quality
                # sharing it rather than claiming a bit depth the file may not have.
                on_disk = Quality.FLAC if candidate.suffix == ".flac" else Quality.MP3_128
                return Download(on_disk, existing, existing.stat().st_size, skipped=True)

        track = self.catalog.ensure(track)
        stream = self.media.stream(track, wanted)
        target = folder / f"{stem}{stream.quality.suffix}"
        if target.exists() and target.stat().st_size > 0 and not force:
            return Download(stream.quality, target, target.stat().st_size, skipped=True)

        part = target.with_name(target.name + ".part")
        part.unlink(missing_ok=True)
        self.media.fetch(stream, part, progress)

        artwork = None
        if cover and track.cover:
            try:
                artwork = self.tagger.cover(track.cover)
            except requests.RequestException:
                artwork = None
        self._write_cover(folder, artwork, save_cover)

        lyric = None
        if lyrics:
            try:
                lyric = self.tagger.lyrics(track.id)
            except DeezerError as exc:
                warnings.warn(f"{target.name}: {exc}", RuntimeWarning, stacklevel=2)
        if lyric and lyric.text:
            self.tagger.save_lrc(folder, stem, track, lyric)
        try:
            self.tagger.apply(
                part,
                track,
                stream.quality,
                lyric.text if lyric else "",
                artwork,
                total_tracks,
            )
        except DeezerError as exc:
            # The audio is already fetched; publishing it untagged beats discarding it.
            warnings.warn(f"{target.name}: {exc}", RuntimeWarning, stacklevel=2)

        part.replace(target)
        return Download(
            quality=stream.quality,
            path=target,
            size=target.stat().st_size,
        )

    def download_episode(
        self,
        episode: Episode,
        folder: Path,
        stem: str,
        *,
        force: bool = False,
        cover: bool = True,
        progress: Progress | None = None,
        save_cover: bool = False,
    ) -> EpisodeDownload:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{stem}.mp3"
        if target.exists() and target.stat().st_size > 0 and not force:
            return EpisodeDownload(target, target.stat().st_size, skipped=True)

        if not episode.direct_url:
            episode = self.catalog.episode(episode.id)
        if not episode.direct_url:
            raise DeezerError("episode has no direct stream")

        part = target.with_name(target.name + ".part")
        part.unlink(missing_ok=True)
        self.media.fetch_plain(episode.direct_url, part, progress)

        artwork = None
        if cover and episode.art:
            try:
                artwork = self.tagger.cover_talk(episode.art)
            except requests.RequestException:
                artwork = None
        self._write_cover(folder, artwork, save_cover)

        try:
            self.tagger.apply_episode(part, episode, artwork)
        except DeezerError as exc:
            warnings.warn(f"{target.name}: {exc}", RuntimeWarning, stacklevel=2)

        part.replace(target)
        return EpisodeDownload(path=target, size=target.stat().st_size)
