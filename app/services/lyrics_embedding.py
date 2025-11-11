import numpy as np
from flask import current_app
from app.services.supabase_db import SUPABASE_ANON, SUPABASE_ADMIN  

def embed_text(lyrics_text, max_chunk_chars=20000):
    """Embed lyrics into a single vector via OpenAI."""
    if not lyrics_text or len(lyrics_text) < 50:
        return None
    client = current_app.config["OPENAI_CLIENT"]

    chunks = [lyrics_text[i:i+max_chunk_chars] for i in range(0, len(lyrics_text), max_chunk_chars)]
    vecs = []
    for ch in chunks:
        r = client.embeddings.create(input=ch, model="text-embedding-3-small")
        vecs.append(r.data[0].embedding)
    if not vecs:
        return None
    return np.mean(np.array(vecs), axis=0).tolist()

def find_similar_songs(query_embedding, top_n=10):
    """Vector search via RPC (read-only client)."""
    return (
        SUPABASE_ANON
        .rpc("match_lyrics_similarity", {"query_embedding": query_embedding, "match_count": top_n})
        .execute()
        .data
    )

def save_song_embedding(track_id, track_name, artist_name, lyrics, embedding):
    """Upsert embedding with the admin client."""
    if not embedding:
        return
    if SUPABASE_ADMIN is None:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY not configured on server")

    snippet = (lyrics or "")[:240] if lyrics else None

    SUPABASE_ADMIN.table("song_embeddings").upsert(
        {
            "track_id": track_id,
            "track_name": track_name,
            "artist_name": artist_name,
             "lyrics": snippet,           
            "embedding": embedding,
        },
        on_conflict=["track_id"],
    ).execute()

def generate_and_store_embedding(track_id, track_name, artist_name, lyrics_text):
    """Compute embedding and persist & return the vector for immediate use."""
    emb = embed_text(lyrics_text)
    save_song_embedding(track_id, track_name, artist_name, lyrics_text, emb)
    return emb