"""Covers, lyrics and audio tags."""

from __future__ import annotations

from pathlib import Path

from mutagen import MutagenError
from mutagen.flac import FLAC, Picture, VCFLACDict
from mutagen.id3 import (
    APIC,
    COMM,
    ID3,
    TALB,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    TSRC,
    USLT,
)

from .constants import COVER, TALK_COVER
from .errors import DeezerError
from .gateway import Gateway
from .models import Episode, Lyrics, Quality, Track


class Tagger:
    def __init__(self, gateway: Gateway) -> None:
        self.gateway = gateway
        self._covers: dict[str, bytes] = {}

    def cover(self, picture: str) -> bytes:
        cached = self._covers.get(picture)
        if cached is None:
            response = self.gateway.session().get(COVER.format(picture), timeout=30)
            response.raise_for_status()
            cached = response.content
            if len(self._covers) >= 128:
                self._covers.clear()
            self._covers[picture] = cached
        return cached

    def cover_talk(self, art: str) -> bytes:
        key = f"talk:{art}"
        cached = self._covers.get(key)
        if cached is None:
            response = self.gateway.session().get(TALK_COVER.format(art), timeout=30)
            response.raise_for_status()
            cached = response.content
            if len(self._covers) >= 128:
                self._covers.clear()
            self._covers[key] = cached
        return cached

    def lyrics(self, track_id: str) -> Lyrics:
        try:
            raw = self.gateway.call("song.getLyrics", {"sng_id": str(track_id)})
        except DeezerError as exc:
            # A track with no lyrics comes back as an error, not an empty result.
            # Anything else is a real failure and must not be mistaken for "none".
            if "no lyrics" in str(exc).lower():
                return Lyrics()
            raise
        return Lyrics(
            text=raw.get("LYRICS_TEXT") or "",
            synced=raw.get("LYRICS_SYNC_JSON") or None,
            writers=raw.get("LYRICS_WRITERS") or "",
            copyright=raw.get("LYRICS_COPYRIGHTS") or "",
        )

    def save_lrc(self, folder: Path, stem: str, track: Track, lyric: Lyrics) -> Path:
        path = folder / f"{stem}.lrc"
        header = [
            f"# Title: {track.title}",
            f"# Artist: {track.artist}",
            f"# Album: {track.album}",
            f"# Track: {track.number}",
        ]
        if track.year:
            header.append(f"# Date: {track.year}")
        if lyric.writers:
            header.append(f"# Writers: {lyric.writers}")
        if lyric.copyright:
            header.append(f"# Copyright: {lyric.copyright}")
        body = []
        if lyric.synced:
            for line in lyric.synced:
                if line.get("line"):
                    body.append(f"{line.get('lrc_timestamp') or ''} {line['line']}".strip())
        else:
            body = lyric.text.splitlines()
        path.write_text("\n".join(header) + "\n\n" + "\n".join(body) + "\n", encoding="utf-8")
        return path

    def apply(
        self,
        path: Path,
        track: Track,
        quality: Quality,
        lyrics: str,
        artwork: bytes | None,
        total_tracks: int,
    ) -> None:
        try:
            if quality.suffix == ".flac":
                tags = FLAC(path)
                if tags.tags is None:
                    tags.tags = VCFLACDict()
                tags["title"] = track.title
                tags["artist"] = track.artist
                tags["album"] = track.album
                tags["albumartist"] = track.album_artist or track.artist
                tags["tracknumber"] = str(track.number)
                tags["discnumber"] = str(track.disk)
                if total_tracks:
                    tags["tracktotal"] = str(total_tracks)
                if track.year:
                    tags["date"] = track.year
                if track.isrc:
                    tags["isrc"] = track.isrc
                tags["comment"] = track.link
                if lyrics:
                    tags["lyrics"] = lyrics
                if artwork:
                    picture = Picture()
                    vars(picture).update(type=3, mime="image/jpeg", data=artwork)  # 3 = front cover
                    tags.add_picture(picture)
                tags.save()
            else:
                try:
                    id3 = ID3(path)
                except MutagenError:
                    id3 = ID3()
                id3.add(TIT2(encoding=3, text=track.title))
                id3.add(TPE1(encoding=3, text=track.artist))
                id3.add(TPE2(encoding=3, text=track.album_artist or track.artist))
                id3.add(TALB(encoding=3, text=track.album))
                id3.add(TRCK(encoding=3, text=str(track.number)))
                id3.add(TPOS(encoding=3, text=str(track.disk)))
                id3.add(COMM(encoding=3, lang="eng", desc="", text=track.link))
                if track.year:
                    id3.add(TDRC(encoding=3, text=track.year))
                if track.isrc:
                    id3.add(TSRC(encoding=3, text=track.isrc))
                if lyrics:
                    id3.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
                if artwork:
                    id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=artwork))
                id3.save(path)
        except Exception as exc:
            raise DeezerError(f"tagging failed: {exc}") from exc

    def apply_episode(self, path: Path, episode: Episode, artwork: bytes | None) -> None:
        try:
            try:
                tags = ID3(path)
            except MutagenError:
                tags = ID3()
            tags.delall("COMM")
            tags.delall("APIC")
            tags.add(TIT2(encoding=3, text=episode.title))
            tags.add(TPE1(encoding=3, text=episode.show))
            tags.add(TPE2(encoding=3, text=episode.show))
            tags.add(TALB(encoding=3, text=episode.show))
            tags.add(TCON(encoding=3, text="Podcast"))
            tags.add(COMM(encoding=3, lang="eng", desc="", text=episode.link))
            if episode.published:
                tags.add(TDRC(encoding=3, text=episode.published))
            if artwork:
                tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=artwork))
            tags.save(path)
        except Exception as exc:
            raise DeezerError(f"tagging failed: {exc}") from exc
