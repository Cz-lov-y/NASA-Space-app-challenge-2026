# Architecture

Small modular Python application; keep interfaces stable during the hackathon. Clean Architecture concepts are used lightly via boundaries, not a large framework.

```text
NASA MODIS / GLDAS (future real integration)
       |
       v
src/nasa_data.py + src/preprocessing.py  [B]
       |
       v
src/statistics.py + src/divergence.py    [A]
       |                       |
       v                       v
src/policy_agent.py             app.py / src/ui/ [D]
src/literature.py [C]                 ^
       |                              |
       +----- verified evidence ------+
```

Member B owns acquisition/QA and a normalized DataFrame; Member A owns science and structured findings; Member C owns retrieval, verification and source-aware reports; Member D owns presentation, integration and deployment.

Do not make an LLM infer a p-value, manufacture citations, or substitute for numerical computation. The synthetic demo is for integration tests only.
