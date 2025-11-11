# app/__init__.py
import os
from flask import Flask
from dotenv import load_dotenv

def create_app():
    # Load env only when the app is created
    load_dotenv()

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )
    app.secret_key = os.getenv("APP_SECRET", "dev-secret")

    # Lazy imports to avoid import-time errors
    from .config import SCOPE, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
    from spotipy.oauth2 import SpotifyOAuth
    from openai import OpenAI

    # Configurement
    app.config["SP_OAUTH"] = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=None,
    )
    app.config["OPENAI_CLIENT"] = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    app.config["GENIUS_API_KEY"] = os.getenv("GENIUS_API_KEY")

    # Register blueprints (import AFTER app exists)
    from .routes.core import core_bp
    from .routes.auth import auth_bp
    from .routes.playlists import playlists_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(playlists_bp)

    return app