from spotipy import Spotify
from flask import current_app, session
import requests

def ensure_spotify():
    """Return an authenticated Spotify client and access token
    for the current Flask session. Refreshes the token if needed."""
    sp_oauth = current_app.config["SP_OAUTH"]
    if "token_info" not in session:
        return None, None

    token_info = session["token_info"]
     # Refresh if the current token has expired
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info

    access_token = token_info["access_token"]
    return Spotify(auth=access_token), access_token

def collect_meta_by_id(sp: Spotify, playlist_id: str) -> dict:
    """Collect track metadata (name, artist, URI) from a playlist
    and return a lookup dict keyed by track ID."""
    tracks = []
    data = sp.playlist_items(playlist_id, additional_types=["track"],
                             fields="items(track(id,name,uri,artists(name))),next",
                             limit=100)
    # Paginate through all playlist items
    while True:
        for item in data["items"]:
            t = item.get("track") or {}
            tid = t.get("id")
            if tid:
                tracks.append({
                    "id": tid,
                    "name": t["name"],
                    "artists": ", ".join(a["name"] for a in t.get("artists", [])),
                    "uri": t["uri"]
                })
        if data.get("next"):
            data = sp.next(data)
        else:
            break
    return {t["id"]: {"name": t["name"], "artists": t["artists"]} for t in tracks}

def get_artist_from_playlist(access_token, playlist_id):
    """Walk through a playlist via the Spotify Web API and
    collect parallel lists of artist names/IDs and track info."""
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    artist_names, artist_ids, track_ids, track_names = [], [], [], []
    while url:
        resp = requests.get(url, headers=headers).json()
        for item in resp.get("items", []):
            track = item.get("track")
            if not track: continue
            tid, tname = track.get("id"), track.get("name")
            if not tid or not tname: continue
            artists = track.get("artists", [])
            if not artists: continue
            main = artists[0]
            artist_ids.append(main.get("id"))
            artist_names.append(main.get("name"))
            track_ids.append(tid)
            track_names.append(tname)
        url = resp.get("next")
    return artist_names, artist_ids, track_ids, track_names