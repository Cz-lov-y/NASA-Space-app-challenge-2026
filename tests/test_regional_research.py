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
    revised = research_region(ANALYSIS, other, cache_dir=tmp_path, environ={}, now=NOW)
    assert revised["status"] == "cached"
    assert revised["qualitative_reused_across_data_revision"]
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


def test_explicit_offline_cache_validates_and_refreshes_numeric_payload(tmp_path, monkeypatch):
    from src.regional_research import load_cached_report
    report = run(search=search,generator=draft)
    path = tmp_path/'real.json'
    import json
    path.write_text(json.dumps(report))
    monkeypatch.setattr('src.regional_research.requests.post',lambda *a,**k:pytest.fail('network'))
    analysis = {**ANALYSIS,'trend_slopes':{'ndvi':.123}}
    result = load_cached_report(path,analysis,CONTEXT,now=NOW+timedelta(days=2))
    assert result['status']=='cached' and result['cache_stale']
    assert result['quantitative_analysis']==analysis
    assert result['verification_status']=='machine_generated_unreviewed'
    with pytest.raises(ValueError):
        load_cached_report(path,analysis,CONTEXT,now=NOW+timedelta(days=2),allow_stale=False)


@pytest.mark.parametrize('change',['region','period','boundary','dataset','jurisdiction','query_version','citation_url','review_label','source_duplicate','official_label'])
def test_cache_rejects_mismatched_context_or_tampered_records(tmp_path,change):
    import json
    from src.regional_research import load_cached_report
    report=run(search=search,generator=draft)
    context=deepcopy(CONTEXT)
    if change=='region':
        report['region_id']='other'
    elif change=='period':
        context['period']=[2004,2024]
    elif change=='boundary':
        context['bbox']=[0,0,10,10]
    elif change=='dataset':
        context['dataset_version']='other'
    elif change=='jurisdiction':
        context['jurisdictions'][0]['name']='other'
    elif change=='query_version':
        report['cache_key']='old-query-version'
    elif change=='citation_url':
        report['citations'][0]['url']='https://attacker.example'
    elif change=='review_label':
        report['verification_status']='human_reviewed'
    elif change=='source_duplicate':
        report['candidate_sources'].append(deepcopy(report['candidate_sources'][0]))
    else:
        report['candidate_sources'][0]['official_domain_match']=False
    path=tmp_path/'cached.json'
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='unavailable or incompatible'):
        load_cached_report(path,ANALYSIS,context,now=NOW)


