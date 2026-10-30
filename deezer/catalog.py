"""Catalog lookups: tracks, albums, playlists, artists, podcasts, search."""

from __future__ import annotations

import re
from urllib.parse import unquote

import requests

from .errors import DeezerError
from .gateway import Gateway
from .models import AlbumRef, ArtistPage, Collection, Episode, Show, Track

_KIND = r"(track|album|playlist|artist|show|episode)"
_LINK = re.compile(rf"deezer\.com/(?:[\w-]+/)?{_KIND}/(\d+)")
_REDIRECT = re.compile(rf"{_KIND}[=/](\d+)")


def _album_size(value: dict | None) -> int:
    if not value:
        return 0
    return int(value.get("total") or len(value.get("data") or []))


class Catalog:
    def __init__(self, gateway: Gateway) -> None:
        self.gateway = gateway

    def resolve(self, text: str) -> tuple[str, str] | None:
        text = text.strip()
        if match := _LINK.search(text):
            return match.group(1), match.group(2)
        if text.isdigit():
            return "track", text
        if text.startswith("http") or "link.deezer.com" in text:
            url = text if text.startswith("http") else f"https://link.deezer.com/s/{text}"
            try:
                response = self.gateway.session().get(url, allow_redirects=False, timeout=20)
            except requests.RequestException:
                return None
            location = unquote(response.headers.get("Location", ""))
            if match := _REDIRECT.search(location):
                return match.group(1), match.group(2)
            return None
        if len(text) > 10 and "/" not in text:
            return self.resolve(f"https://link.deezer.com/s/{text}")
        return None

    def track(self, track_id: str) -> Track:
        raw = self.gateway.call("song.getData", {"sng_id": str(track_id)})
        raw = raw.get("FALLBACK") or raw
        if not raw.get("SNG_ID"):
            raise DeezerError("track not found")
        return Track.from_raw(raw)

    def ensure(self, track: Track) -> Track:
        return track if track.token and track.md5 else self.track(track.id)

    def album(self, album_id: str) -> Collection:
        raw = self.gateway.call("deezer.pageAlbum", {"alb_id": str(album_id), "lang": "en"})
        data = raw.get("DATA") or {}
        rows = ((raw.get("SONGS") or {}).get("data")) or []
        expected = int(data.get("NUMBER_TRACK") or 0)
        if expected and len(rows) < expected:
            rows = self._album_tracks(album_id)
        if not rows:
            raise DeezerError("album not found")
        tracks = [Track.from_raw(row) for row in rows]
        return Collection(
            kind="album",
            title=data.get("ALB_TITLE") or tracks[0].album,
            artist=data.get("ART_NAME") or tracks[0].album_artist,
            tracks=tracks,
        )

    def _album_tracks(self, album_id: str) -> list[dict]:
        rows: list[dict] = []
        start = 0
        while True:
            page = self.gateway.call(
                "song.getListByAlbum", {"alb_id": str(album_id), "start": start, "nb": 100}
            )
            chunk = page.get("data") or []
            rows.extend(chunk)
            start += len(chunk)
            if not chunk or start >= int(page.get("total") or 0):
                break
        return rows

    def playlist(self, playlist_id: str) -> Collection:
        raw = self.gateway.call("deezer.pagePlaylist", {"playlist_id": str(playlist_id), "lang": "en"})
        data = raw.get("DATA") or {}
        tracks = self._playlist_tracks(playlist_id)
        if not tracks:
            raise DeezerError("playlist not found or empty")
        creator = data.get("CREATOR") or {}
        return Collection(
            kind="playlist",
            title=data.get("TITLE") or "Playlist",
            artist=creator.get("NAME") or self.gateway.user,
            tracks=tracks,
        )

    def _playlist_tracks(self, playlist_id: str) -> list[Track]:
        tracks: list[Track] = []
        start = 0
        while True:
            page = self.gateway.call(
                "playlist.getSongs", {"playlist_id": str(playlist_id), "start": start, "nb": 100}
            )
            chunk = page.get("data") or []
            tracks.extend(Track.from_raw(row) for row in chunk)
            start += len(chunk)
            if not chunk or start >= int(page.get("total") or 0):
                break
        return tracks

    def artist(self, art_id: str) -> ArtistPage:
        raw = self.gateway.call("deezer.pageArtist", {"art_id": str(art_id), "lang": "en"})
        data = raw.get("DATA") or {}
        albums = ((raw.get("ALBUMS") or {}).get("data")) or []
        return ArtistPage(
            name=data.get("ART_NAME") or "Unknown",
            albums=[
                AlbumRef(
                    id=str(row.get("ALB_ID") or ""),
                    title=row.get("ALB_TITLE") or "Unknown",
                    year=(row.get("PHYSICAL_RELEASE_DATE") or row.get("DIGITAL_RELEASE_DATE") or "")[:4],
                    tracks=_album_size(row.get("SONGS")),
                )
                for row in albums
            ],
        )

    def show(self, show_id: str, start: int = 0, nb: int = 15) -> Show:
        raw = self.gateway.call(
            "deezer.pageShow",
            {"show_id": str(show_id), "start": int(start), "nb": int(nb), "lang": "en"},
        )
        data = raw.get("DATA") or {}
        block = raw.get("EPISODES") or {}
        rows = block.get("data") or []
        if not data.get("SHOW_ID") and not rows:
            raise DeezerError("show not found")
        return Show(
            title=data.get("SHOW_NAME") or "Podcast",
            total=int(block.get("total") or len(rows)),
            episodes=[Episode.from_raw(row) for row in rows],
        )

    def episode(self, episode_id: str) -> Episode:
        raw = self.gateway.call("episode.getData", {"episode_id": str(episode_id)})
        if not raw.get("EPISODE_ID"):
            raise DeezerError("episode not found")
        return Episode.from_raw(raw)

    def search(self, query: str, limit: int = 10) -> list[Track]:
        raw = self.gateway.call(
            "deezer.pageSearch",
            {
                "query": query,
                "start": 0,
                "nb": limit,
                "suggest": False,
                "artist_suggest": False,
                "top_tracks": False,
            },
        )
        rows = ((raw.get("TRACK") or {}).get("data")) or []
        return [Track.from_raw(row) for row in rows]
