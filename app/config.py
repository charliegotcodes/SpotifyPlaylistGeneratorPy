import os, re

CLIENT_ID     = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("SPOTIPY_REDIRECT_URI")

AUTH_URL      = "https://accounts.spotify.com/authorize"
TOKEN_URL     = "https://accounts.spotify.com/api/token"
API_BASE_URL  = "https://api.spotify.com/v1/"

SCOPE = ("user-read-private user-read-email "
         "playlist-read-private playlist-read-collaborative "
         "playlist-modify-private playlist-modify-public")

SPLIT_RE = re.compile(r"\s*(?:,|/|&| and )\s*", re.I)
CLEAN_RE = re.compile(r"[^A-Za-z0-9 .'\-&/]")