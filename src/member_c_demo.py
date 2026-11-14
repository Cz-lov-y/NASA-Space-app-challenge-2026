"""Offline synthetic integration example; this is not a policy assessment."""
import json

import pandas as pd

from src.divergence import analyze_region
from src.nasa_data import get_timeseries
from src.policy_agent import generate_explanation, investigate_policy


def run_demo() -> dict:
    """Exercise the B -> A -> C interface without network or model calls."""
    frame = pd.concat([get_timeseries("demo-region", variable)
                       for variable in ("ndvi", "soil_moisture")])
    analysis = analyze_region(frame)
    report = investigate_policy(analysis)
    explanation = generate_explanation(analysis, report)
    return {"notice": "SYNTHETIC DEMONSTRATION: not NASA observations or verified policy research.",
            "analysis": analysis, "report": report, "explanation": explanation}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, allow_nan=False))
