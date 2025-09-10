import os
import re
import tweepy
# Used for creating and managing routes on a flask app
from flask import Flask, redirect, request, jsonify, session, render_template, url_for

# Python library for Spotify API
from spotipy import Spotify 
from spotipy.oauth2 import SpotifyOAuth

# Loads Enviroment variables 

import urllib.parse

import time 

from supabase_client import create_client, Client, save_recs_to_cache, get_cached_recs


# Responsible for loading the enviroment variables
from dotenv import load_dotenv
load_dotenv()

# Creates a Flask app and its corresponding app.secret_key for managing the session
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET")

# Spotify credentials retrieved from the .env
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

# X client
client = tweepy.Client(bearer_token=os.getenv("X_BEARER_TOKEN"), wait_on_rate_limit=True)



def spotify_artist_lookup(sp: Spotify, name: str):
    res = sp.search(q=f"artist:{name}", type="artist", limit=1)
    items = res.get("artists", {}).get("items", [])
    if items:
        a = items[0]
        return a["id"], a["name"]
    return None, None

def spotify_top_track(sp: Spotify, artist_id: str, market="CA"):
    if not artist_id:
        return None
    tt = sp.artist_top_tracks(artist_id=artist_id, country=market)
    for t in tt.get("tracks", []):
        return t["name"], t["artists"][0]["name"], t["uri"]
    return None

SPLIT_RE = re.compile(r"\s*(?:,|/|&| and )\s*", re.I)
CLEAN_RE = re.compile(r"[^A-Za-z0-9 .'\-&/]")

def discover_from_twitter(sp: Spotify, meta_by_id: dict, market="CA", per_seed=2, max_results=20, min_likes=100, min_retweets=100):

    playlist_artists = {a.strip().lower()
                        for v in meta_by_id.values()
                        for a in v['artists'].split(',')}
    recs = {}
    rate_limited = False

    for tid, meta in meta_by_id.items():
        seed_track = meta['name']
        seed_artist = meta['artists'].split(',')[0].strip()
        cached = get_cached_recs(seed_track, seed_artist)
        if cached:
            recs[tid] = cached
            continue
        queries = [
            f"\"{seed_artist}\" (ffo OR \"for fans of\" OR \"similar to\" OR \"sounds like\") -is:retweet lang:en"]
        candidate = []
    for q in queries:
        if rate_limited:
            print("⚠️ Skipping query due to previous rate limit hit.")
            continue

        print(f"\n🔍 Querying Twitter for: '{seed_track}' by {seed_artist}")
        print(f"Query string: {q}")

        try:
            resp = client.search_recent_tweets(
                query=q,
                max_results=min(100, max_results),
                tweet_fields=["text", "public_metrics"]
            )

            if not resp.data:
                print("😕 No tweets found for this query.")
                continue

            printed = 0
            for tw in (resp.data or []):
                public_metrics = getattr(tw, "public_metrics", {})
                likes = public_metrics.get("like_count", 0)
                rts = public_metrics.get("retweet_count", 0)

                if likes < min_likes or rts < min_retweets:
                    continue

                if printed < 3:
                    print("✅ Valid Tweet Found:")
                    print(f"Text: {tw.text[:150]}...")
                    print(f"Likes: {likes}, Retweets: {rts}\n")
                    printed += 1

                candidate += extract_candidate_artists(tw.text)

        except tweepy.TooManyRequests as e:
            rate_limited = True
            print("🚫 Rate limit hit BEFORE we got any results.")
            print("Remaining:", e.response.headers.get("x-rate-limit-remaining"))
            print("Reset in:", e.response.headers.get("x-rate-limit-reset"))
            break  # Optional: or return/continue if you want to skip seeds

        
        seen, usable = set(), []
        for c in candidate:
            k = c.lower()
            if k not in seen and k not in playlist_artists and k!= seed_artist.lower():
                seen.add(k)
                usable.append(c)

        picked = 0
        for name in usable: 
            if picked >= per_seed:
                break
            aid, aname = spotify_artist_lookup(sp, name)
            top = spotify_top_track(sp, aid, market=market)
            if top:
                tname, aname2, uri = top
                recs.setdefault(tid, []).append({
                    'rec_artist': aname2,
                    'rec_track': tname,
                    'spotify_uri': uri,
                    'via': "twitter"
                })
                picked += 1
        if tid in recs:
            save_recs_to_cache(seed_track, seed_artist, recs[tid])
    return recs

def extract_candidate_artists(text: str) -> list[str]:
    """Find names in FFO / for fans of / similar to / sounds like / if you like phrasing along with mentions/hashtags"""
    
    if not text: return []
    patterns = [
        r"(?i)\bffo[:\-]?\s+(.+)",
        r"(?i)\bfor\s+fans\s+of[:\-]?\s+(.+)",
        r"(?i)\bsimilar\s+to[:\-]?\s+(.+)",
        r"(?i)\bsounds\s+like[:\-]?\s+(.+)",
        r"(?i)\bif\s+you\s+like[:\-]?\s+(.+)"
    ]

    found = []
    for p in patterns:
        m = re.search(p, text)
        if m: 
            chunk = re.sub(r"[.!?].*$", "", m.group(1))
            found.extend(SPLIT_RE.split(chunk))

    mentions = re.findall(r"@([A-Za-z0-9_]+)", text)
    tags = [t[1:] for t in re.findall(r"#([A-Za-z0-9_][A-Za-z0-9_ ]+)", text)]

    cand = found + mentions + tags
    print(cand)

    seen, out = set(), []
    for s in cand:
            s = CLEAN_RE.sub(" ", s).strip(" :-_")
            s = re.sub(r"\s{2,}", " ", s)
            k = s.lower()
            if 2 <= len(s) <= 60 and k not in seen:
                seen.add(k); out.append(s)
    return out