def test_cli_cached_only_never_loads_keys_or_calls_research(tmp_path,monkeypatch,capsys):
    import json
    import scripts.run_regional_research as cli
    path=tmp_path/'report.json'
    path.write_text(json.dumps(run(search=search,generator=draft)))
    bundle={'region_id':'cell','screening_status':'current','screening':{'analysis':ANALYSIS},
            'research_context':deepcopy(CONTEXT)}
    monkeypatch.setattr(cli,'load_region',lambda *a,**k:deepcopy(bundle))
    monkeypatch.setattr(cli,'read_settings',lambda *a,**k:pytest.fail('secret file read'))
    monkeypatch.setattr(cli,'research_selected_region',lambda *a,**k:pytest.fail('network'))
    assert cli.main(['--region','cell','--cached-only','--report-file',str(path)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['mode']=='cached_only_no_network' and result['status']=='cached'


def test_stale_report_never_triggers_paid_refresh_and_data_revision_refreshes_numbers(tmp_path):
    counts={'search':0,'model':0}
    def lookup(*a,**k):
        counts['search']+=1
        return search(*a,**k)
    def generate(payload):
        counts['model']+=1
        return draft(payload)
    run(cache_dir=tmp_path,search=lookup,generator=generate)
    revised={**CONTEXT,'dataset_version':'new-real-observations'}
    numbers={**ANALYSIS,'trend_slopes':{'ndvi':.25}}
    cached=research_region(numbers,revised,cache_dir=tmp_path,search=lookup,generator=generate,
                           environ={},now=NOW+timedelta(days=10))
    assert counts=={'search':2,'model':1}
    assert cached['cache_stale'] and cached['qualitative_reused_across_data_revision']
    assert cached['quantitative_analysis']==numbers
    assert cached['run_context']['dataset_version']=='new-real-observations'
    changed={**revised,'bbox':[0,0,10,10]}
    another=research_region(numbers,changed,cache_dir=tmp_path,search=lookup,generator=generate,
                            environ={},now=NOW+timedelta(days=10))
    # The new geometry gets its own draft, but reuses country source searches.
    assert counts=={'search':2,'model':2}
    assert another['status']=='complete'
    assert all(item['status']=='cached' and item['stale'] for item in another['source_searches'])
    assert {s['retrieved_at'] for s in another['candidate_sources']}=={NOW.isoformat()}


def test_shared_source_queries_are_deduplicated_for_concurrent_neighbor_cells(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Lock
    import time
    counts={'search':0,'model':0}
    guard=Lock()
    def lookup(*a,**k):
        with guard:
            counts['search']+=1
        time.sleep(.02)
        return search(*a,**k)
    def generate(payload):
        with guard:
            counts['model']+=1
        return draft(payload)
    def one(region):
        ctx={**CONTEXT,'region_id':region}
        analysis={**ANALYSIS,'region':region}
        return research_region(analysis,ctx,cache_dir=tmp_path,search=lookup,generator=generate,environ={},now=NOW)
    with ThreadPoolExecutor(max_workers=2) as executor:
        reports=list(executor.map(one,['neighbor-one','neighbor-two']))
    assert counts=={'search':2,'model':2}
    assert {r['region_id'] for r in reports}=={'neighbor-one','neighbor-two'}
    assert all(r['status']=='complete' for r in reports)


def test_source_query_domain_and_version_cache_invalidation(tmp_path,monkeypatch):
    import src.regional_research as module
    calls=[]
    def lookup(query,**kwargs):
        calls.append((query,kwargs['domains']))
        return search(query,**kwargs)
    def lookup_cached(query,domains):
        return module._cached_search(query,domains=domains,api_key='fake',search=lookup,
                                     cache_dir=tmp_path,now=NOW)
    lookup_cached('Canadian water policy',['canada.ca'])
    lookup_cached('Canadian water policy',['canada.ca'])
    assert len(calls)==1
    lookup_cached('Canadian water policy',['gc.ca'])
    lookup_cached('Canadian wetlands policy',['gc.ca'])
    assert len(calls)==3
    monkeypatch.setattr(module,'QUERY_VERSION','test-new-version')
    lookup_cached('Canadian wetlands policy',['gc.ca'])
    assert len(calls)==4


def test_saved_report_reusable_in_new_python_process_without_provider_calls(tmp_path):
    import subprocess
    import sys
    run(cache_dir=tmp_path,search=search,generator=draft)
    # A separate interpreter has no in-memory report or lock registry.
    code='''import json,sys
from src.regional_research import research_region
from datetime import datetime,timezone
analysis=json.loads(sys.argv[2]); context=json.loads(sys.argv[3])
def fail(*a,**k): raise AssertionError('Provider called on stored report')
r=research_region(analysis,context,cache_dir=sys.argv[1],environ={},search=fail,generator=fail,now=datetime(2026,11,15,tzinfo=timezone.utc))
print(r['status'])
'''
    import json
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path),json.dumps(ANALYSIS),json.dumps(CONTEXT)],
                          capture_output=True,text=True,timeout=5)
    assert result.returncode==0 and result.stdout.strip()=='cached'


def test_explicit_refresh_is_only_path_that_replaces_stored_sources(tmp_path):
    counts={'search':0,'model':0}
    def lookup(*a,**k):
        counts['search']+=1
        return search(*a,**k)
    def generate(payload):
        counts['model']+=1
        return draft(payload)
    run(cache_dir=tmp_path,search=lookup,generator=generate)
    research_region(ANALYSIS,CONTEXT,cache_dir=tmp_path,search=lookup,generator=generate,
                    environ={},now=NOW+timedelta(days=2),refresh=True)
    assert counts=={'search':4,'model':2}
