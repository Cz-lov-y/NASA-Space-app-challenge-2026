"""Optional Canadian open-government catalogue discovery (not policy verification)."""
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from src.evidence import evidence_record

ENDPOINT = "https://open.canada.ca/data/en/api/3/action/package_search"


def search_canadian_catalogue(query: str, limit: int = 5) -> list[dict]:
    """Find catalogue records for review; these may be datasets, not policies."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("A non-empty search query is required")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    response = requests.get(ENDPOINT, params={"q": query, "rows": limit}, timeout=12)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError("Catalogue returned an unsuccessful response")
    result = data.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        raise ValueError("Catalogue returned malformed results")
    retrieved = datetime.now(timezone.utc).isoformat()
    candidates = []
    for item in result["results"]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if isinstance(title, dict):
            title = title.get("en") or title.get("fr")
        name = item.get("name")
        if not isinstance(title, str) or not title.strip() or not isinstance(name, str) or not name.strip():
            continue
        url = "https://open.canada.ca/data/en/dataset/" + quote(name, safe="")
        record = evidence_record(title, url, "policy")
        record.update(retrieved_at=retrieved, discovery_source="Open Government Portal catalogue",
                      jurisdiction=None, effective_date=None, policy_status=None,
                      original_official_url=None, evidence_type="catalogue metadata",
                      uncertainty="Catalogue candidate; original source, jurisdiction, policy relevance and status not reviewed.")
        candidates.append(record)
    return candidates


def search_for_analysis(analysis: dict) -> list[dict]:
    """Search Canadian catalogue only when Canada is explicitly supplied."""
    if not isinstance(analysis, dict) or analysis.get("country_code") != "CA":
        raise ValueError("Explicit country_code CA is required for Canadian catalogue search")
    region = analysis.get("region")
    if not isinstance(region, str) or not region.strip() or region == "demo-region":
        raise ValueError("A real named region is required")
    return search_canadian_catalogue(f"{region} water vegetation policy")
