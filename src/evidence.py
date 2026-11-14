"""Citation validation helpers, not proof of content accuracy."""
from urllib.parse import urlparse
from datetime import datetime


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


def validate_reviewed_evidence(record: dict, region: str) -> dict:
    """Validate a human's documented review; this does not verify its truth."""
    if not isinstance(record, dict):
        raise ValueError("Reviewed evidence must be a dictionary")
    kind = record.get("source_type")
    if kind not in ("policy", "scientific_literature"):
        raise ValueError("Unsupported reviewed evidence type")
    required = ("title", "url", "region", "claim", "reviewer", "reviewed_at",
                "retrieved_at", "uncertainty")
    if any(not isinstance(record.get(k), str) or not record[k].strip() for k in required):
        raise ValueError("Reviewed evidence is missing required review information")
    if not valid_http_url(record["url"]) or record["region"] != region:
        raise ValueError("Reviewed source URL or region is invalid")
    for key in ("reviewed_at", "retrieved_at"):
        try:
            timestamp = datetime.fromisoformat(record[key].replace("Z", "+00:00"))
            if timestamp.utcoffset() is None:
                raise ValueError
        except (ValueError, OverflowError):
            raise ValueError(f"{key} must be an ISO timestamp with a timezone") from None
    if kind == "policy":
        if not isinstance(record.get("jurisdiction"), str) or not record["jurisdiction"].strip():
            raise ValueError("Policy evidence requires a jurisdiction")
        if not isinstance(record.get("authority"), str) or not record["authority"].strip():
            raise ValueError("Policy evidence requires an authority")
    result = dict(record)
    result["verification_status"] = "human_reviewed"
    if kind == "policy":
        result.setdefault("effective_date", None)
        result.setdefault("policy_status", "unknown")
        result["original_official_url"] = result["url"]
        result.setdefault("evidence_type", "policy source")
    return result
