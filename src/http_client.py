from __future__ import annotations
from typing import Dict, Any, Tuple
import urllib.request
import urllib.error

DEFAULT_TIMEOUT = 5.0           # seconds
DEFAULT_MAX_BYTES = 256 * 1024  # 256 KiB
DEFAULT_UA = "Loom/0.2 (+https://github.com/Redmountain73/loomweaver)"

class FetchError(Exception):
    pass

def _read_limited(fp, max_bytes: int) -> Tuple[bytes, bool]:
    """Read up to max_bytes from a file-like object; return (data, truncated?)."""
    chunks = []
    got = 0
    while True:
        need = max_bytes - got
        if need <= 0:
            extra = fp.read(1)
            return b"".join(chunks), True if extra else False
        part = fp.read(min(65536, need))
        if not part:
            return b"".join(chunks), False
        chunks.append(part)
        got += len(part)

def http_fetch(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """GET a URL with limits. Returns dict {url, status, headers, body, truncated, content_type}."""
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": DEFAULT_UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            hdrs = {k.lower(): v for k, v in resp.getheaders()}
            body, truncated = _read_limited(resp, max_bytes)
            ctype = hdrs.get("content-type", "")
            return {
                "url": url,
                "status": int(status),
                "headers": hdrs,
                "body": body,
                "truncated": bool(truncated),
                "content_type": ctype,
            }
    except urllib.error.HTTPError as e:
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
        return {"url": url, "status": int(e.code), "headers": {k.lower(): v for k, v in dict(e.headers or {}).items()},
                "body": e.read() if hasattr(e, "read") else b"", "truncated": False, "content_type": ctype}
    except Exception as e:
        raise FetchError(str(e)) from e
