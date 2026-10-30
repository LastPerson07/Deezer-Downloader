"""Endpoints, browser identity and Blowfish constants."""

GW = "https://www.deezer.com/ajax/gw-light.php"
MEDIA = "https://media.deezer.com/v1/get_url"
COVER = "https://e-cdns-images.dzcdn.net/images/cover/{}/1000x1000-000000-80-0-0.jpg"
TALK_COVER = "https://cdn-images.dzcdn.net/images/talk/{}/1000x1000.jpg"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

BF_SECRET = b"g4el58wc0zvf9na1"
BF_IV = bytes(range(8))
BLOCK = 2048
GROUP = BLOCK * 3
