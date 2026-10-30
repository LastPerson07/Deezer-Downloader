"""Catalog and download data structures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

Progress = Callable[[int, int], None]


class Quality(StrEnum):
    FLAC_24 = "FLAC_24"
    FLAC = "FLAC"
    MP3_320 = "MP3_320"
    MP3_128 = "MP3_128"

    @property
    def label(self) -> str:
        return {
            Quality.FLAC_24: "24-bit FLAC",
            Quality.FLAC: "FLAC (16-bit)",
            Quality.MP3_320: "MP3 320",
            Quality.MP3_128: "MP3 128",
        }[self]

    @property
    def suffix(self) -> str:
        return ".flac" if self in (Quality.FLAC_24, Quality.FLAC) else ".mp3"

    @classmethod
    def ladder(cls, wanted: Quality) -> list[Quality]:
        order = list(cls)
        return order[order.index(wanted):]

    @classmethod
    def of(cls, value: str, url: str = "") -> Quality:
        value = (value or "").upper()
        for quality in cls:
            if quality.value == value:
                return quality
        return cls.FLAC if url.lower().endswith(".flac") else cls.MP3_128


@dataclass(slots=True)
class Track:
    id: str
    title: str
    artist: str
    album: str
    album_artist: str
    cover: str
    number: int
    disk: int
    year: str
    isrc: str
    token: str
    md5: str
    size_24: int
    size_flac: int
    size_320: int
    size_128: int

    @property
    def link(self) -> str:
        return f"https://www.deezer.com/track/{self.id}"

    def size(self, quality: Quality) -> int:
        return {
            Quality.FLAC_24: self.size_24,
            Quality.FLAC: self.size_flac,
            Quality.MP3_320: self.size_320,
            Quality.MP3_128: self.size_128,
        }[quality]

    @classmethod
    def from_raw(cls, raw: dict) -> Track:
        artist = raw.get("ART_NAME") or next(
            (row["ART_NAME"] for row in raw.get("ARTISTS") or [] if row.get("ART_NAME")),
            "Unknown",
        )
        return cls(
            id=str(raw.get("SNG_ID") or ""),
            title=raw.get("SNG_TITLE") or "Unknown",
            artist=artist,
            album=raw.get("ALB_TITLE") or "Unknown",
            album_artist=raw.get("ART_NAME") or artist,
            cover=raw.get("ALB_PICTURE") or "",
            number=int(raw.get("TRACK_NUMBER") or 1),
            disk=int(raw.get("DISK_NUMBER") or 1),
            year=(raw.get("PHYSICAL_RELEASE_DATE") or raw.get("DIGITAL_RELEASE_DATE") or "")[:4],
            isrc=raw.get("ISRC") or "",
            token=raw.get("TRACK_TOKEN") or "",
            md5=raw.get("MD5_ORIGIN") or "",
            size_24=int(raw.get("FILESIZE_FLAC_24") or 0),
            size_flac=int(raw.get("FILESIZE_FLAC") or 0),
            size_320=int(raw.get("FILESIZE_MP3_320") or 0),
            size_128=int(raw.get("FILESIZE_MP3_128") or 0),
        )


@dataclass(slots=True)
class Collection:
    kind: str
    title: str
    artist: str
    tracks: list[Track]


@dataclass(slots=True)
class AlbumRef:
    id: str
    title: str
    year: str
    tracks: int


@dataclass(slots=True)
class ArtistPage:
    name: str
    albums: list[AlbumRef]


@dataclass(slots=True)
class Lyrics:
    text: str = ""
    synced: list[dict] | None = None
    writers: str = ""
    copyright: str = ""


@dataclass(slots=True)
class Episode:
    id: str
    title: str
    show: str
    duration: int
    published: str
    direct_url: str
    art: str

    @property
    def link(self) -> str:
        return f"https://www.deezer.com/episode/{self.id}"

    @classmethod
    def from_raw(cls, raw: dict) -> Episode:
        return cls(
            id=str(raw.get("EPISODE_ID") or ""),
            title=raw.get("EPISODE_TITLE") or "Episode",
            show=raw.get("SHOW_NAME") or "Podcast",
            duration=int(raw.get("DURATION") or 0),
            published=str(
                raw.get("EPISODE_PUBLISHED_TIMESTAMP") or raw.get("EPISODE_PUBLISHED_TS") or ""
            )[:10],
            direct_url=raw.get("EPISODE_DIRECT_STREAM_URL") or "",
            art=raw.get("SHOW_ART_MD5") or "",
        )


@dataclass(slots=True)
class Show:
    title: str
    total: int
    episodes: list[Episode]


@dataclass(slots=True)
class EpisodeDownload:
    path: Path
    size: int
    skipped: bool = False


@dataclass(slots=True)
class Stream:
    quality: Quality
    size: int
    urls: list[str]
    encrypted: bool
    song_id: str = ""


@dataclass(slots=True)
class Download:
    quality: Quality
    path: Path
    size: int
    skipped: bool = False
