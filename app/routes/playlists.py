# app/routes/playlists.py
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from ..services.spotify_api import ensure_spotify, collect_meta_by_id
from ..services.recommender import generate_playlist_from_seed

playlists_bp = Blueprint("playlists", __name__)

@playlists_bp.route("/selectone", methods=["GET", "POST"])
def select_playlist():
    if request.method == "POST":
        pid = request.form.get("playlist_id")
        if not pid:
            return redirect(url_for("playlists.select_playlist"))
        session["chosen_playlist"] = pid
        return redirect(url_for("playlists.generation"))

    sp, _ = ensure_spotify()
    if not sp:
        return redirect(url_for("auth.login"))

    # fetch ALL playlists (owned and followed)
    limit, offset = 50, 0
    all_items = []
    while True:
        page = sp.current_user_playlists(limit=limit, offset=offset)
        items = page.get("items", [])
        all_items.extend(items)
        if page.get("next"):
            offset += limit
        else:
            break

    # minimal dicts with id/name for your template
    playlists = [{"id": p.get("id"), "name": p.get("name")} for p in all_items if p.get("id")]

    return render_template("ChooseAplaylist.html", playlists=playlists)
@playlists_bp.route("/name_playlist", methods=["POST"])
def name_playlist():
    pid = request.form.get("playlist_id")
    if not pid:
        return redirect(url_for("playlists.select_playlist"))

    session["chosen_playlist"] = pid
    sp, _ = ensure_spotify()
    playlist_name = (sp.playlist(pid) or {}).get("name", "Your Playlist")
    return render_template("name_playlist.html", original_name=playlist_name)

@playlists_bp.route("/generation", methods=["GET", "POST"])
def generation():
    pid = session.get("chosen_playlist")
    if not pid:
        return redirect(url_for("playlists.select_playlist"))

    new_name = request.form.get("new_playlist_name", "Generated Mix")

    sp, access_token = ensure_spotify()
    if not sp:
        return redirect(url_for("auth.login"))

    meta_by_id = collect_meta_by_id(sp, pid)

    # make generator return {"id": "...", "added": N} 
    result = generate_playlist_from_seed(sp, access_token, pid, new_name)

    new_pl_id = result["id"] if isinstance(result, dict) else result  # handle old return shape
    added     = (result.get("added", 0) if isinstance(result, dict) else None)

    print("generation(): new_pl_id =", new_pl_id, "added =", added)

    return render_template(
        "generation.html",
        playlist_id=pid,
        meta_by_id=meta_by_id,
        new_pl_id=new_pl_id,
        added=added
    )

@playlists_bp.route("/discover", methods=["GET"])
def discover():
    playlist_id = session.get("chosen_playlist")
    if not playlist_id:
        return jsonify({"error": "no playlist selected"}), 400
    sp, _ = ensure_spotify()
    if not sp:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({"message": "Discovery handled by hybrid recommender now.",
                    "playlist_id": playlist_id})