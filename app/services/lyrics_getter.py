import re, unicodedata, requests, logging
from bs4 import BeautifulSoup
from flask import current_app

log = logging.getLogger("playlistgen")

# common junk patterns to ignore when searching Genius
BAD_TERMS = [
    "videography","discography","tracklist","contributors",
    "spotify new music friday","annotated","playlist","album"
]


def _norm(s: str) -> str:
    """Basic Unicode cleanup which normalizes quotes and spacing."""
    s = unicodedata.normalize("NFKC", s or "").strip()
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    return s

def _clean_title(s: str) -> str:
    """Lowercase and strip common decorations like (feat.), [Live], - Remastered, etc."""
    s = _norm(s).lower()
    s = re.sub(r"\(feat\.?[^)]*\)", "", s)
    s = re.sub(r"\(with [^)]*\)", "", s)
    s = re.sub(r"\[[^]]*\]", "", s)
    s = re.sub(r"-\s*(remaster(?:ed)?(?: \d{2,4})?|radio edit|live|bonus track|mono|stereo).*", "", s)
    s = re.sub(r"[^a-z0-9\s&']", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _slugify_artist_title(artist: str, title: str) -> str:
    """Construct the canonical Genius slug for example: drake-headlines-lyrics."""
    a = _clean_title(artist).replace("&", "and").replace(" ", "-")
    t = _clean_title(title).replace("&", "and").replace(" ", "-")
    return f"https://genius.com/{a}-{t}-lyrics"

def _session(auth=True) -> requests.Session:
    """
    Prepare a requests session with browser like headers.
    Adds Authorization if a Genius API token is configured."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.8",
        "Referer": "https://www.google.com/"
    })
    if auth:
        token = current_app.config.get("GENIUS_API_KEY")
        if token:
            s.headers["Authorization"] = f"Bearer {token}"
        else:
            log.warning("genius: no API token configured => relying on public fallback")
    return s

def _is_good_hit(result: dict) -> bool:
    """Filter out non-song pages and keep only real /lyrics URLs."""
    full_title = (result.get("full_title") or "").lower()
    path = (result.get("path") or "").lower()
    url = (result.get("url") or "").lower()
    if any(term in full_title or term in path for term in BAD_TERMS):
        return False
    return "/lyrics" in url


def genius_get_search_hits(track_name: str, artist_name: str, max_hits: int = 5):
    """
    Search Genius for likely lyric pages using the official API token.
    No public fallback – if Genius blocks us, we just return [].
    """
    s = _session(auth=True)
    q1 = f"{_norm(track_name)} {_norm(artist_name)}"
    q2 = _norm(track_name)

    hits_all = []

    for q in (q1, q2):
        try:
            r = s.get("https://api.genius.com/search", params={"q": q}, timeout=12)
            log.info("genius: /search q=%s status=%s", q, r.status_code)

            
            if r.status_code in (401, 403):
                log.warning("genius: /search forbidden/unauthorized for q=%s", q)
                return []  

            r.raise_for_status()
            hits = r.json().get("response", {}).get("hits", [])
        except Exception as e:
            log.warning("genius: tokened search error for %s — %s: %s", track_name, artist_name, e)
            hits = []

        for h in hits:
            res = h.get("result") or {}
            if _is_good_hit(res):
                hits_all.append({
                    "id": res.get("id"),
                    "url": res.get("url"),
                    "title": res.get("title"),
                    "artist": (res.get("primary_artist") or {}).get("name"),
                })
            if len(hits_all) >= max_hits:
                return hits_all

    return hits_all


def scrape_lyrics_from_genius(url: str) -> str | None:
    """ Fetch a Genius page and extract lyrics text.
    Falls back to a reader if the main HTML lacks lyric containers."""
    s = _session(auth=False)
    try:
        html = s.get(url, timeout=12).text
    except Exception as e:
        log.warning("genius: fetch error %s", e)
        html = ""

    text = _extract_lyrics_from_html(html)
    if text:
        return text

    # fallback via Jina proxy
    try:
        prox = "https://r.jina.ai/http/" + url.replace("https://", "").replace("http://", "")
        prox_text = s.get(prox, timeout=12).text
        block = _slice_lyrics_like_section(prox_text)
        if block and len(block.split()) >= 10:
            return block
    except Exception as e:
        log.warning("genius: proxy fetch error %s", e)

    return None

def _extract_lyrics_from_html(html: str) -> str | None:
    """Pull text from <div data-lyrics-container> blocks and clean structure markers."""
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all("div", {"data-lyrics-container": "true"}) \
             or soup.select("div[class^='Lyrics__Container']")
    parts = [b.get_text(separator="\n").strip() for b in blocks if b.get_text(strip=True)]
    text = "\n".join(parts).strip()
    m = re.search(r"\[Verse\s*\d*[^]]*\]", text, flags=re.I)
    if m:
        text = text[m.start():]
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s{2,}", "\n", text).strip()
    return text if len(text.split()) >= 10 else None

def _slice_lyrics_like_section(txt: str) -> str | None:
    """Extract a lyrics-like section from the text using loose heuristics."""
    if not txt:
        return None
    start = None
    m = re.search(r"\[(Intro|Verse|Chorus|Bridge)[^\]]*\]", txt, flags=re.I)
    if m:
        start = m.start()
    else:
        m2 = re.search(r"\bLyrics\b", txt, flags=re.I)
        start = m2.start() if m2 else 0
    chunk = txt[start:]
    chunk = re.split(r"\b(You might also like|Embed|More on Genius)\b", chunk, maxsplit=1, flags=re.I)[0]
    chunk = re.sub(r"\[.*?\]", "", chunk)
    chunk = re.sub(r"\s{2,}", "\n", chunk).strip()
    return chunk if len(chunk.split()) >= 10 else None


def get_lyrics(track_name: str, artist_name: str) -> str | None:
    """ Combined entry point: tokened API search => public fallback => canonical slug.
    Returns plain lyrics text or None. """
    t = _clean_title(track_name)
    a = _clean_title(artist_name)

    # FIRST: API search
    hits = genius_get_search_hits(t, a, max_hits=5)
    for h in hits:
        url = h.get("url") or ""
        if "/lyrics" not in url.lower():
            continue
        lyr = scrape_lyrics_from_genius(url)
        if lyr:
            log.info("genius: using %s — %s (%s)", h.get("artist"), h.get("title"), url)
            return lyr

    # SECOND: canonical slug patterm
    slug = _slugify_artist_title(a, t)
    lyr = scrape_lyrics_from_genius(slug)
    if lyr:
        log.info("genius: used canonical slug %s", slug)
        return lyr

    log.warning("genius: no lyrics for %s — %s after all passes", artist_name, track_name)
    return None
