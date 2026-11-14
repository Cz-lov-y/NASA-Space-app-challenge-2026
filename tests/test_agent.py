import pytest

from src.evidence import evidence_record
from src.policy_agent import investigate_policy


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
