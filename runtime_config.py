from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_APP_DATA_DIR = BASE_DIR / "data"
DEFAULT_FRONTEND_BASE_URL = "http://localhost:5173"
DEFAULT_LOCAL_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def get_app_data_dir() -> Path:
    raw_value = os.getenv("APP_DATA_DIR", "").strip()
    if not raw_value:
        return DEFAULT_APP_DATA_DIR
    return Path(raw_value).expanduser().resolve()


def get_frontend_base_url() -> str:
    raw_value = os.getenv("FRONTEND_BASE_URL", DEFAULT_FRONTEND_BASE_URL).strip()
    normalized = raw_value.rstrip("/")
    return normalized or DEFAULT_FRONTEND_BASE_URL


def _origin_from_url(raw_url: str) -> str | None:
    parsed = urlparse(raw_url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def get_cors_allow_origins() -> list[str]:
    explicit_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if explicit_origins:
        origins: list[str] = []
        seen: set[str] = set()
        for part in explicit_origins.split(","):
            origin = part.strip().rstrip("/")
            if not origin:
                continue
            if origin == "*":
                raise RuntimeError("CORS_ALLOW_ORIGINS 必须是显式 origin 列表，不能使用 '*'.")
            if origin not in seen:
                seen.add(origin)
                origins.append(origin)
        if origins:
            return origins

    frontend_origin = _origin_from_url(get_frontend_base_url())
    if frontend_origin:
        return [frontend_origin]

    return list(DEFAULT_LOCAL_CORS_ORIGINS)
