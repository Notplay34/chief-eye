"""Identity normalization helpers."""

from typing import Optional


def normalize_login(login: Optional[str]) -> Optional[str]:
    if login is None:
        return None
    normalized = login.strip().lower()
    return normalized or None
