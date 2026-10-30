"""Blowfish key derivation and streaming decryption."""

from __future__ import annotations

from binascii import b2a_hex
from pathlib import Path

from Cryptodome.Cipher import Blowfish
from Cryptodome.Hash import MD5

from .constants import BF_IV, BF_SECRET, BLOCK, GROUP
from .errors import DeezerError
from .models import Progress, Quality


def blowfish_key(song_id: str) -> str:
    digest = b2a_hex(MD5.new(str(song_id).encode()).digest())
    return "".join(chr(digest[i] ^ digest[i + 16] ^ BF_SECRET[i]) for i in range(16))


def write_decrypted(
    response, out: Path, key: bytes | None, total: int, progress: Progress | None
) -> int:
    """Write a BF_CBC_STRIPE stream, decrypting every third 2048-byte block."""
    buffer = bytearray()
    written = 0
    block_index = 0
    step = max(total // 50, 1) if total else 0
    last = 0
    with out.open("wb") as handle:
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            buffer.extend(chunk)
            while len(buffer) >= GROUP:
                group = bytes(buffer[:GROUP])
                del buffer[:GROUP]
                head = group[:BLOCK]
                if key and block_index % 3 == 0:
                    head = Blowfish.new(key, Blowfish.MODE_CBC, BF_IV).decrypt(head)
                handle.write(head)
                handle.write(group[BLOCK:])
                written += GROUP
                block_index += 3
            if progress and total and written - last >= step:
                progress(written, total)
                last = written

        offset = 0
        while offset + BLOCK <= len(buffer):
            block = bytes(buffer[offset:offset + BLOCK])
            if key and block_index % 3 == 0:
                block = Blowfish.new(key, Blowfish.MODE_CBC, BF_IV).decrypt(block)
            handle.write(block)
            offset += BLOCK
            block_index += 1
            written += BLOCK
        if offset < len(buffer):
            rest = bytes(buffer[offset:])
            handle.write(rest)
            written += len(rest)

    if progress:
        progress(written, total or written)
    return written


def validate_audio(path: Path, quality: Quality) -> None:
    with path.open("rb") as handle:
        head = handle.read(4)
    if quality.suffix == ".flac" and head != b"fLaC":
        raise DeezerError("decrypted data is not FLAC")
    if quality.suffix == ".mp3" and not (
        head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
    ):
        raise DeezerError("decrypted data is not MP3")
