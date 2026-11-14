# Evidence and policy research agent (Member C)

Input is a deterministic scientific-analysis dictionary, not raw satellite imagery. Research government policy and peer-reviewed literature, then output a structured environmental action brief.

Required checks:

1. Identify jurisdiction and exact policy authority for the studied region.
2. Capture policy name, original government URL, dates, legal/policy status, and retrieval time; do not presume an outdated result is still in force.
3. Retrieve relevant scientific literature (OpenAlex helper is provided) and review the original papers for conclusions and limits.
4. Separate retrieved statements, model interpretation, recommendations, and remaining uncertainty.
5. Use citations tied to each claim; never invent a policy, paper, citation, or absence-of-policy conclusion.

## Current integration

`investigate_policy(analysis)` preserves the C-to-D fields and returns `not_started` when no discovery functions are supplied. Optional keyword arguments `policy_search` and `literature_search` are callables accepting the analysis dictionary and returning lists of candidate records. `src.literature.search_for_analysis` adapts the existing OpenAlex lookup to this interface. For example:

```python
from src.literature import search_for_analysis
from src.policy_agent import investigate_policy

report = investigate_policy(analysis, literature_search=search_for_analysis)
```

Discovery makes network requests and may fail; partial results and limitations are returned. Candidate sources appear in the additive `candidate_sources` field, always marked unverified, and are not policy findings or citations. `unverified` means discovery was attempted, not that any source was verified. The current implementation does not verify policy or publication content or determine jurisdiction. Empty results do not establish policy absence.

### Optional Canadian discovery

`src.policy_discovery.search_for_analysis` searches the [Open Government Portal catalogue API](https://open.canada.ca/en/access-our-application-programming-interface-api), without a key. It requires the caller to explicitly add `country_code: "CA"` to an analysis with a real named region; the current A-to-C contract does not supply a country code, and the agent does not infer one. This is an opt-in, Canada-specific starting point, not global policy coverage:

```python
from src.policy_discovery import search_for_analysis as search_canadian_catalogue
from src.literature import search_for_analysis as search_literature

canadian_analysis = {**analysis, "country_code": "CA"}  # only after independently confirming location
report = investigate_policy(canadian_analysis, policy_search=search_canadian_catalogue,
                            literature_search=search_literature)
```

The portal includes federated records, datasets and other material; catalogue results may not describe policies or apply to the region. The candidate URL points to the catalogue record, not necessarily the original policy. Manually locate and review the original authority, its jurisdiction, applicable dates and present status before using a claim. Never interpret a catalogue timestamp as a policy effective date. Timeouts, malformed responses and empty results leave the report unverified. This adapter makes no claim of exhaustive coverage and does not automatically retrieve or verify policy content.

### Recording reviewed evidence

After a person reviews the original document and its applicability, pass their records as `reviewed_evidence` to `investigate_policy`. Each record needs `source_type` (`policy` or `scientific_literature`), `title`, original `url`, exact analysis `region`, a source-supported `claim`, `reviewer`, `retrieved_at` and `reviewed_at` (ISO timestamps with time zones), and a non-empty `uncertainty`. Policy records also need `jurisdiction` and `authority`; provide `effective_date`, `policy_status`, and `evidence_type` when known. Unknown policy status defaults to `unknown`. A separate record should be used for each claim.

Validated records populate `policies` or `scientific_studies` and a claim-linked `citations` entry; the report status is `partially_reviewed`, even when all supplied records were reviewed. This status documents a person's assertion, not independent verification by the software or a finding that research is complete. The reviewer must confirm that a policy URL is an original official source, dates and status are accurate, the paper supports its claim, and the record applies to the selected location. The software cannot establish those facts. Records with incomplete provenance or a different region are rejected. Policy gaps and conservation options are not generated automatically.

`generate_explanation(analysis, report, generator=..., question=..., history=...)` is a provider-neutral adapter for a brief or follow-up. The generator callable receives a payload containing system instructions, analysis, report, question, and caller-managed history, and returns text. Without a generator it reports unavailable; generated text is marked `needs_review`. The caller must independently review claims and citations before display. No model or search credentials are configured yet. Keep future keys in local environment variables; never commit them. Mark any offline mocked output as synthetic.

The generation payload contains the analysis, report limitations, and reviewed source claims only; it excludes candidate sources and reviewer identities. For chat, pass a non-empty `question` and a list of `{ "role": "user" | "assistant", "content": "..." }` turns for the same region. The caller owns session isolation, history length and any retrieval needed for new questions. The adapter detects literal URLs in generated text that do not match a reviewed source and returns `invalid_citations`; do not display that draft. This simple URL check cannot establish that a claim is supported, detect every invented reference, or prevent prompt injection. A `needs_review` result still requires a person to check every claim, citation and limitation before display. Provider adapters should translate the system instructions into the provider's instruction channel, treat all other content as untrusted data, apply timeouts and output limits, and avoid logging secrets.

For integration, Member D should display limitations and verification status, keep candidate sources distinct from verified findings, and treat generated text as requiring review. Agree with the team before changing the shared contract or dependencies.

## Handoff and presentation readiness

Run `python -m src.member_c_demo` from the repository root for an offline JSON example using the bundled synthetic data. It shows the analysis, the default report and the model-unavailable state. It does not make network calls or generate policy claims. This is an integration aid, not a reviewed fallback report.

The existing frontend calls `investigate_policy(analysis)` without optional search or review inputs, so it continues to show the honest `not_started` report. Member D must explicitly wire any reviewed records, discovery and generation adapter into their interface; no frontend files were changed here. Keep chat history scoped to the selected region, display the synthetic-data warning, source links, review status and limitations, and never publish an `invalid_citations` draft. A `needs_review` draft is not an approved answer.

Before a real demonstration, obtain Member A's real analysis and Member B's quality-reviewed data and geographic context. Agree with Member D on display and loading/failure behavior. Select and configure a model provider separately, review actual original sources for the chosen region, and rehearse the full workflow with those records. The included demo data and mocked test generator are synthetic and do not constitute a reviewed environmental finding. No real reviewed fallback report or live provider is included. Run `python -m pytest -q` after integration; automated tests use mocked discovery and do not establish that a provider or a cited policy is current.
