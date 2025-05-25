import os
# Used for creating and managing routes on a flask app
from flask import Flask, redirect, request, jsonify, session, render_template, url_for

# Python library for Spotify API
from spotipy import Spotify 
from spotipy.oauth2 import SpotifyOAuth

# Loads Enviroment variables 
from dotenv import load_dotenv
import urllib.parse

# Responsible for loading the enviroment variables
load_dotenv()

# Creates a Flask app and its corresponding app.secret_key for managing the session
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET")

# Spotify credentials retrieved from the .env
CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

# Scope Privileges
SCOPE = 'user-read-private playlist-read-private playlist-read-collaborative user-library-read'

sp_oauth = SpotifyOAuth( client_id = CLIENT_ID, client_secret = CLIENT_SECRET, redirect_uri = REDIRECT_URI, scope = SCOPE)

AUTH_URL     = "https://accounts.spotify.com/authorize"
TOKEN_URL    = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1/"

def get_user_preferences():
    print(" Time to create a personalized playlist! ")
    genre = input("Enter a genre: ").strip()
    energy= float(input("Enter desired energy level (0.0 to 1.0): ")).strip()
    danceability = float(input("Enter a desired danceability level (0.0 to 1.0): ")).strip()

    return genre, energy, danceability

def get_recommendations(spot: Spotify, genre: str, energy: float, danceability: float):
    """"""
    return 



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

@app.route('/generation', methods=['POST'])
def generation():
    pid = request.form['playlist_id']
    session['chosen_playlist'] = pid
    print(pid)
    playlist_id = session.get('chosen_playlist')
    if not playlist_id:
        return redirect(url_for('select_playlist'))
    
    if sp_oauth.is_token_expired(session):
        tok = sp_oauth.refresh_access_token(session['refresh_token'])
        session['access_token'] = tok['access_token']
        session['expires_at']   = tok['expires_at']
    sp = Spotify(auth=session['access_token'])

    tracks_data = sp.playlist_tracks(playlist_id)
    tracks_ids = [item['track']['id']
        for item in tracks_data['items']
        if item['track'] and item['track']['id']]

    features = sp.audio_features(tracks_ids)
    features = [feats for feats in features if feats]

    avg = {'danceability': sum(feats['danceability'] for feats in features) / len(features),
        'energy': sum(feats['energy'] for feats in features) / len(features),
        'instrumentalness': sum(feats['instrumentalness'] for feats in features) / len(features),
        'liveness': sum(feats['liveness'] for feats in features) / len(features),
        'loudness': sum(feats['loudness'] for feats in features) / len(features),
        'tempo': sum(feats['tempo'] for feats in features) / len(features),
        'valence': sum(feats['valence'] for feats in features) / len(features),
        'acousticness': sum(feats['acousticness'] for feats in features) / len(features)
    }
    print(avg)
    return render_template('generation.html', playlist_id=pid)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)