# Member C: regional research backend

## Local configuration verification — 2026-11-14

DeepSeek and Tavily credentials are configured privately in the Git-ignored `.env` with owner-only permissions. One live basic Tavily request returned two usable sources; a small live DeepSeek request returned valid JSON through the application model adapter. These are connection checks, not a reviewed regional research report. The DeepSeek tracking ID is not required for authentication and is not stored in the repository.

The adapter disables thinking mode specifically for `api.deepseek.com` to keep short JSON summaries within the output budget. DeepSeek currently enables thinking by default; an initial small-limit request returned unusable JSON. See the [official thinking-mode documentation](https://api-docs.deepseek.com/guides/thinking_mode/). Other providers retain their existing request settings. Research adapter tests pass after this adjustment.

Implemented in `src/regional_research.py`; the existing human-reviewed evidence interface in `src/policy_agent.py` remains available. This backend can support the future globe selection handler. The frontend is deferred to the human team for design and implementation.

## Current deliverable

`research_region(analysis, region_context, ...)` returns an independent copy of A's numerical analysis, source candidates with retrieved excerpts, and an optional structured qualitative draft. It never sends numerical analysis to the model. Automated tests use injected adapters. A bounded live Canada demonstration was then attempted using real source excerpts; its actual outcome and request counts are recorded below and in the saved report, without implying human review.

Statuses are `needs_context`, `unavailable`, `partial`, `complete`, and `cached`. A complete machine report remains `machine_generated_unreviewed`; source records remain `unverified`. Completion describes the pipeline, not scientific, legal or editorial verification. Citation-ID validation checks membership in the retrieved source set; it cannot establish that a claim is supported by the text. This distinction must remain visible in the UI.

## Shared input and output

```python
from src.regional_research import research_region

report = research_region(
    analysis,  # A's JSON-compatible dict; region must match
    {
        "region_id": selected_region_id,
        "bbox": [west, south, east, north],
        "dataset_version": dataset_version,
        "period": ["2003-01-01", "2024-12-31"],
        "jurisdictions": jurisdictions,
    },
    cache_dir=".cache/regional_research",
)
```

Each jurisdiction is `{"name": "country or jurisdiction", "land_area_fraction": area_fraction, "official_domains": ["agency.example"]}`. Country names must come from actual boundary intersections or a human selection; a grid centroid does not identify every applicable jurisdiction. Never substitute an arbitrary country for an unknown intersection. Domain lists must be human/source verified. Without a trusted domain list, policy search candidates are explicitly not authenticated as official government sources. Country-level context may not establish local jurisdiction, policy applicability or current legal status.

Countries are ordered by descending supplied land-area fraction, with name as a stable tie break. The first three receive two queries each; remaining jurisdictions are returned as `omitted_jurisdictions` for later user selection. At most six search requests and twelve unique sources are included. Country area weights must be computed over land, not ocean-containing cell area. Any missing/fallback weights must be documented by the caller.

The report has `region_id`, `status`, `verification_status`, `quantitative_analysis`, `qualitative`, `candidate_sources`, `citations`, `jurisdictions`, `omitted_jurisdictions`, `retrieved_at`, `cache_key`, and `limitations`. A successful `qualitative` object contains:

```json
{
  "summary": {"text": "Qualitative summary with uncertainty.", "source_ids": ["S1"]},
  "policies": [{"text": "Candidate policy context needing review.", "source_ids": ["S1"]}],
  "scientific_studies": [],
  "conservation_options": []
}
```

Each claim needs an allowed source ID. Prose with numeric digits or URLs is rejected conservatively to keep numerical statements in the dataset panel; policy dates can be reviewed separately in original sources. Numeric environmental values, trends, causal claims and policy-failure conclusions are prohibited in the model instructions. This is not a semantic correctness guarantee: number words (for example, "ninety percent"), unsupported qualitative trend statements and causal prose can pass the structural validator. Human review remains necessary; do not describe this check as preventing all fabricated quantitative or causal claims. Original source URLs, excerpt text and retrieval timestamps are kept in candidate records; citations resolve IDs to the original URLs. Model prose must be rendered as text, not trusted HTML.

## DeepSeek local setup

The team selected DeepSeek for the model service. The [official first-call guide](https://api-docs.deepseek.com/) currently documents `https://api.deepseek.com` and `deepseek-flash`; these are the example defaults in `.env.example` (checked 2026-11-14). The backend appends `/chat/completions`. An account login or an available token balance is not sufficient: the server needs an API key created through the [DeepSeek platform](https://platform.deepseek.com/). Do not paste the key into chat.

1. From the repository directory, run `cp .env.example .env` if you have not already created `.env`. Preserve an existing local configuration rather than overwriting it.
2. Run `chmod 600 .env`, then open that local file in your editor. Set `MODEL_API_KEY` to the DeepSeek API key. Keep `MODEL_BASE_URL=https://api.deepseek.com` and `MODEL_NAME=deepseek-flash`, or choose another currently documented model available to your account. `.env` is private local configuration and must remain excluded from Git.
3. Set `POLICY_SEARCH_API_KEY` to a separate Tavily API key. DeepSeek model credits do not authenticate the current Tavily discovery adapter. Search remains unavailable without that separate key; no DeepSeek web-search adapter is implemented here.
4. In the same zsh terminal that will start the server, load the file without printing its contents:

   ```sh
   set -a
   source .env
   set +a
   ```

   This sources a shell configuration file, so only use the file you created locally. Values must be valid shell assignments; quote values containing shell metacharacters. Do not run `cat .env`, `printenv`, or commands that echo keys into logs or screenshots.
5. Start the application from this terminal with `.venv/bin/python -m streamlit run app.py`. The existing app is not yet connected to the new `research_region` backend; D's future selection handler must call it before the new research behavior appears. Starting the app alone does not verify the new provider configuration.
6. Once D connects it and B supplies actual jurisdictions, test one real region. This will use the configured service credits; inspect the original source pages and output labels before rehearsing. Automated tests have confirmed request construction only, not live account access, API billing, response latency or model quality.

The [DeepSeek JSON-output guide](https://api-docs.deepseek.com/guides/json_mode/) documents JSON-object response mode. The adapter requests this mode; blank, truncated or malformed output becomes a partial/unavailable draft, with source candidates retained. There is no automatic paid retry. If this provider's model changes, update the local `MODEL_NAME` based on the official documentation.

## Human setup, in order

1. Decide who owns live search/model service accounts and approve the intended demo usage and spending limits. The backend performs at most six Tavily searches and one model request for an uncached region selection; it does not choose or provision a paid plan.
2. Obtain a Tavily API key. Put it in the server environment as `POLICY_SEARCH_API_KEY`. Never place real keys in repository files, browser code, screenshots or commit messages.
3. Choose an OpenAI-compatible chat-completions provider and model that support JSON-object responses. Configure `MODEL_API_KEY`, `MODEL_BASE_URL` and `MODEL_NAME` on the server. `MODEL_BASE_URL` must be an HTTPS API base, usually ending in `/v1`; the backend appends `/chat/completions`. Compatibility with a particular provider has not been live-tested. Missing credentials produce an explicit unavailable/partial result.
4. Supply real jurisdiction intersections from B's regional catalog. If no jurisdictions are known, the backend returns `needs_context` and does not search. Confirm government domain allowlists for the demo countries, or retain unverified-policy-candidate wording.
5. Call the backend for one real region with the actual dataset version and frozen analysis period. Inspect returned source excerpts and original pages; check geography, policy status and whether each drafted claim is supported. A successful request does not certify these points.
6. Repeat for chosen real demonstration regions across continents. Enable `cache_dir` to retain genuine generated reports. Keep retrieval timestamps and machine-review labels. Do not create synthetic report caches or reuse one country's report for another region.
7. For reviewed claims, record the evidence through the existing `validate_reviewed_evidence` / `investigate_policy` pathway with reviewer and review time. This automatic backend never promotes a machine report to human reviewed.
8. D should call research from its background job, show loading and failure states, and discard completed responses whose region/context no longer matches the selected region. Server-side credentials must never be sent to the globe component. Debounce repeated clicks and prevent duplicate jobs for the same cache key.

The backend function does not automatically load `.env`. The new readiness-first CLI safely parses allowlisted literal assignments without shell evaluation. Local frontend development can alternatively export these variables in the shell before starting Streamlit. Deployment must inject them into the server process. Streamlit's `st.secrets` values are not automatically environment variables; the future frontend may pass a server-only `environ` mapping or map them into the process at startup. Do not expose the mapping to JavaScript or download exports.

## Caching, failure and reproducibility

The cache key includes region ID, bounding box, the complete normalized jurisdiction list and domain lists, dataset version, analysis period and query version. A caller must change `dataset_version` when processed inputs or relevant processing decisions change. The report always returns the current numerical analysis, including when a qualitative cache is used.

Fresh caches are reused for twenty-four hours. When live credentials are missing or a provider fails, an older exact-context cache may be returned with `cache_stale=true`, its original retrieval time, and an explicit fallback limitation. Reports for another region, period, boundary or dataset are not reused. `cache_dir=None` disables disk storage. Cache records include source excerpts, so use a server directory excluded from Git unless deliberately publishing a reviewed handoff artifact. Do not assume every transient or failed response is cached: only reports with a validated qualitative draft are stored.

HTTP calls have bounded connect/read timeouts, no automatic retry, and generic failure messages that do not echo provider errors or keys. With six sequential discovery requests plus one model request, a slow uncached job can take several minutes; the frontend should keep navigation responsive and show progress while the worker runs. The research function itself is synchronous; the optional `ResearchJobs` wrapper below supplies process-local scheduling and cancellation of delivery. Search results without usable source text are discarded. Search failure/absence never proves that a policy is absent.

## Validation and next handoff

Run `.venv/bin/python -m pytest -q tests/test_regional_research.py`. Tests cover missing context/keys, immutable numerical analysis, request/source caps, jurisdiction ordering, unverified source labels, malformed/injected citations, numeric prose rejection, exact-context cache isolation, stale fallback, provider failures and credential redaction.

## Readiness-first command line

The command below loads B's stored geometry/observations, checks A's current artifact and reports credential-presence booleans only. It performs no network requests and writes no report:

```sh
.venv/bin/python scripts/run_regional_research.py --region grid_r14_c07
```

This CLI reads the local `.env` as literal assignments for the four documented variables; existing process environment values override the file. It does not execute `source`, interpolate `$()` or expand shell variables. `.env` must contain literal values rather than references such as `MODEL_API_KEY=$OTHER_KEY`. It never prints actual values. Unknown variable names are ignored; malformed assignments fail with a generic message.

After deliberately enabling live use, this command runs one region and writes its actual report:

```sh
.venv/bin/python scripts/run_regional_research.py \
  --region grid_r14_c07 \
  --official-domain canada.ca --official-domain gc.ca \
  --live --output data/research/grid_r14_c07_context_brief.json
```

`--live` is required for provider access and `--output`. Missing settings, unknown regions and stale screening artifacts fail before live requests. The command uses `.cache/regional_research` by default. Domain overrides apply only to this server-side call and only to cells with one jurisdiction; they do not modify B's catalog. The Canada domains used for this example were checked against the [federal water page](https://www.canada.ca/en/environment-climate-change/services/water-overview.html) and the [agriculture environment page](https://agriculture.canada.ca/en/environment), including their linked `gc.ca` services. A matching host does not validate legal status, location-specific applicability or evidence support.

## Real Canada sample

The example `grid_r14_c07` covers longitude minus one hundred ten to minus one hundred and latitude fifty to sixty north, EPSG:4326. B's coarse Natural Earth boundary identifies Canada as its sole country candidate. Actual GLDAS monthly observations are available for both soil layers; regional NDVI remains missing. A's available single-indicator analysis is exploratory. This report supplies jurisdiction context only and cannot establish greening/drying divergence, source QA approval, ecological damage, causality or policy failure.

`data/research/grid_r14_c07_context_brief_first_partial.json` preserves the first actual attempt: two basic Tavily searches, four genuine source candidates, and one attempted DeepSeek generation that was not displayed because generation/validation did not succeed. That original path did not record a granular failure code, so the precise first failure remains unknown. No citations or qualitative prose were fabricated to fill the gap.

A second explicitly bounded model-only attempt reused those saved excerpts and made no further search requests. It completed successfully with four cited source records and `verification_status=machine_generated_unreviewed`; the genuine successful report is also cached under its exact context key. `data/research/grid_r14_c07_context_brief.json` records its real result, request counts and source timestamps. The result's `status`, `qualitative`, `verification_status` and any `generation_failure_code` are authoritative; a saved JSON file alone does not imply successful generation. Total authorized live budget for this sample was two discovery requests and two model attempts, with no automatic retries. If generation is successful, it remains machine generated and unreviewed; the initial partial report is preserved.

The retrieved sources include a federal nature strategy, a federal wetland guide, a Scientific Reports soil-erosion paper, and a Senate soil-health report. These have different document types. The wetland guide is historical, so current applicability needs separate review. The erosion paper's soil loss is a different variable from GLDAS soil-water storage. The Senate document is a legislative study/report rather than automatically peer-reviewed scientific literature. None establishes that a policy currently applies throughout this cell. Excerpt inspection and domain matching during automation do not constitute human review or legal validation.

Granular generation failure codes now distinguish timeout, provider error, invalid JSON, invalid citation IDs, numeric digits/URLs in prose, and other invalid structure. They expose no raw provider bodies or credentials. No additional live requests should be necessary to inspect the saved sample.

The HTTP search adapter follows [Tavily's official search endpoint documentation](https://docs.tavily.com/documentation/api-reference/endpoint/search): bearer authentication, explicit source content and no provider-generated answer. No provider account, deployment, or live-source verification is completed by the automated tests. The team's remaining decisions are service credentials/budget, trusted country/domain mapping, selected rehearsal regions, and review of generated claims.


## Offline report reuse on a fresh checkout

A genuine machine report is committed for the Canada sample; a fresh checkout does not need private `.cache` files or credentials to inspect it. The explicit cache-only path loads the report, verifies its exact selection context, refreshes numerical analysis from the current regional artifact, and performs no network requests or `.env` reads:

```sh
.venv/bin/python scripts/run_regional_research.py \
  --region grid_r14_c07 \
  --official-domain canada.ca --official-domain gc.ca \
  --cached-only \
  --report-file data/research/grid_r14_c07_context_brief.json
```

`--output` may be added to export that validated report with current numerical values. `--live` and `--cached-only` are mutually exclusive. Without an explicit report path, cache-only mode tries the private exact-key cache and then `data/research/<region_id>_context_brief.json`. It never substitutes another region's report. Its `configured` flags are false because credentials are deliberately not loaded (`credentials_loaded=false`); these flags do not claim that the user lacks service accounts.

The public `research_context_key(context)` supplies the same key used by live caching and job selections. `load_cached_report(path, analysis, context, now=None, allow_stale=True)` is the no-network Python interface. It requires region, bounding box, dataset fingerprint, analysis period, jurisdiction/domain mapping and query version to match. It validates unique source IDs, source URLs, source/citation correspondence, timestamps, official-domain labels and machine-review status; it rejects incomplete first-attempt reports. Current numerical analysis replaces the stored numerical payload. A stale report retains its original timestamp and gets a limitation and `cache_stale=true`; `allow_stale=False` rejects it. This verifies cache structure and selection compatibility, not source authenticity, legal applicability or claim truth.

If processing inputs change, the source fingerprint changes and the saved report is intentionally rejected. Do not edit the saved key or relabel a different-country report to bypass this check. A newly authorized live run can create a genuinely matching report. Query version changes also require fresh output; old source text cannot silently become new research. The existing live `research_region` cache path uses the same validation before reuse.

## Optional background jobs for D

`src/research_jobs.py` provides a UI-independent manager. D can create one manager per trusted application/user context and retain it while the app reruns; do not create a new manager on every interaction or share one user's credential-bearing jobs across users. The default runner is `research_selected_region`, so submitting is an explicit request for provider work. For offline operation, inject a runner that calls `load_cached_report` with the current bundle and analysis.

```python
from src.research_jobs import ResearchJobs
from src.regional_research import research_context_key

jobs = ResearchJobs(max_workers=2, max_pending=4, timeout_seconds=240)
# Explicit submit after selection; settings stay on the server.
request = jobs.submit(bundle, environ=server_settings, cache_dir=cache_path)
# Save this request_id as the latest request for the current UI selection.
snapshot = jobs.poll(
    request["request_id"],
    region_id=current_bundle["region_id"],
    context_key=research_context_key(current_bundle["research_context"]),
)
```

States are `queued`, `loading`, `complete`, `failed`, `cancelled`, `timed_out`, `unknown` and `stale`. Only `complete` includes a report; that report's own status still distinguishes successful, partial, cached or unavailable research. An exact-context duplicate shares the existing queued/running/completed job. A full queue raises `RuntimeError`; the UI should display a busy state and avoid blindly retrying. Jobs are bounded to at most two worker threads, with a configurable bounded number of waiting jobs; terminal history is bounded separately. The manager returns generic error codes without exception strings, provider bodies or credentials.

Before displaying a result, D must verify that its request ID is still the latest selected request. `poll` also requires matching region and context and otherwise returns `stale` without a result. Submission snapshots the input bundle and credentials in memory, and returned reports are copied so external mutations cannot alter stored results. Context changes in geometry, release, period or jurisdiction mapping create a different key. If only credentials change for an otherwise identical selection, the existing job is deliberately reused; cancel/recreate the manager when switching user/provider context.

`cancel(request_id)` suppresses delivery immediately. A queued wrapper skips the provider call when dequeued. A running HTTP call cannot be forcibly stopped by Python threads; it continues to occupy capacity until it returns, and its result stays suppressed. Timed-out jobs behave the same way. This prevents rapid cancel/submit interactions from creating an unbounded executor backlog. The display deadline includes queue time; a result completed before the deadline remains available even if polling happens later. Provider adapters retain their own connect/read timeouts; custom injected runners must bound their own I/O.

Call `close(wait=False)` when disposing of the context; it rejects new submissions and suppresses pending results. Running requests may still finish. There is no database, distributed worker, cross-process coordination, automatic restart recovery or persistent job history. Deployments with multiple processes need application-specific coordination or accept process-local behavior. Test coverage uses event-controlled offline runners to verify duplication, queue limits, queued cancellation, late-result suppression, safe failure codes and stale selection handling.

Run `.venv/bin/python -m pytest -q tests/test_regional_research.py tests/test_research_jobs.py tests/test_agent.py` for the combined backend checks. No additional paid calls were made for this caching/jobs milestone.
