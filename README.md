<div align="center">

# Deezer-Downloader

A CLI downloader for Deezer. Paste a link or type a search, pick what you want, and get FLAC or MP3 files with tags, cover art and lyrics attached. There are no flags or config files.

[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/) [![Dependencies](https://img.shields.io/badge/dependencies-3-informational)](requirements.txt) [![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](#requirements) [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

[Usage](#usage) · [Output](#output) · [Quality](#quality) · [Notes](#notes)

</div>

```text
quality  1. 24-bit FLAC   2. FLAC (16-bit)   3. MP3 320   4. MP3 128
pick        : 1
username  lossless  FR  24-bit FLAC
link, search, 'quality' to change it, enter to quit

search/link : Attention
   1. Charlie Puth - Attention  [FLAC]
   2. Coral Reef - Attention  [FLAC]
   3. NewJeans - Attention  [FLAC]

pick        : 1
Charlie Puth - Attention
  [########################] 100.0%    23.8/23.8 MB
  saved    Charlie Puth - Attention.flac  FLAC (16-bit), 23.8 MB, 4.5s

search/link : https://www.deezer.com/track/578698542
Mathew V - Home
  [########################] 100.0%    18.1/18.1 MB
  saved    Mathew V - Home.flac  FLAC (16-bit), 18.1 MB, 7.6s

search/link :
```

## Requirements

- Python 3.11+
- A Deezer account. Free accounts get MP3 128; 320 and FLAC need a paid tier

```bash
pip install -r requirements.txt
```

The dependencies are `requests`, `pycryptodomex` and `mutagen`.

## Login

The downloader reads the `arl` cookie from a logged-in browser session.

```text
deezer.com -> DevTools -> Application -> Cookies -> arl
```

Paste it when prompted. It goes into `cookies.txt` next to the script and is reused on every later run, so you only do this once. Delete the file to switch accounts.

That cookie is the whole session. Treat it like a password and keep it out of the repository.

## Usage

```bash
python Deezer.py
```

Pick a quality, then paste a link or type a search.

The prompt accepts:

- `https://www.deezer.com/track/66609426`, and the same shape for `album`, `playlist`, `artist`, `show` and `episode`
- `66609426`, a bare track id
- `34LBa8KcAfAMzrpmMXPH8`, a `link.deezer.com/s/` share code
- `daft punk get lucky`, which is treated as a search

Type `quality` at the prompt to reopen the menu without restarting. An empty line quits.

An artist lists its albums and a show lists its episodes 15 at a time. Both ask which one you want before anything downloads.

## Output

Everything goes into `downloads/` next to the script, whichever directory you run it from.

```text
downloads/Charlie Puth - Attention.flac               single track
downloads/Mathew V - Home/01 - Home.flac              album
downloads/En mode 60/01 - The Beatles - Hey Jude.mp3  playlist
```

Podcast episodes get a folder named after the show, with one MP3 per episode. Multi-disc albums prefix the track number with the disc, as in `1-01 - Back In The U.S.S.R.flac`.

The downloader writes a `.lrc` sidecar when Deezer has lyrics for the track, and saves one `cover.jpg` per folder.

FLAC files get Vorbis comments and MP3 files get ID3v2.4 frames. Both get the cover art embedded. Re-running a job skips anything already present at the same or better quality, so an interrupted album picks up where it stopped.

## Quality

The four options map to Deezer's formats, and the server decides what you get. A 24-bit request asks for `FLAC_24`, `FLAC`, `MP3_320` and `MP3_128` in that order, then takes the best one available.

Most of the catalogue has no hi-res master. Picking 24-bit on an ordinary album gets you 16-bit FLAC, because that is all Deezer holds for it.

The menu only lists what your account can stream, so a free account never sees FLAC or 320.

## Notes

- Audio arrives encrypted. The downloader decrypts 2048-byte blocks, every third one, using a key derived from the track id and Deezer's static secret.
- Some playlist rows carry a token for an id that no longer streams. The gateway answers with a fallback id holding the same audio, and the stream is fetched against that one.
- Podcasts never reach the media service. Episodes come as plain MP3 from the publisher's host, so nothing is decrypted.
- Albums and playlists come back 100 tracks per request, shows 15 episodes per request, so long ones take several calls.
- The `arl` cookie lasts a long time but not forever. If every request starts failing on auth, grab a fresh one.

## -:-

This project is not affiliated with or endorsed by Deezer. Downloading content you don't have the rights to may violate Deezer's terms of service or local law. Use it with your own account, for content you're entitled to.
