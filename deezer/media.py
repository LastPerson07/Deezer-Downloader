"""Stream resolution through media.deezer.com and the raw audio fetch."""

from __future__ import annotations

from pathlib import Path

import requests

from .catalog import Catalog
from .constants import MEDIA, UA
from .crypto import blowfish_key, validate_audio, write_decrypted
from .errors import DeezerError
from .gateway import Gateway
from .models import Progress, Quality, Stream, Track


class Media:
    def __init__(self, gateway: Gateway, catalog: Catalog) -> None:
        self.gateway = gateway
        self.catalog = catalog

    def stream(self, track: Track, wanted: Quality = Quality.FLAC_24) -> Stream:
        track = self.catalog.ensure(track)
        stream, errors = self._request(track, wanted)
        if stream:
            return stream

        # Some playlist rows carry a token for a ghost id; song.getData then
        # exposes a playable FALLBACK with a different SNG_ID.
        try:
            fallback = self.catalog.track(track.id)
        except DeezerError:
            fallback = None
        if fallback and (fallback.id != track.id or fallback.token != track.token):
            stream, fallback_errors = self._request(fallback, wanted)
            if stream:
                return stream
            errors = errors or fallback_errors

        raise DeezerError(f"no stream available{f': {errors}' if errors else ''}")

    def _request(self, track: Track, wanted: Quality) -> tuple[Stream | None, str | None]:
        if not self.gateway.license:
            raise DeezerError("no license token — this account cannot stream")
        body = {
            "license_token": self.gateway.license,
            "media": [
                {
                    "type": "FULL",
                    "formats": [
                        {"cipher": "BF_CBC_STRIPE", "format": quality.value}
                        for quality in Quality.ladder(wanted)
                    ],
                }
            ],
            "track_tokens": [track.token],
        }
        try:
            response = self.gateway.session().post(MEDIA, json=body, timeout=30)
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise DeezerError(f"media: {exc}") from exc
        if response.status_code != 200:
            raise DeezerError(f"media: HTTP {response.status_code}: {str(payload)[:200]}")

        for item in payload.get("data") or []:
            for media in item.get("media") or []:
                sources = [source.get("url") for source in media.get("sources") or [] if source.get("url")]
                if not sources:
                    continue
                quality = Quality.of(media.get("format") or "", sources[0])
                cipher = (media.get("cipher") or {}).get("type")
                return (
                    Stream(
                        quality=quality,
                        size=int(media.get("filesize") or track.size(quality) or 0),
                        urls=sources,
                        encrypted=cipher == "BF_CBC_STRIPE",
                        song_id=track.id,
                    ),
                    None,
                )

        errors = payload.get("errors") or payload.get("error")
        return None, str(errors)[:200] if errors else None

    def fetch(self, stream: Stream, part: Path, progress: Progress | None) -> None:
        key = blowfish_key(stream.song_id).encode() if stream.encrypted else None
        last_error: Exception | None = None
        for url in stream.urls:
            try:
                with self.gateway.session().get(
                    url, headers={"User-Agent": UA}, stream=True, timeout=60
                ) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length") or stream.size or 0)
                    written = write_decrypted(response, part, key, total, progress)
                if stream.size and written != stream.size:
                    raise DeezerError(f"short read {written}/{stream.size}")
                validate_audio(part, stream.quality)
                return
            except (requests.RequestException, DeezerError) as exc:
                last_error = exc
                part.unlink(missing_ok=True)
        raise DeezerError(f"stream download failed: {last_error}")

    def fetch_plain(self, url: str, part: Path, progress: Progress | None) -> int:
        """Podcast episodes stream unencrypted from the publisher's own host."""
        if not url:
            raise DeezerError("episode has no direct stream")
        try:
            with self.gateway.session().get(
                url, headers={"User-Agent": UA}, stream=True, timeout=60
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length") or 0)
                step = max(total // 50, 1) if total else 0
                written = last = 0
                with part.open("wb") as handle:
                    for chunk in response.iter_content(65536):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        written += len(chunk)
                        if progress and total and written - last >= step:
                            progress(written, total)
                            last = written
                if progress:
                    progress(written, total or written)
                if total and written != total:
                    raise DeezerError(f"short read {written}/{total}")
                validate_audio(part, Quality.MP3_128)
                return written
        except requests.RequestException as exc:
            part.unlink(missing_ok=True)
            raise DeezerError(f"episode stream failed: {exc}") from exc
        except DeezerError:
            part.unlink(missing_ok=True)
            raise
