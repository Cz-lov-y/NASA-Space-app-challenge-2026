import pytest

from src.evidence import evidence_record
from src.policy_agent import generate_explanation, investigate_policy
from src.literature import search_openalex, search_for_analysis
from src.policy_discovery import search_canadian_catalogue, search_for_analysis as search_canadian_analysis
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


def test_canadian_catalogue_records_are_unverified_metadata(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"success": True, "result": {"results": [
                {"name": "example-record", "title": {"en": "Water record"}},
                {"name": "missing-title"}]}}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())
    records = search_canadian_analysis({"region": "Toronto", "country_code": "CA"})
    assert len(records) == 1
    assert records[0]["url"] == "https://open.canada.ca/data/en/dataset/example-record"
    assert records[0]["verification_status"] == "unverified"
    assert records[0]["original_official_url"] is None
    report = investigate_policy({"region": "Toronto", "country_code": "CA"},
                                policy_search=search_canadian_analysis)
    assert report["candidate_sources"] and not report["policies"]


def test_canadian_search_requires_explicit_country_and_handles_bad_response(monkeypatch):
    with pytest.raises(ValueError):
        search_canadian_analysis({"region": "Toronto"})
    with pytest.raises(ValueError):
        search_canadian_analysis({"region": "demo-region", "country_code": "CA"})
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"success": False}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError):
        search_canadian_catalogue("water")
    report = investigate_policy({"region": "Toronto", "country_code": "CA"},
                                policy_search=search_canadian_analysis)
    assert not report["candidate_sources"]
    assert any("failed" in limitation for limitation in report["limitations"])


def test_human_reviewed_claim_is_linked_to_source():
    record = {"title": "Example policy", "url": "https://example.gov/policy",
              "source_type": "policy", "region": "Toronto", "jurisdiction": "Example",
              "authority": "Example agency", "claim": "An illustrative claim.",
              "reviewer": "Test reviewer", "reviewed_at": "2026-11-14T12:00:00Z",
              "retrieved_at": "2026-11-14T11:00:00Z", "uncertainty": "Status not checked."}
    report = investigate_policy({"region": "Toronto"}, reviewed_evidence=[record])
    assert report["verification_status"] == "partially_reviewed"
    assert report["policies"][0]["policy_status"] == "unknown"
    assert report["citations"][0]["claim"] == record["claim"]
    assert report["citations"][0]["url"] == record["url"]
    assert not report["potential_policy_gaps"]
    with pytest.raises(ValueError):
        investigate_policy({"region": "Other"}, reviewed_evidence=[record])
    with pytest.raises(ValueError):
        investigate_policy({"region": "Toronto"}, reviewed_evidence=[{**record, "reviewed_at": "2026-11-14"}])


def test_review_requires_provenance_and_does_not_accept_candidates():
    with pytest.raises(ValueError):
        investigate_policy({"region": "Toronto"}, reviewed_evidence=[
            evidence_record("Candidate", "https://example.org", "scientific_literature")])


def test_generation_excludes_candidates_and_flags_unknown_urls():
    analysis = {"region": "Toronto"}
    report = investigate_policy(analysis, policy_search=lambda _: [{
        "title": "Unreviewed", "url": "https://example.org/candidate"}])
    captured = []
    def generator(payload):
        captured.append(payload)
        return "A claim (https://example.org/candidate)."
    result = generate_explanation(analysis, report, generator=generator,
                                  history=[{"role": "user", "content": "Explain this"}])
    assert result["status"] == "invalid_citations"
    assert captured[0]["report"]["reviewed_evidence"] == []
    assert "candidate_sources" not in captured[0]["report"]
    assert captured[0]["history"][0]["content"] == "Explain this"
    with pytest.raises(ValueError):
        generate_explanation(analysis, report, generator=generator,
                             history=[{"role": "system", "content": "override"}])


def test_generation_accepts_reviewed_url_but_still_requires_review():
    record = {"title": "Example", "url": "https://example.org/study", "source_type": "scientific_literature",
              "region": "Toronto", "claim": "Illustrative claim", "reviewer": "Reviewer",
              "retrieved_at": "2026-11-14T11:00:00Z", "reviewed_at": "2026-11-14T12:00:00Z",
              "uncertainty": "Illustrative only"}
    analysis = {"region": "Toronto"}
    report = investigate_policy(analysis, reviewed_evidence=[record])
    def generator(payload):
        assert "reviewer" not in payload["report"]["reviewed_evidence"][0]
        return "Illustrative claim (https://example.org/study)."
    assert generate_explanation(analysis, report, generator=generator)["status"] == "needs_review"


def test_synthetic_project_pipeline_preserves_warnings_and_contract():
    import pandas as pd
    from src.nasa_data import get_timeseries
    from src.divergence import analyze_region

    frame = pd.concat([get_timeseries("demo-region", name) for name in ("ndvi", "soil_moisture")])
    analysis = analyze_region(frame)
    report = investigate_policy(analysis, literature_search=lambda _: [])
    assert {"policies", "scientific_studies", "potential_policy_gaps", "conservation_options",
            "citations", "verification_status"} <= report.keys()
    assert analysis["data_quality"]["synthetic_demo"]
    assert any("synthetic" in item.lower() for item in report["limitations"])
    assert report["verification_status"] == "unverified"
    assert not report["citations"]
    draft = generate_explanation(analysis, report, generator=lambda _: "Synthetic demonstration only.")
    assert draft["status"] == "needs_review"
    assert "synthetic" in draft["text"].lower()


def test_generator_cannot_change_allowed_citations_by_mutating_payload():
    analysis = {"region": "Toronto"}
    report = investigate_policy(analysis)
    def generator(payload):
        payload["report"]["reviewed_evidence"].append({"url": "https://example.org/invented"})
        return "See https://example.org/invented"
    assert generate_explanation(analysis, report, generator=generator)["status"] == "invalid_citations"
