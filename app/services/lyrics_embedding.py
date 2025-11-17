import numpy as np
from flask import current_app
from app.services.supabase_db import SUPABASE_ANON, SUPABASE_ADMIN
import traceback

def embed_text(lyrics_text, max_chunk_chars=20000):
    """Embed lyrics into a single vector via OpenAI."""
    # Basic safety: skip very short or empty lyrics
    if not lyrics_text or len(lyrics_text) < 50:
        return None
    
    client = current_app.config.get("OPENAI_CLIENT")
    if client is None:
        current_app.logger.error("OPENAI_CLIENT is not configured on the app.")
        return None

    chunks = [
        lyrics_text[i:i + max_chunk_chars]
        for i in range(0, len(lyrics_text), max_chunk_chars)
    ]

    vecs = []
    for ch in chunks:
        try:
            resp = client.embeddings.create(
                input=ch,
                model="text-embedding-3-small",
            )
            vecs.append(resp.data[0].embedding)
        except Exception as e:
            current_app.logger.error(f"Error generating embedding for chunk: {e}")
            traceback.print_exc()
            continue

    if not vecs:
        return None

    # Average all chunk vectors into a single embedding
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

    if emb is None:
        current_app.logger.warning(
            f"Skipping save_song_embedding for {track_id} – embedding is None"
        )
        return None

    save_song_embedding(track_id, track_name, artist_name, lyrics_text, emb)
    return emb