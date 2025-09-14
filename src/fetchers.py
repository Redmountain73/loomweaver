# src/fetchers.py
from __future__ import annotations
from typing import Dict, Any
from pathlib import Path
import base64

from .http_client import http_fetch, DEFAULT_TIMEOUT, DEFAULT_MAX_BYTES

def real_fetcher(url: str, *, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES) -> Dict[str, Any]:
    return http_fetch(url, timeout=timeout, max_bytes=max_bytes)

def fixture_fetcher(url: str, *, timeout: float = DEFAULT_TIMEOUT, max_bytes: int = DEFAULT_MAX_BYTES) -> Dict[str, Any]:
    """Load bytes from repo path when url starts with fixture://"""
    if not url.startswith("fixture://"):
        raise ValueError("fixture_fetcher can only handle fixture:// URLs")
    rel = url[len("fixture://"):]
    root = Path(__file__).resolve().parents[1]
    path = (root / rel).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"fixture not found: {rel}")
    data = path.read_bytes()[:max_bytes]
    truncated = path.stat().st_size > len(data)
    return {
        "url": url,
        "status": 200,
        "headers": {"content-type": "application/atom+xml"},
        "body": data,
        "truncated": truncated,
        "content_type": "application/atom+xml",
    }
