# EarthRisk — Green Mirage

NASA Space Apps Challenge 2026 | Toronto | 14–15 November 2026

**Mission:** Investigate whether increasing vegetation greenness coincides with deteriorating water conditions, then connect reproducible Earth-observation findings to verifiable policy and conservation evidence.

## Project status

**Scaffold / demonstration only.** The included CSV is deliberately synthetic; it is NOT a NASA dataset, an environmental finding, or a verified policy report. Replace it with authentic, quality-controlled NASA observations before presenting scientific conclusions.

## Team ownership

| Member | Branch | Ownership |
| --- | --- | --- |
| A — Statistical modeling / team lead | `feature/statistics` | `src/statistics.py`, `src/divergence.py`, `tests/test_statistics.py`, `docs/methodology.md` |
| B — NASA data engineering | `feature/nasa-data` | `src/nasa_data.py`, `src/preprocessing.py`, `data/sample/`, `tests/test_data.py`, `docs/data_sources.md` |
| C — Policy research agent | `feature/policy-agent` | `src/policy_agent.py`, `src/literature.py`, `src/evidence.py`, `tests/test_agent.py`, `docs/agent_methodology.md` |
| D — Frontend and deployment | `feature/frontend` | `app.py`, `src/ui/`, `.streamlit/`, dependencies, and integration |

## Quick start (Python 3.12 recommended)

```bash
git clone https://github.com/Cz-lov-y/NASA-Space-app-challenge-2026.git
cd NASA-Space-app-challenge-2026
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

On Windows, activate with `.venv\Scripts\activate`.

## Contracts

1. `src.nasa_data.get_timeseries(region, variable) -> pandas.DataFrame` (Member B to A).
2. `src.divergence.analyze_region(data) -> dict` (Member A to C/D).
3. `src.policy_agent.investigate_policy(analysis) -> dict` (Member C to D).

See `docs/contracts.md` for exact fields and integration expectations.

## Workflow

Create work only on your assigned feature branch, push, and open a pull request against `main`. Keep `main` runnable. Run `python -m pytest -q` before requesting review. Never commit API keys or claim that the demonstration data is authentic.

See `docs/team_workflow.md` for detailed commands and `docs/architecture.md` for the system design.
