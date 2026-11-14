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

Discovery makes network requests and may fail; partial results and limitations are returned. Candidate sources appear in the additive `candidate_sources` field, always marked unverified, and are not policy findings or citations. `unverified` means discovery was attempted, not that any source was verified. The current implementation does not verify policy or publication content, determine jurisdiction, or provide a policy-search provider. Empty results do not establish policy absence.

`generate_explanation(analysis, report, generator=..., question=..., history=...)` is a provider-neutral adapter for a brief or follow-up. The generator callable receives a payload containing system instructions, analysis, report, question, and caller-managed history, and returns text. Without a generator it reports unavailable; generated text is marked `needs_review`. The caller must independently review claims and citations before display. No model or search credentials are configured yet. Keep future keys in local environment variables; never commit them. Mark any offline mocked output as synthetic.

For integration, Member D should display limitations and verification status, keep candidate sources distinct from verified findings, and treat generated text as requiring review. Agree with the team before changing the shared contract or dependencies.
