# 🎵 Spotify ML Playlist Generator  
_Automatically generate new playlists using lyric embeddings, similarity search, and Spotify’s API._

This project builds personalized Spotify playlists by analyzing the **lyrics and mood** of tracks you choose. Using OpenAI embeddings, pgvector similarity search (Supabase), and Spotify’s Web API, the app generates a curated playlist that feels consistent with the vibe of your seed playlist.

👉 **Live demo:** https://spotifyplaylistgeneratorpy.onrender.com  
👉 **Source code:** https://github.com/charliegotcodes/SpotifyPlaylistGeneratorPy

---

## 🚀 Features

### 🎧 Spotify Login & Playlist Selection
- Secure OAuth login using your Spotify account  
- Fetches your playlists via the Spotify Web API  
- Lets you choose any playlist as the “seed mood” for generation  

### 🧠 ML-Driven Song Embeddings
- Fetches lyrics for each track in the seed playlist  
- Generates vector embeddings using OpenAI  
- Saves embeddings to Supabase for reuse  
- Builds a **playlist mood vector** by averaging track embeddings  

### 🔍 Vector Similarity Search (pgvector)
- Uses a Supabase RPC function to find lyrically similar tracks  
- Ranks tracks by cosine similarity to your playlist mood  
- Filters out near-duplicates and obvious repeats  
- Skips tracks with missing or low-quality lyrics  

### 🎶 Automated Playlist Generation
- Creates a brand-new Spotify playlist in your account  
- Populates it with tracks that match the lyrical/mood profile  
- Returns a final list of recommended songs with titles & artists  

### 🔐 Token & Session Handling
- Spotify OAuth 2.0 with refresh token support  
- Account switching via `show_dialog=True`  
- No `.cache` files required (cloud-friendly)  

---

## 🏗️ Tech Stack

**Backend**
- Python 3
- Flask
- Spotipy (Spotify Web API wrapper)
- Requests

**Machine Learning / Vector Search**
- OpenAI embeddings
- Supabase (PostgreSQL)
- `pgvector` extension
- Supabase RPC for similarity search

**Auth / Deployment**
- Spotify OAuth 2.0
- Render (Flask web service)

---

## 🗂️ Project Structure

```text
app/
│
├── routes/
│   ├── auth.py            # Spotify OAuth login/logout/callback
│   ├── playlists.py       # Playlist selection + generate UI
│   └── core.py            # Landing page / index
│
├── services/
│   ├── spotify_api.py     # Spotify client + token refresh logic
│   ├── lyrics_getter.py   # Fetch lyrics from external sources
│   ├── lyrics_embedding.py# Generate & store embeddings in Supabase
│   ├── recommender.py     # Main playlist generation pipeline
│   └── supabase_db.py     # Supabase admin & anon clients
│
├── utils.py               # Duplicate detection / helper functions
├── templates/             # Jinja2 HTML templates
└── static/                # CSS / JS / assets
```
---
## ⚙️ How It Works (Pipeline)

User logs in with Spotify

/login redirects to Spotify OAuth

/callback stores access + refresh tokens in the session

User selects a playlist

/selectone lists the user’s playlists

User chooses a “seed” playlist for generation

Lyrics extraction

For each unique track in the seed playlist:

lyrics_getter.get_lyrics(track_name, artist_name)

Tracks with missing/low-quality lyrics are skipped

Embedding generation & storage

lyrics_embedding.embed_text(lyrics) uses OpenAI embeddings

lyrics_embedding.generate_and_store_embedding(...) saves to Supabase

Only tracks with valid embeddings are used for the seed set

Playlist mood vector

All seed track embeddings are averaged:

playlist_vec = np.mean(np.array(embeddings), axis=0)

Vector similarity search (Supabase)

Supabase RPC match_lyrics_similarity(query_embedding, match_count)

Returns top-N most similar songs from song_embeddings

Playlist creation on Spotify

A new playlist is created in the user’s account

Filtered, non-duplicate recommended tracks are added

User sees the final generated playlist

## 🧪 Running Locally
1. Clone the repository
git clone https://github.com/charliegotcodes/SpotifyPlaylistGeneratorPy.git
cd SpotifyPlaylistGeneratorPy

2. Create & activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate        # macOS / Linux
# or
venv\Scripts\activate           # Windows

3. Install dependencies
pip install -r requirements.txt

4. Set up environment variables

Create a .env file in the project root:

SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret

SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_anon_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key

OPENAI_API_KEY=your_openai_api_key
FLASK_SECRET_KEY=some_random_secret_key


Make sure the same redirect URI configured in your Spotify Developer Dashboard is:

http://localhost:5000/callback        # for local dev


If you’re using the Render URL in config.py, adjust accordingly when you run in production.

5. Run the app

Most setups will use run.py:

python run.py


Then open:

http://localhost:5000


Log in with Spotify and test playlist generation.
