# Evidence and policy research agent (Member C)

Input is a deterministic scientific-analysis dictionary, not raw satellite imagery. Research government policy and peer-reviewed literature, then output a structured environmental action brief.

Required checks:

1. Identify jurisdiction and exact policy authority for the studied region.
2. Capture policy name, original government URL, dates, legal/policy status, and retrieval time; do not presume an outdated result is still in force.
3. Retrieve relevant scientific literature (OpenAlex helper is provided) and review the original papers for conclusions and limits.
4. Separate retrieved statements, model interpretation, recommendations, and remaining uncertainty.
5. Use citations tied to each claim; never invent a policy, paper, citation, or absence-of-policy conclusion.

`src/policy_agent.py` is intentionally a nonfunctional, honest stub and returns `verification_status: not_started`. LLM provider keys belong in local environment variables; never commit them. Mark any offline mocked output as synthetic.
