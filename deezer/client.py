"""Facade that wires the gateway, catalog, media, tagger and downloader."""

from __future__ import annotations

from pathlib import Path

from .catalog import Catalog
from .downloader import Downloader
from .gateway import Gateway
from .media import Media
from .models import (
    ArtistPage,
    Collection,
    Download,
    Episode,
    EpisodeDownload,
    Progress,
    Quality,
    Show,
    Track,
)
from .tagging import Tagger


class Deezer:
    def __init__(self, arl: str) -> None:
        self.gateway = Gateway(arl)
        self.catalog = Catalog(self.gateway)
        self.tagger = Tagger(self.gateway)
        self.media = Media(self.gateway, self.catalog)
        self.downloader = Downloader(self.catalog, self.media, self.tagger)

    @property
    def user(self) -> str:
        return self.gateway.user

    @property
    def tier(self) -> str:
        return self.gateway.tier

    @property
    def country(self) -> str:
        return self.gateway.country

    def resolve(self, text: str) -> tuple[str, str] | None:
        return self.catalog.resolve(text)

    def track(self, track_id: str) -> Track:
        return self.catalog.track(track_id)

    def album(self, album_id: str) -> Collection:
        return self.catalog.album(album_id)

    def playlist(self, playlist_id: str) -> Collection:
        return self.catalog.playlist(playlist_id)

    def artist(self, art_id: str) -> ArtistPage:
        return self.catalog.artist(art_id)

    def show(self, show_id: str, start: int = 0, nb: int = 15) -> Show:
        return self.catalog.show(show_id, start, nb)

    def episode(self, episode_id: str) -> Episode:
        return self.catalog.episode(episode_id)

    def search(self, query: str, limit: int = 10) -> list[Track]:
        return self.catalog.search(query, limit)

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
        return self.downloader.download(
            track,
            folder,
            stem,
            wanted,
            force=force,
            cover=cover,
            lyrics=lyrics,
            progress=progress,
            total_tracks=total_tracks,
            save_cover=save_cover,
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
        return self.downloader.download_episode(
            episode,
            folder,
            stem,
            force=force,
            cover=cover,
            progress=progress,
            save_cover=save_cover,
        )
