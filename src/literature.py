"""OpenAlex literature lookup helper (Member C).

Returned metadata are candidate references, NOT independently verified
scientific claims. Inspect each original publication before citing it.
"""
import requests

from src.evidence import evidence_record

OPENALEX_ENDPOINT = "https://api.openalex.org/works"


def search_openalex(query: str, limit: int = 3) -> list[dict]:
    """Find papers by keywords; uses no LLM or secret key."""
    if not query.strip():
        return []
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    response = requests.get(
        OPENALEX_ENDPOINT,
        params={"search": query, "per-page": limit},
        timeout=12,
    )
    response.raise_for_status()
    candidates = []
    for item in response.json().get("results", []):
        url = item.get("doi") or item.get("id")
        title = item.get("display_name") or ""
        if title and url:
            candidates.append(evidence_record(title, url, "scientific_literature"))
    return candidates
