# Four-person Git workflow

1. Clone the repository and checkout your assigned branch:

```bash
git clone https://github.com/Cz-lov-y/NASA-Space-app-challenge-2026.git
cd NASA-Space-app-challenge-2026
git fetch origin
git switch feature/statistics   # or feature/nasa-data, feature/policy-agent, feature/frontend
```

2. Commit changes only to your feature branch:

```bash
git add .
git commit -m "Implement focused module and tests"
git push -u origin HEAD
```

3. Open a pull request into `main`. Describe the behavior, test results, real NASA dataset references if used, and evidence/limitations. Ask a teammate to review. Resolve feedback before merge.
4. Sync the latest stable interface before integrating:

```bash
git fetch origin
git merge origin/main
```

5. Run `python -m pytest -q`. Check the dashboard with `streamlit run app.py`. Keep `main` deployable and do not commit credentials.

GitHub settings recommendation: require PR review and passing tests for `main` if branch rules are available to the account.

Shared milestones: B -> A validated data, A -> C/D analysis dict, C -> D verified research output, then D integrates the app. Pair on contract changes before modifying another member's files.
