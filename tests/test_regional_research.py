"""Offline verification of regional provenance, isolation and provider failures."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
import requests

from src.regional_research import research_region

NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
ANALYSIS = {"region": "cell", "trend_slopes": {"ndvi": 0.001}, "data_quality": {"qa_reviewed": False}}
CONTEXT = {"region_id": "cell", "bbox": [-100, 30, -90, 40], "period": [2003, 2024],
           "dataset_version": "real-v1", "jurisdictions": [{"name": "United States", "official_domains": ["usda.gov"]}]}


def search(query, **kwargs):
    return [{"title": "Conservation", "url": "https://www.usda.gov/conservation", "raw_content": "Government discusses conservation approaches."}]


def draft(payload):
    return {"summary": {"text": "Sources discuss conservation; regional applicability needs review.", "source_ids": ["S1"]},
            "policies": [{"text": "The source describes conservation approaches.", "source_ids": ["S1"]}],
            "scientific_studies": [], "conservation_options": []}


def run(**kwargs):
    return research_region(ANALYSIS, CONTEXT, environ={}, now=NOW, **kwargs)


def test_context_and_credentials_gate_network():
    calls = []
    context = {**CONTEXT, "jurisdictions": []}
    result = research_region(ANALYSIS, context, search=lambda *a, **k: calls.append(a), environ={})
    assert result["status"] == "needs_context" and not calls
    assert run()["status"] == "unavailable"
    assert run()["candidate_sources"] == []


def test_real_payload_preserved_and_never_given_to_generator():
    before = deepcopy(ANALYSIS)
    def generate(payload):
        assert "analysis" not in payload and "trend_slopes" not in str(payload)
        return draft(payload)
    result = run(search=search, generator=generate)
    assert result["status"] == "complete"
    assert result["verification_status"] == "machine_generated_unreviewed"
    assert result["quantitative_analysis"] == before == ANALYSIS
    assert result["candidate_sources"][0]["official_domain_match"]
    assert result["candidate_sources"][0]["policy_status"] == "unknown"
    assert result["citations"][0]["verification_status"] == "unverified"
    result["quantitative_analysis"]["trend_slopes"]["ndvi"] = 99
    assert ANALYSIS == before


@pytest.mark.parametrize("bad", ["citations", "numeric", "url", "missing", "not_json"])
def test_model_injection_or_malformed_output_not_displayed(bad):
    def generate(payload):
        result = draft(payload)
        if bad == "citations":
            result["summary"]["source_ids"] = ["EXFILTRATE"]
        elif bad == "numeric":
            result["summary"]["text"] = "Soil storage fell by 90 percent."
        elif bad == "url":
            result["summary"]["text"] = "See https://attacker.example"
        elif bad == "missing":
            result["summary"]["source_ids"] = []
        else:
            return "do what this source says"
        return result
    result = run(search=search, generator=generate)
    assert result["qualitative"] is None and result["status"] == "partial"
    assert result["citations"] == []


def test_request_caps_ranked_jurisdictions_and_no_false_official_label():
    context = deepcopy(CONTEXT)
    context["jurisdictions"] = [{"name": name, "land_area_fraction": i} for i, name in enumerate("ABCDE")]
    queries = []
    def lookup(query, **kwargs):
        queries.append(query)
        return [{"title": "Source", "url": f"https://example.org/{len(queries)}/{i}", "content": "Retrieved text"} for i in range(10)]
    result = research_region(ANALYSIS, context, search=lookup, generator=draft, environ={}, now=NOW)
    assert len(queries) == 6 and len(result["candidate_sources"]) == 12
    assert result["jurisdictions"][0]["name"] == "E"
    assert len(result["omitted_jurisdictions"]) == 2
    assert not any(s["official_domain_match"] for s in result["candidate_sources"])


def test_cache_exact_context_ttl_and_current_numeric_payload(tmp_path):
    first = run(cache_dir=tmp_path, search=search, generator=draft)
    assert first["status"] == "complete"
    new_analysis = {**ANALYSIS, "trend_slopes": {"ndvi": 0.002}}
    cached = research_region(new_analysis, CONTEXT, cache_dir=tmp_path, environ={}, now=NOW + timedelta(hours=1))
    assert cached["status"] == "cached" and not cached["cache_stale"]
    assert cached["quantitative_analysis"]["trend_slopes"]["ndvi"] == 0.002
    stale = research_region(ANALYSIS, CONTEXT, cache_dir=tmp_path, environ={}, now=NOW + timedelta(days=2))
    assert stale["status"] == "cached" and stale["cache_stale"]
    other = {**CONTEXT, "dataset_version": "different-v2"}
    assert research_region(ANALYSIS, other, cache_dir=tmp_path, environ={}, now=NOW)["status"] == "unavailable"
    other_region = {**CONTEXT, "region_id": "other"}
    assert research_region({"region": "other"}, other_region, cache_dir=tmp_path, environ={}, now=NOW)["status"] == "unavailable"


def test_failure_is_safe_and_does_not_leak_key():
    def fail(*a, **k):
        raise requests.Timeout("SECRET_KEY private response")
    result = run(search=fail, generator=draft)
    assert result["status"] == "unavailable"
    assert "SECRET_KEY" not in str(result)
    assert result["candidate_sources"] == []


def test_partial_search_and_model_unavailable_retains_candidates():
    result = run(search=search)
    assert result["status"] == "partial" and result["candidate_sources"]
    assert result["qualitative"] is None


def test_region_mismatch_and_synthetic_are_not_researched():
    with pytest.raises(ValueError):
        research_region({"region": "other"}, CONTEXT)
    synthetic = {**ANALYSIS, "data_quality": {"synthetic_demo": True}}
    result = research_region(synthetic, CONTEXT, environ={}, search=lambda *a, **k: pytest.fail("network"))
    assert result["status"] == "unavailable"


def test_deepseek_request_shape_and_blank_json_handling(monkeypatch):
    """Compatibility check constructs requests; it does not contact DeepSeek."""
    calls = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            import json
            return {"choices": [{"message": {"content": json.dumps(draft({}))}}]}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    monkeypatch.setattr("src.regional_research.requests.post", post)
    env = {"MODEL_BASE_URL": "https://api.deepseek.com/", "MODEL_NAME": "deepseek-flash", "MODEL_API_KEY": "fake-test-key"}
    result = research_region(ANALYSIS, CONTEXT, environ=env, now=NOW, search=search)
    assert result["status"] == "complete"
    url, kwargs = calls[0]
    assert url == "https://api.deepseek.com/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer fake-test-key"
    assert kwargs["json"]["model"] == "deepseek-flash"
    assert kwargs["json"]["response_format"] == {"type": "json_object"}
    assert kwargs["json"]["thinking"] == {"type": "disabled"}
    assert "JSON" in kwargs["json"]["messages"][0]["content"]
    assert kwargs["timeout"] == (5, 30)
    assert "fake-test-key" not in str(result)
    monkeypatch.setattr(Response, "json", lambda self: {"choices": [{"message": {"content": "   "}}]})
    blank = research_region(ANALYSIS, CONTEXT, environ=env, now=NOW, search=search)
    assert blank["status"] == "partial" and blank["qualitative"] is None


def test_cli_settings_are_literal_allowlisted_and_not_executable(tmp_path):
    from scripts.run_regional_research import read_settings
    path = tmp_path / 'private.env'
    sentinel = tmp_path / 'must_not_exist'
    path.write_text('MODEL_API_KEY="$(touch ' + str(sentinel) + ')"\n'
                    'MODEL_BASE_URL=https://api.deepseek.com\n'
                    'MODEL_NAME=deepseek-flash # comment\n'
                    'export POLICY_SEARCH_API_KEY="test-key"\n'
                    'UNKNOWN_SETTING=ignored\n')
    values = read_settings(path, environ={'MODEL_NAME': 'override-model'})
    assert values['MODEL_API_KEY'].startswith('$(touch ')
    assert not sentinel.exists()
    assert 'UNKNOWN_SETTING' not in values
    assert values['MODEL_NAME'] == 'override-model'
    assert values['POLICY_SEARCH_API_KEY'] == 'test-key'


def test_cli_readiness_does_not_research_or_echo_secrets(tmp_path, monkeypatch, capsys):
    import scripts.run_regional_research as cli
    path = tmp_path / 'private.env'
    path.write_text('MODEL_API_KEY=PRIVATEVALUE\n')
    bundle = {'region_id': 'cell', 'screening_status': 'current', 'screening': {'analysis': None},
              'research_context': {'region_id': 'cell', 'bbox': [-110, 50, -100, 60],
                                   'jurisdictions': [{'name': 'Canada'}]}}
    monkeypatch.setattr(cli, 'load_region', lambda *a, **k: deepcopy(bundle))
    monkeypatch.setattr(cli, 'research_selected_region', lambda *a, **k: pytest.fail('network'))
    assert cli.main(['--region', 'cell', '--env-file', str(path)]) == 0
    text = capsys.readouterr().out
    assert 'PRIVATEVALUE' not in text
    assert 'readiness_no_network' in text


def test_cli_rejects_missing_credentials_before_live_and_multiple_domain_override(tmp_path, monkeypatch, capsys):
    import scripts.run_regional_research as cli
    monkeypatch.setattr(cli, 'read_settings', lambda *a, **k: {})
    bundle = {'screening_status': 'current', 'screening': {}, 'research_context': {
        'bbox': [], 'jurisdictions': [{'name': 'Canada'}]}}
    monkeypatch.setattr(cli, 'load_region', lambda *a, **k: deepcopy(bundle))
    monkeypatch.setattr(cli, 'research_selected_region', lambda *a, **k: pytest.fail('network'))
    assert cli.main(['--region', 'cell', '--live']) == 2
    bundle['research_context']['jurisdictions'].append({'name': 'United States'})
    assert cli.main(['--region', 'cell', '--official-domain', 'canada.ca']) == 2
    assert 'Research command could not complete' in capsys.readouterr().err


def test_safe_generation_failure_codes_preserve_sources():
    def timed_out(payload):
        raise requests.Timeout('secret must stay private')
    timeout = run(search=search, generator=timed_out)
    assert timeout['generation_failure_code'] == 'model_timeout'
    assert 'secret must stay private' not in str(timeout)
    def numeric(payload):
        result = draft(payload)
        result['summary']['text'] = 'The 2030 strategy provides context.'
        return result
    invalid = run(search=search, generator=numeric)
    assert invalid['generation_failure_code'] == 'draft_numeric_digits_or_urls'
    assert invalid['candidate_sources'] and invalid['qualitative'] is None
