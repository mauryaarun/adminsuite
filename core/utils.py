"""
General utilities.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_SECRET_RE = re.compile(
    r"(?i)\b(password|passphrase|secret|token|api_key)\b\s*[:=]\s*([^\s;]+)"
)


def ensure_parent_dir(path: str | Path) -> None:
    """
    Ensure parent directory for a file path exists.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: str | Path, default: Any = None) -> Any:
    """
    Read JSON file. Return default if missing or invalid.
    """
    path = Path(path)

    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json_secure(path: str | Path, obj: Any) -> None:
    """
    Write JSON file with restrictive permissions where possible.
    """
    path = Path(path)

    ensure_parent_dir(path)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def safe_int(value: Any, default: int = 0) -> int:
    """
    Convert value to int safely.
    """
    try:
        return int(str(value).strip())
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Convert value to float safely.
    """
    try:
        return float(str(value).strip())
    except Exception:
        return default


def human_bytes(value: Any) -> str:
    """
    Convert numeric byte count to human-readable string.
    """
    n = safe_float(value)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"

        n /= 1024

    return f"{n:.1f} PB"


def human_duration(seconds: Any) -> str:
    """
    Convert seconds to human-readable duration.
    """
    seconds = safe_int(seconds)

    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    parts = []

    if days:
        parts.append(f"{days}d")

    if hours or days:
        parts.append(f"{hours}h")

    if minutes or hours or days:
        parts.append(f"{minutes}m")

    parts.append(f"{secs}s")

    return " ".join(parts)


def sanitize_for_log(text: Any) -> str:
    """
    Basic secret sanitizer for logs.

    This does not guarantee perfect coverage, but reduces accidental
    leakage of simple key=value style secrets.
    """
    text = str(text)
    return _SECRET_RE.sub(r"\1=******", text)
