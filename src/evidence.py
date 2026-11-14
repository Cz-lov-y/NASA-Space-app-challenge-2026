"""Citation validation helpers, not proof of content accuracy."""
from urllib.parse import urlparse


def valid_http_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme in ("https", "http") and bool(parsed.netloc)


def evidence_record(title: str, url: str, source_type: str) -> dict:
    """Record a source as unverified until its content is actually reviewed."""
    if not title.strip() or not valid_http_url(url):
        raise ValueError("Evidence must have a title and an HTTP(S) URL")
    return {
        "title": title.strip(),
        "url": url,
        "source_type": source_type,
        "verification_status": "unverified",
    }
