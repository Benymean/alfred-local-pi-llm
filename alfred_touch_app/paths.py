from __future__ import annotations

from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"
FAVICON_PATH = PACKAGE_DIR / "assets" / "favicon.png"
EARLY_ACK_PHRASES = (
    "One sec.",
    "Just a sec.",
    "Give me a moment.",
    "Hang on a sec.",
    "Let me think.",
    "One moment.",
    "Im thinking"
)
