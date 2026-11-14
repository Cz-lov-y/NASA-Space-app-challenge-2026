# Member C revised delivery plan

## Repository review and working assumptions

This plan is based on a fetch of origin and inspection of the tracked code,
tests, data summaries and team branches. Main and the current policy-agent
branch point to `84c045b`. The frontend branch is already an ancestor of main;
the NASA-data branch points to main. Member A has an additional unmerged commit,
`4a66018` (`Add global exploratory analysis boundary`). These references describe
this review, not a promise that teammates have stopped making changes.

The agreed scope is the whole Earth, at least January 2003 through December
2024, with DeepSeek used for initial model testing. The first deliverable should
explain the available global aggregates. The requested map-click experience is
a separate integration milestone: global averages cannot supply local trends.

| Member | What is available | What C must account for |
| --- | --- | --- |
| A | Schema 0.3 regional statistics, annual aggregation, uncertainty, reliability and real GLDAS regression fixture. Unmerged global wrapper in `4a66018`. | Preserve A's numerical outputs and limitations. Use the global wrapper once integrated; global divergence is deliberately not assessed. |
| B | Preliminary real MODIS/GLDAS global CSV and provenance. The required period has 264 months for each of three variables (792 rows). | All present values remain `coverage_review_required`. The geographic footprints differ and overlap has not been established. Data availability is not scientific QA approval. |
| C | Optional candidate discovery, supplied human-review records, citation-linked reports, provider-neutral brief/chat adapter, offline demo and local evaluation harness. | No live model, real reviewed evidence package or worldwide jurisdiction discovery is implemented. Canadian catalogue discovery is optional and geographically limited. |
| D | Streamlit dashboard, evidence panels, exports and smoke tests, already merged. | App still uses the synthetic reader and calls research without discovery, reviewed evidence or generation. Clickable regional analysis and chat are not implemented. UI status logic needs alignment with A. |

Relevant files: `docs/contracts.md`, `docs/data_sources.md`,
`data/processed/global_combined/metadata.md`,
`data/processed/global_combined/quality_report.csv`, `src/nasa_data.py`,
`app.py`, `src/ui/presentation.py`, and Member A's branch files
`docs/global_exploratory.md` and `src/global_exploratory.py`.

Current validation: 91 tests passed with 68 subtests when excluding
`tests/test_nasa_processing.py`. The full suite stopped at collection because
the local environment lacks `rasterio`; no data-processing success is claimed.
The old C demo runs, but its sparse synthetic record now yields insufficient
annual data under A's complete-calendar-year defaults. It remains an interface
example, not a useful positive-trend demonstration.

## Phase 1: align C's input and interpretation with the global work

Objective: provide a stable explanation input that accurately represents the
available science and its geographic scope.

- Coordinate integration of A's global wrapper. Inspect the focused commit
  rather than replacing teammates' files with an older branch snapshot.
- Add C-owned tests/fixtures for schema 0.3, `scope=global_exploratory`,
  `divergence_detected=null`, `divergence_status=not_assessed`, insufficient data,
  QA not reviewed and differing spatial footprints.
- Preserve the observation window, variable names, units, uncertainty, adjusted
  significance, reliability reasons and source limitations in the model input.
  Do not ask the model to recompute statistics or interpret global averages as
  evidence of local co-occurrence, environmental damage or policy failure.
- Use a deliberate soil indicator selection with A; `soil_water_0_10cm` is the
  global wrapper default. Do not silently rename or combine both soil layers.
- Update C's demo to use complete synthetic monthly fixtures for offline checks;
  add a separate explicit real-data demonstration once A's wrapper is available.

Completion: C's tests exercise the current analysis shape; the global explanation
states that Green Mirage is not assessed and carries the coverage/QA limitations.
Dependencies: A's wrapper availability for the real-data path; B's provenance and
QA decisions for scientific interpretation. Fixture-based development can start now.

## Phase 2: connect DeepSeek through the existing generation interface

Objective: produce a professional passage and follow-up answers using configurable
instructions, without binding policy research to one model.

- Implement a C-owned provider adapter with environment-based credentials and
  configurable exact model identifier. Consult current official provider docs
  during implementation before selecting API options or defaults.
- Keep system instructions in the provider's instruction channel; serialize
  analysis, reviewed evidence and the user's question as input data.
- Handle timeouts, authentication failures, rate limits, malformed/empty output
  and output limits. Keep API keys and sensitive request logs out of Git.
- Bound conversation history and record provider-reported token usage, model
  identifier and latency where available. Make network calls explicit.
- Use prompt configuration first for tone and structure; model-weight fine-tuning
  is not a prerequisite for the requested professional passage style.
- Test with mocked provider responses, then make a small live smoke test once
  the user has supplied local API configuration and funded access.

Completion: the same callable supports the brief and chat functions, failures
return a usable unavailable state, and a live response is reviewed against its
inputs. Dependencies: the user's provider account, local key and funded access
for the live step only. Adapter implementation and mocked tests can start now.

## Phase 3: assemble a reviewed global evidence package

Objective: ground the global explanation in a small, defensible set of original
sources before attempting broad jurisdiction coverage.

- Discover and review scientific literature relevant to vegetation greenness,
  soil-water interpretation and the limitations of global aggregation.
