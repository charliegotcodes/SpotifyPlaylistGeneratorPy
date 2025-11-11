import time
import numpy as np
import logging
from spotipy import Spotify
from flask import session
from .spotify_api import get_artist_from_playlist
from .lyrics_getter import get_lyrics 
from .lyrics_embedding import generate_and_store_embedding, find_similar_songs
from .supabase_db import SUPABASE_ANON as supabase
from .utils import is_duplicate_song 

log = logging.getLogger("playlistgen")

def generate_playlist_from_seed(sp: Spotify, access_token: str, playlist_id: str, playlist_name="Generated Mix"):
    """Generate a new playlist based on the lyrical similarity of an existing one."""
    t0 = time.perf_counter()
    spotify_id = session.get("spotify_id")
    log.info("gen: start | pid=%s name=%s", playlist_id, playlist_name)

   # Pull all tracks and primary artists from the seed playlist
    seed_artists, seed_ids, track_ids, track_names = get_artist_from_playlist(access_token, playlist_id)
    log.info("gen: seeds | tracks=%d", len(track_ids))

    # Deduplicate seed tracks (same artist or near-identical title)
    seen_sigs = set() 
    unique_seeds = []
    for tid, tname, aname in zip(track_ids, track_names, seed_artists):
        sig = f"{aname}:{tname}"
        if is_duplicate_song(tname, aname, seen_sigs, threshold=0.90):
            log.info("gen: skip duplicate seed | %s — %s", aname, tname)
            continue
        seen_sigs.add(sig)
        unique_seeds.append((tid, tname, aname))
    log.info("gen: unique seeds | count=%d", len(unique_seeds))

    # Fetch lyrics and build embeddings for each unique seed track
    embeddings = []
    for i, (tid, tname, aname) in enumerate(unique_seeds, start=1):
        log.info("gen: [%d/%d] lyrics | %s — %s", i, len(unique_seeds), aname, tname)
        lyrics = get_lyrics(tname, aname)
        if not lyrics:
            log.warning("gen: no lyrics | %s — %s", aname, tname)
            continue
        emb = generate_and_store_embedding(tid, tname, aname, lyrics)
        if emb:
            embeddings.append(emb)
            log.info("gen: embedded ✓ | total=%d", len(embeddings))

    if not embeddings:
        log.error("gen: abort — no embeddings created")
        return None

    # Average seed embeddings => overall "playlist mood" vector
    playlist_vec = list(np.mean(np.array(embeddings), axis=0))

    # Vector search for lyrically similar songs
    similar_songs = find_similar_songs(playlist_vec, top_n=50) or []
    log.info("gen: similar_songs | count=%d", len(similar_songs))

    # Resolve matches to Spotify URIs while avoiding duplicates or variants
    track_uris, added_sigs = [], set(seed_artists[i] + ":" + track_names[i] for i in range(len(track_ids)))
    for s in similar_songs:
        cand_title = s.get("track_name") or ""
        cand_artist = s.get("artist_name") or ""
        if is_duplicate_song(cand_title, cand_artist, added_sigs, threshold=0.90):
            log.info("gen: skip duplicate rec | %s — %s", cand_artist, cand_title)
            continue

        # Try exact match first, then fallback to title-only search
        q = f"track:{cand_title} artist:{cand_artist}"
        items = sp.search(q=q, type="track", limit=1).get("tracks", {}).get("items", [])
        if not items:
            items = sp.search(q=cand_title, type="track", limit=1).get("tracks", {}).get("items", [])
        if not items:
            continue

        tid2 = items[0]["id"]
        uri  = items[0]["uri"]
        track_uris.append(uri)
        added_sigs.add(f"{cand_artist}:{cand_title}")

    log.info("gen: candidate uris | count=%d", len(track_uris))

    # Create the new playlist and add up to 100 recommended tracks
    user_id = spotify_id or sp.current_user().get("id")
    new_playlist = sp.user_playlist_create(user=user_id, name=playlist_name, public=False,
                                           description="Lyrics-aware mix seeded from your playlist")
    added = 0
    if track_uris:
        sp.playlist_add_items(new_playlist["id"], track_uris[:100])
        added = min(len(track_uris), 100)
    log.info("gen: created | id=%s added=%d", new_playlist["id"], added)

    # Optionally persist metadata to Supabase
    try:
        if supabase:
            user_row = supabase.table("users").select("id").eq("spotify_id", user_id).execute()
            uid = user_row.data[0]["id"] if user_row.data else None
            supabase.table("playlists").insert({
                "user_id": uid,
                "name": new_playlist["name"],
                "spotify_playlist_id": new_playlist["id"],
                "seed_playlist_id": playlist_id,
                "seeds": [{"artist_id": sid, "artist_name": sname} for sid, sname in zip(seed_ids, seed_artists)]
            }).execute()
    except Exception as e:
        log.warning("gen: supabase insert failed: %s", e)

    log.info("gen: embedded | total=%d", len(embeddings))

    return {"id": new_playlist["id"], "added": added}