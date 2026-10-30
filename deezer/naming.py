"""Folder and filename helpers."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Collection, Track

RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}


def safe_name(text: str) -> str:
    cleaned = re.sub(r'[\\/*?:"<>|\x00-\x1f]', "", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:150]
    if cleaned.upper() in RESERVED:
        cleaned += "_"
    return cleaned or "track"


def collection_folder(out: Path, collection: Collection) -> Path:
    if collection.kind == "album":
        return out / safe_name(f"{collection.artist} - {collection.title}")
    return out / safe_name(collection.title)


def track_stem(track: Track, collection: Collection, position: int, total: int) -> str:
    width = max(2, len(str(total))) if total else 2
    if collection.kind == "album":
        prefix = f"{track.disk}-{track.number:02d}" if _max_disc(collection) > 1 else f"{track.number:0{width}d}"
        return safe_name(f"{prefix} - {track.title}")
    if collection.kind == "playlist":
        return safe_name(f"{position:0{width}d} - {track.artist} - {track.title}")
    return safe_name(f"{position:0{width}d} - {track.title}")


def _max_disc(collection: Collection) -> int:
    return max((track.disk for track in collection.tracks), default=1)


def single_stem(track: Track) -> str:
    return safe_name(f"{track.artist} - {track.title}")
