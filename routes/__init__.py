"""
Routes package.

Exports every Blueprint so app.py can import them in one line.
"""

from routes.main import main_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.learning import learning_bp
from routes.missions import missions_bp
from routes.leaderboard import leaderboard_bp
from routes.profile import profile_bp
from routes.admin import admin_bp

__all__ = [
    "main_bp",
    "auth_bp",
    "dashboard_bp",
    "learning_bp",
    "missions_bp",
    "leaderboard_bp",
    "profile_bp",
    "admin_bp",
]
