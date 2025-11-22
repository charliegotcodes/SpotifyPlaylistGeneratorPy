from flask import Blueprint, current_app, redirect, request, session, url_for
import requests

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login")
def login():
    session.clear()

    sp_oauth = current_app.config["SP_OAUTH"]
    return redirect(sp_oauth.get_authorize_url())

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect("https://accounts.spotify.com/logout")

@auth_bp.route("/callback")
def callback():
    sp_oauth = current_app.config["SP_OAUTH"]
    code = request.args.get("code")
    if not code:
        return redirect(url_for("core.index"))

    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info

    access_token = token_info["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    profile = requests.get("https://api.spotify.com/v1/me", headers=headers).json()

    session["spotify_id"] = profile["id"]
    display_name = profile.get("display_name", "")

    # Supabase upsert for the user's info
    try:
        from ..services.supabase_db import SUPABASE_ADMIN
        if SUPABASE_ADMIN:
            SUPABASE_ADMIN.table("users").upsert(
                {"spotify_id": session["spotify_id"], "display_name": display_name},
                on_conflict=["spotify_id"]
            ).execute()
    except Exception as e:
        print("Supabase upsert failed:", e)

    return redirect(url_for("playlists.select_playlist"))