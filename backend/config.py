"""Application paths and environment settings."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SECRETBOX_DATA_DIR", BASE_DIR / "objects"))
DB_FILE = Path(os.environ.get("SECRETBOX_DB_FILE", BASE_DIR / "users.db"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secretbox-local-key-change-before-deployment")
ALGORITHM = "HS256"
FRONTEND_DIST = BASE_DIR / "secretbox-ui" / "dist"
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://zhanaliber.github.io,https://the-fabulous.github.io",
).split(",")
CORS_ORIGINS = [origin.strip().rstrip("/") for origin in CORS_ORIGINS if origin.strip()]
