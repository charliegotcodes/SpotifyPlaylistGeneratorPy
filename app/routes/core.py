from flask import Blueprint, render_template, session, request, redirect, url_for

core_bp = Blueprint("core", __name__)

@core_bp.route("/")
def index():
    return render_template("index.html")

@core_bp.route("/submit", methods=["POST"])
def submit():
    session["username"] = request.form.get("username", "").strip()
    return redirect(url_for("auth.login"))

@core_bp.route("/playlists")
def playlists_page():
    return render_template("PlaylistPicker.html")