"""Deezer terminal engine.

Catalog calls use the web player gateway; audio comes from
``media.deezer.com/v1/get_url`` as BF_CBC_STRIPE-encrypted FLAC or MP3.
"""

from .client import Deezer
from .errors import DeezerError
from .models import (
    AlbumRef,
    ArtistPage,
    Collection,
    Download,
    Episode,
    EpisodeDownload,
    Lyrics,
    Progress,
    Quality,
    Show,
    Stream,
    Track,
)
from .naming import (
    collection_folder,
    safe_name,
    single_stem,
    track_stem,
)

__all__ = [
    "AlbumRef",
    "ArtistPage",
    "Collection",
    "Deezer",
    "DeezerError",
    "Download",
    "Episode",
    "EpisodeDownload",
    "Lyrics",
    "Progress",
    "Quality",
    "Show",
    "Stream",
    "Track",
    "collection_folder",
    "safe_name",
    "single_stem",
    "track_stem",
]