- Review original international policy/framework sources for global context.
  Label their authority and legal/policy status explicitly; an international
  framework does not establish a country's local legal obligations.
- Store claim-level source records, retrieval/review timestamps, uncertainty
  and applicability. A `whole_earth` region label alone does not establish
  worldwide applicability of a national policy.
- Distinguish the historical observation window (2003–2024) from a policy's
  effective dates and status as of review. Current policy context cannot explain
  historical changes without supporting evidence and an appropriate analysis.
- Improve literature queries for global concepts instead of relying on raw
  region IDs and variable names. Keep Canadian catalogue discovery opt-in.
- Preserve unsupported questions as evidence gaps. Never treat no search result
  as proof of no policy, or a model-generated statement as reviewed evidence.

Completion: a reviewer can trace each contextual statement to an original source
and see geographic, temporal and interpretive limits. Dependencies: source review
and agreed presentation focus; exhaustive country-by-country research is not
required for the first global demonstration.

## Phase 4: evaluate and refine the passage and follow-up behavior

Objective: make the explanation accurate, readable and affordable under repeatable
tests using DeepSeek first.

- Extend `src/member_c_evaluation.py` with global scope, unreviewed QA, unknown
  jurisdiction, policy-date mismatch, unavailable provider and unsupported local
  claims, alongside the existing fictional brief/chat/override scenarios.
- Review factual support, citations, uncertainty, professional tone, question
  relevance and resistance to instructions to invent evidence.
- Keep unavailable and invalid-citation drafts out of the display path. Existing
  `needs_review` is a draft state; define how reviewed presentation answers are
  approved with D before integration.
- Repeat runs and document model/settings, provider-reported usage, latency and
  observed cost. Do not infer quality or cost from a placeholder run.
- Keep the final presentation model configurable; selection can happen later
  using the same cases. Changing models requires rerunning evaluations.

Completion: representative outputs and failures are reviewed and documented, and
the chosen testing configuration meets an explicit quality/budget target.
Dependencies: Phases 1–3 for meaningful live evaluation; synthetic tests can run earlier.

## Phase 5: hand the global brief and chat to Member D

Objective: connect the working C service to the existing dashboard without taking
over frontend ownership.

- Provide a C-owned example for analysis -> evidence report -> generated brief,
  plus follow-up calls and explicit return-state handling.
- Give D the configuration steps, expected statuses, source records and timeout
  behavior. Preserve the existing C-to-D report keys; propose additive changes
  before changing any shared schema.
- D wires real data/loading, scope-appropriate science labels, generation,
  citations and chat. C supports adapter debugging and integration tests.
- Scope chat state to analysis region, period and selected indicators; reset or
  invalidate it when those inputs change. Show limitations with the explanation.
- Rehearse the global case, missing evidence, insufficient data and API failure.
  Prepare a clearly labeled, reviewed static fallback for the presentation.

Completion: a real-data global flow works end to end with sources and limitations,
and stale conversation/report data cannot appear under a changed selection.
Dependencies: D's integration and secrets configuration, A's global path, B's
documented data/QA status. Publication/deployment remains D's task.

## Phase 6: extend to selected map locations when regional inputs exist

Objective: deliver location-specific context and policy research for the original
map-click experience.

- B supplies spatially resolved or regional time series with geographic support
  and comparable footprints. D supplies the selected feature/location and stable
  region identity; A supplies the corresponding regional analysis.
- Agree on an explicit location-context input: coordinates or boundary, country
  and relevant administrative jurisdictions, provenance and ambiguity. Reverse
  geocoding alone is not proof that a policy applies.
- C resolves jurisdiction-aware source selection and separately reviews national
  and subnational policy applicability. Global framework context may supplement
  these sources but cannot replace local research.
- Test several jurisdictions, ambiguous borders, unsupported countries and no
  reviewed sources. Return limited evidence honestly rather than substituting
  the global trend for a local measurement.

Completion: a clicked region has its own scientific result and appropriately
scoped sources. Dependencies: regional inputs and map selection from B/A/D.
This phase is required for the original local experience, but can follow a
working global presentation if the team chooses that delivery order.

## File ownership and immediate next work

Work on `feature/policy-agent`. Preserve the existing local evaluation changes
(two added files and the methodology edit); they are not yet committed.

C may edit `src/policy_agent.py`, `src/evidence.py`, `src/literature.py`,
`src/policy_discovery.py`, `src/member_c_demo.py`,
`src/member_c_evaluation.py`, `docs/agent_methodology.md` and this plan.
Use new C-specific adapter, evidence-fixture and test files as needed. Prefer
new `tests/test_member_c_*.py` files for cross-contract checks.

Coordinate changes to `docs/contracts.md` and dependency files. Leave A's
statistics/global wrapper, B's ingestion/raw/processed data and D's
`app.py`/`src/ui/` implementations to their owners. Review remote changes before
each integration and do not switch branches or merge over uncommitted work.

The next implementation slice is Phase 1's scope/contract tests and demo refresh,
followed by Phase 2's DeepSeek adapter with mocked tests. Neither requires waiting
for worldwide policy coverage or local map data. The next team handoffs are A's
global wrapper, B's documented QA/indicator choice and D's global display/brief/chat
wiring. The user only needs to configure DeepSeek access before a live model call.
