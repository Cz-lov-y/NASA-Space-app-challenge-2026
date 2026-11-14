import pytest

from src.evidence import evidence_record
from src.policy_agent import generate_explanation, investigate_policy
from src.literature import search_openalex, search_for_analysis
import requests


def test_agent_stub_does_not_fabricate_sources():
    result = investigate_policy({"region": "demo-region"})
    assert result["verification_status"] == "not_started"
    assert result["citations"] == []
    assert result["policies"] == []


def test_analysis_required():
    with pytest.raises(ValueError):
        investigate_policy({})


def test_evidence_record_starts_unverified():
    record = evidence_record("Example", "https://example.org/study", "scientific_literature")
    assert record["verification_status"] == "unverified"


def test_evidence_rejects_invalid_url():
    with pytest.raises(ValueError):
        evidence_record("Bad", "not-a-url", "policy")


def test_search_results_are_candidates_even_if_provider_claims_verification():
    result = investigate_policy({"region": "Toronto"}, policy_search=lambda _: [
        {"title": "Example", "url": "https://example.gov/policy", "verification_status": "verified"}])
    assert result["candidate_sources"][0]["verification_status"] == "unverified"
    assert result["policies"] == result["citations"] == []
    assert result["verification_status"] == "unverified"


def test_search_failure_and_synthetic_data_are_explicit():
    def fail(_):
        raise requests.Timeout()
    result = investigate_policy({"region": "demo-region", "data_quality": {"synthetic_demo": True}},
                                literature_search=fail)
    assert any("synthetic" in x.lower() for x in result["limitations"])
    assert any("failed" in x for x in result["limitations"])
    assert not result["scientific_studies"]


def test_openalex_results_are_unverified(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"results": [{"display_name": "Study", "doi": "https://doi.org/10.1/example", "publication_date": "2020-01-01"}]}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())
    result = search_openalex("water")
    assert result[0]["verification_status"] == "unverified"
    assert result[0]["retrieved_at"]
    assert search_for_analysis({"region": "Toronto", "variables": ["ndvi"]})


def test_generation_is_optional_and_marked_for_review():
    analysis = {"region": "Toronto"}
    report = investigate_policy(analysis)
    assert generate_explanation(analysis, report)["status"] == "unavailable"
    result = generate_explanation(analysis, report, generator=lambda payload: "Example passage.", question="Why?")
    assert result["status"] == "needs_review"
    assert result["text"] == "Example passage."
    with pytest.raises(ValueError):
        generate_explanation({"region": "Elsewhere"}, report)
