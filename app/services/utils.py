import difflib

def is_duplicate_song(name, artist, seen_sigs, threshold=0.9):
    """Check whether a song is essentially a duplicate of something
    we've already processed for the same artist.
    Uses a simple string-similarity ratio on titles to catch
    near-identical variants like "Remastered" or "Radio Edit"."""
    for sig in seen_sigs:
        sig_artist, sig_name = sig.split(":", 1)
        if sig_artist == artist:
            if difflib.SequenceMatcher(None, name, sig_name).ratio() > threshold:
                return True
    return False