# Scope Privileges
SCOPE = 'user-read-private playlist-read-private playlist-read-collaborative user-library-read'

sp_oauth = SpotifyOAuth( client_id = CLIENT_ID, client_secret = CLIENT_SECRET, redirect_uri = REDIRECT_URI, scope = SCOPE, cache_path=None)

AUTH_URL     = "https://accounts.spotify.com/authorize"
TOKEN_URL    = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1/"

def collect_meta_by_id(sp: Spotify, playlist_id: str) -> dict:
        tracks = []
        tracks_data = sp.playlist_items(playlist_id, additional_types=['track'], fields='items(track(id,name,uri,artists(name))),next', limit=100)
        while True:
            for item in tracks_data['items']:
                t = item.get('track') or {}
                tid = t.get('id')
                if tid: 
                    tracks.append({
                        'id': tid,
                        'name': t['name'],
                        'artists': ', '.join(a['name'] for a in t.get('artists', [])),
                        'uri': t['uri']
                    })
            if tracks_data.get('next'):
                tracks_data = sp.next(tracks_data)
            else:
                break 
        meta_by_id = {t['id']: {'name': t['name'], 'artists': t['artists']} for t in tracks}
        return meta_by_id

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/submit", methods=["POST"])
def submit():
    session['username'] = request.form.get("username", "").strip()
    return redirect(url_for("login"))

@app.route('/login')
def login():
    params = {
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "scope":         SCOPE,
        "redirect_uri":  REDIRECT_URI,
        "show_dialog":   True
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("index"))

    token_info = sp_oauth.get_access_token(code, as_dict=True)
    session["access_token"]    = token_info["access_token"]
    session["refresh_token"]   = token_info["refresh_token"]
    session["expires_at"]      = token_info["expires_at"]

    return redirect(url_for("select_playlist"))


@app.route('/playlists')
def get_playlists():
    return render_template("PlaylistPicker.html")

@app.route('/selectone', methods=['GET', 'POST'])
def select_playlist():
    if request.method== 'POST':
        pid = request.form['playlist_id']
        session['chosen_playlist'] = pid
        return redirect(url_for('generation'))

    if "access_token" not in session:
        return redirect(url_for("login"))

    spot = Spotify(auth=session["access_token"])

    if sp_oauth.is_token_expired(session):
        token_info = sp_oauth.refresh_access_token(session["refresh_token"])
        session["access_token"] = token_info["access_token"]
        session["expires_at"] = token_info["expires_at"]
        spot = Spotify(auth=session["access_token"])

    results = spot.current_user_playlists(limit=30)
    playlists = results.get("items", [])
    playlist_ids = [pl["id"] for pl in playlists]
    return render_template('ChooseAplaylist.html', playlist_ids=playlist_ids)

@app.route('/selecttwo')
def autogenerate():
    return render_template('autogenerate.html')

@app.route('/generation', methods=['GET', 'POST'])
def generation():
    if request.method == 'POST':
        pid = request.form['playlist_id']
        session['chosen_playlist'] = pid

    playlist_id = session.get('chosen_playlist')
    if not playlist_id:
        return redirect(url_for('select_playlist'))

    # refresh Spotify token if needed
    if time.time() > session.get('expires_at', 0):
        token_info = sp_oauth.refresh_access_token(session['refresh_token'])
        session['access_token'] = token_info['access_token']
        session['expires_at']   = time.time() + token_info['expires_in']

    sp = Spotify(auth=session['access_token'])

    meta_by_id = collect_meta_by_id(sp, playlist_id)

    # 🟦 Run Twitter discovery here so results are rendered on the page
    recs = discover_from_twitter(
        sp, meta_by_id,
        market="CA",
        per_seed=2,          # tweak as you like
        max_results=20,
        min_likes=3,         # engagement thresholds
        min_retweets=1
    )

    return render_template('generation.html',
                           playlist_id=playlist_id,
                           meta_by_id=meta_by_id,
                           recs=recs)

@app.route('/discover', methods=['GET'])
def discover():
    playlist_id = session.get('chosen_playlist')
    if not playlist_id:
        return jsonify({"error":"no playlist selected"}), 400

    if time.time() > session.get('expires_at', 0):
        tok = sp_oauth.refresh_access_token(session['refresh_token'])
        session['access_token'] = tok['access_token']
        session['expires_at']   = time.time() + tok['expires_in']

    sp = Spotify(auth=session['access_token'])
    meta_by_id = collect_meta_by_id(sp, playlist_id)

    # engagement thresholds keep results relevant
    recs = discover_from_twitter(
        sp, meta_by_id, market="CA",
        per_seed=2, max_results=20,
        min_likes=3, min_retweets=1
    )

    return jsonify({"seeds": meta_by_id, "recs": recs})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)