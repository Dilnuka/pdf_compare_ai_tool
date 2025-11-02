"""
Environment loading helpers.

This module centralizes logic to load GOOGLE_API_KEY from:
- Existing environment variables
- .env or .env.local files (if present)
- .env.example as a last-resort fallback (for local dev only)

Note: Do NOT commit real secrets to .env.example. Prefer .env which is ignored by git.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def ensure_google_api_key() -> Optional[str]:
    """Return GOOGLE_API_KEY, attempting to load from common sources if missing.

    Resolution order:
    1) Existing environment variable
    2) .env.local then .env files in project root
    3) .env.example (dev-only fallback)
    """
    key = os.getenv("GOOGLE_API_KEY")
    if key:
        return key

    try:
        from dotenv import load_dotenv
    except Exception:
        # dotenv not installed; just return whatever is in the env
        return os.getenv("GOOGLE_API_KEY")

    root = Path.cwd()
    # Try .env.local then .env
    for fname in (".env.local", ".env"):
        fpath = root / fname
        if fpath.exists():
            load_dotenv(dotenv_path=str(fpath), override=False)
            key = os.getenv("GOOGLE_API_KEY")
            if key:
                return key

    # Last resort: .env.example (do NOT put real secrets here for shared repos)
    ex = root / ".env.example"
    if ex.exists():
        load_dotenv(dotenv_path=str(ex), override=False)

    return os.getenv("GOOGLE_API_KEY")
