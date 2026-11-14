import pytest

from src.member_c_evaluation import evaluate, scenarios


def test_evaluation_exercises_brief_chat_and_missing_evidence():
    payloads = []

    def generator(payload):
        payloads.append(payload)
        return "Synthetic placeholder."

    result = evaluate(generator, model_label="test model")
    assert [case["id"] for case in result["results"]] == [
        "brief_with_evidence", "brief_without_evidence", "follow_up", "instruction_override"]
    assert payloads[0]["report"]["reviewed_evidence"]
    assert not payloads[1]["report"]["reviewed_evidence"]
    assert payloads[2]["history"] and payloads[2]["question"]
    assert all(case["draft"]["status"] == "needs_review" and case["human_review"] is None
               for case in result["results"])


def test_evaluation_flags_unknown_urls_and_scenarios_are_fresh():
    result = evaluate(lambda _: "See https://example.org/invented", model_label="test")
    assert all(case["draft"]["status"] == "invalid_citations" for case in result["results"])
    first = scenarios()
    first[0]["analysis"]["region"] = "Modified"
    assert scenarios()[0]["analysis"]["region"] == "Example Basin"
    with pytest.raises(ValueError):
        evaluate(None, model_label="test")
