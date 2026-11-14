"""C -> D evidence-research interface.

This is an honest integration stub. Member C should add verified government
policy retrieval and scientific literature research. Never invent citations,
policy statuses, government actions, or evidence of conservation effectiveness.
"""


def investigate_policy(analysis: dict) -> dict:
    """Return the agreed report schema without fabricated research results."""
    if not isinstance(analysis, dict) or not analysis.get("region"):
        raise ValueError("A regional analysis with a region is required")
    return {
        "region": analysis["region"],
        "policies": [],
        "scientific_studies": [],
        "potential_policy_gaps": [],
        "conservation_options": [],
        "citations": [],
        "verification_status": "not_started",
        "limitations": [
            "Policy research agent integration has not been implemented.",
            "No government policy or scientific source has been independently verified.",
        ],
    }
