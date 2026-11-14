"""OpenAlex literature lookup helper (Member C).

Returned metadata are candidate references, NOT independently verified
scientific claims. Inspect each original publication before citing it.
"""
import requests
from datetime import datetime, timezone

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
            record = evidence_record(title, url, "scientific_literature")
            record.update(publication_date=item.get("publication_date"),
                          retrieved_at=datetime.now(timezone.utc).isoformat(),
                          discovery_source="OpenAlex",
                          uncertainty="Candidate metadata; original publication not reviewed.")
            candidates.append(record)
    return candidates


def search_for_analysis(analysis: dict) -> list[dict]:
    """Discover candidates from the region and supplied variable names."""
    region = analysis.get("region")
    if not isinstance(region, str) or not region.strip():
        raise ValueError("A named region is required for literature search")
    variables = analysis.get("variables") or []
    if not isinstance(variables, list) or not all(isinstance(v, str) for v in variables):
        raise ValueError("variables must be a list of names")
    return search_openalex(" ".join([region, *variables, "vegetation water"]))
