"""Deezer downloader CLI."""

from __future__ import annotations

import re
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=r"urllib3 .*doesn't match a supported version")

from deezer import (
    Collection,
    Deezer,
    DeezerError,
    Download,
    Episode,
    EpisodeDownload,
    Quality,
    Track,
    collection_folder,
    safe_name,
    single_stem,
    track_stem,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
COOKIE = ROOT / "cookies.txt"
OUTPUT = ROOT / "downloads"
SHARE = re.compile(r"[A-Za-z0-9]{14,}")
TIERS = {
    "lossless": [Quality.FLAC_24, Quality.FLAC, Quality.MP3_320, Quality.MP3_128],
    "high": [Quality.MP3_320, Quality.MP3_128],
    "free": [Quality.MP3_128],
}


def parse_arl(raw: str) -> str:
    text = raw.strip().strip('"')
    if "arl=" in text:
        text = text.split("arl=", 1)[1].split(";", 1)[0]
    return text.strip()


def stored_arl() -> str:
    return parse_arl(COOKIE.read_text(encoding="utf-8")) if COOKIE.exists() else ""


def ask(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        return input(f"{label:<12}{hint}: ").strip() or default
    except EOFError:
        print()
        return default


def pick(count: int, label: str = "pick") -> int | None:
    raw = ask(label)
    if not raw.isdigit():
        return None
    value = int(raw)
    return value if 1 <= value <= count else None


def mb(size: int) -> str:
    return f"{size / 1048576:.1f} MB"


def hms(seconds: int) -> str:
    minutes, secs = divmod(max(int(seconds or 0), 0), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class Bar:
    def __init__(self) -> None:
        self.drawn = False

    def __call__(self, done: int, total: int) -> None:
        if not total:
            return
        share = min(done / total, 1.0)
        filled = int(share * 24)
        print(
            f"\r  [{'#' * filled}{'-' * (24 - filled)}] {share * 100:5.1f}%"
            f"  {done / 1048576:6.1f}/{total / 1048576:.1f} MB",
            end="",
            flush=True,
        )
        self.drawn = True

    def close(self) -> None:
        if self.drawn:
            print()


def report(bar: Bar, started: float, got: Download | EpisodeDownload) -> None:
    bar.close()
    if got.skipped:
        print(f"  skipped  {got.path.name}")
        return
    tag = f"{got.quality.label}, " if isinstance(got, Download) else ""
    print(f"  saved    {got.path.name}  {tag}{mb(got.size)}, {time.perf_counter() - started:.1f}s")


def choose_quality(client: Deezer) -> Quality:
    options = TIERS.get(client.tier, TIERS["free"])
    print("quality  " + "   ".join(f"{i}. {q.label}" for i, q in enumerate(options, 1)))
    return options[(pick(len(options)) or 1) - 1]


def grab_track(client: Deezer, track: Track, quality: Quality) -> None:
    print(f"{track.artist} - {track.title}")
    bar, started = Bar(), time.perf_counter()
    try:
        got = client.download(
            track, OUTPUT, single_stem(track), quality, progress=bar, save_cover=True
        )
    except DeezerError as exc:
        bar.close()
        print(f"  failed   {exc}")
        return
    report(bar, started, got)


def grab_episode(client: Deezer, episode: Episode) -> None:
    print(f"{episode.title}  [{hms(episode.duration)}]")
    bar, started = Bar(), time.perf_counter()
    try:
        got = client.download_episode(
            episode,
            OUTPUT / safe_name(episode.show),
            safe_name(episode.title),
            progress=bar,
            save_cover=True,
        )
    except DeezerError as exc:
        bar.close()
        print(f"  failed   {exc}")
        return
    report(bar, started, got)


def grab_collection(client: Deezer, collection: Collection, quality: Quality) -> None:
    folder = collection_folder(OUTPUT, collection)
    total = len(collection.tracks)
    print(f"{collection.title} - {collection.artist} ({total} tracks)")
    saved = skipped = failed = 0

    for index, track in enumerate(collection.tracks, 1):
        print(f"[{index}/{total}] {track.artist} - {track.title}")
        bar, started = Bar(), time.perf_counter()
        try:
            got = client.download(
                track,
                folder,
                track_stem(track, collection, index, total),
                quality,
                progress=bar,
                total_tracks=total,
                save_cover=True,
            )
        except (DeezerError, OSError) as exc:
            bar.close()
            failed += 1
            print(f"  failed   {exc}")
            continue
        bar.close()
        if got.skipped:
            skipped += 1
            print("  skipped")
        else:
            saved += 1
            print(f"  saved    {got.quality.label}, {mb(got.size)}, {time.perf_counter() - started:.1f}s")

    print(f"{saved} saved, {skipped} skipped, {failed} failed")
    print(f"folder   {folder}")


def browse_show(client: Deezer, show_id: str) -> None:
    start, size = 0, 15
    while True:
        page = client.show(show_id, start, size)
        if not page.episodes:
            print("no episodes")
            return
        print(f"{page.title}  {start + 1}-{start + len(page.episodes)} of {page.total}")
        for index, episode in enumerate(page.episodes, 1):
            print(f"  {index:2}. {episode.title}  [{hms(episode.duration)}] {episode.published}")

        raw = ask("n/p/number").lower()
        if not raw:
            return
        if raw in ("n", "next"):
            if start + size < page.total:
                start += size
            else:
                print("last page")
            continue
        if raw in ("p", "prev", "b"):
            start = max(start - size, 0)
            continue
        choice = int(raw) if raw.isdigit() else 0
        if 1 <= choice <= len(page.episodes):
            grab_episode(client, page.episodes[choice - 1])
            return
        print("invalid")


def search(client: Deezer, query: str) -> Track | None:
    results = client.search(query, 10)
    if not results:
        print("no results")
        return None
    for index, track in enumerate(results, 1):
        tag = "FLAC" if track.size_flac or track.size_24 else "MP3"
        print(f"  {index:2}. {track.artist} - {track.title}  [{tag}]")
    choice = pick(len(results))
    return results[choice - 1] if choice else None


def pick_album(client: Deezer, artist_id: str) -> Collection | None:
    page = client.artist(artist_id)
    if not page.albums:
        print("no albums")
        return None
    print(f"{page.name} - {len(page.albums)} albums")
    for index, album in enumerate(page.albums, 1):
        print(f"  {index:2}. {album.title} ({album.year or '?'}, {album.tracks} tracks)")
    choice = pick(len(page.albums))
    return client.album(page.albums[choice - 1].id) if choice else None


def handle(client: Deezer, target: str, quality: Quality) -> None:
    lowered = target.lower()
    if lowered in ("q", "quit", "exit"):
        raise SystemExit

    if target.isdigit() or "deezer.com" in lowered or SHARE.fullmatch(target):
        resolved = client.resolve(target)
        if resolved:
            match resolved:
                case ("track", ident):
                    grab_track(client, client.track(ident), quality)
                case ("album", ident):
                    grab_collection(client, client.album(ident), quality)
                case ("playlist", ident):
                    grab_collection(client, client.playlist(ident), quality)
                case ("artist", ident):
                    album = pick_album(client, ident)
                    if album:
                        grab_collection(client, album, quality)
                case ("show", ident):
                    browse_show(client, ident)
                case ("episode", ident):
                    grab_episode(client, client.episode(ident))
            return
        if "deezer.com" in lowered:
            print("unsupported link")
            return

    found = search(client, target)
    if found:
        grab_track(client, found, quality)


def connect() -> Deezer | None:
    arl = stored_arl()
    if arl:
        try:
            return Deezer(arl)
        except DeezerError as exc:
            print(f"session  {exc}")

    print("deezer.com > devtools > application > cookies > arl")
    arl = parse_arl(ask("arl"))
    if not arl:
        return None
    try:
        client = Deezer(arl)
    except DeezerError as exc:
        print(f"login    {exc}")
        return None
    COOKIE.write_text(arl + "\n", encoding="utf-8")
    return client


def LastPerson07() -> None:
    client = connect()
    if not client:
        return
    quality = choose_quality(client)
    print(f"{client.user}  {client.tier}  {client.country or '?'}  {quality.label}")
    print("link, search, 'quality' to change it, enter to quit")

    while True:
        try:
            target = ask("search/link")
        except KeyboardInterrupt:
            print()
            return
        if not target:
            return
        if target.lower() == "quality":
            quality = choose_quality(client)
            continue
        try:
            handle(client, target, quality)
        except DeezerError as exc:
            print(f"failed   {exc}")
        print()


if __name__ == "__main__":
    try:
        LastPerson07()
    except KeyboardInterrupt:
        print()
