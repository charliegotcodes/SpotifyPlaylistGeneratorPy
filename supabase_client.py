import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_cached_recs(track, artist):
    response = supabase.table("twitter_recs").select("results").eq("track", track.lower()).eq("artist", artist.lower()).limit(1).execute()
    data = response.data
    return data[0]["results"] if data else None

def save_recs_to_cache(track, artist, results):
    supabase.table("twitter)_recs").insert({
        'track': track.lower(),
        'artist': artist.lower(),
        'results': results
    }).execute()