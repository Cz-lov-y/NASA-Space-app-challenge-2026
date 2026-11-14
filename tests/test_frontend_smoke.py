"""Render-level tests for Member D's Streamlit integration.

These are deliberately separate from A/B/C's unit tests.
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_demo_dashboard_renders_and_discloses_synthetic_data():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    assert len(app.tabs) == 4
    assert any("SYNTHETIC" in item.message for item in app.error)


def test_demo_research_button_does_not_invent_policies():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    app.button("Investigate This Region").click().run()
    assert not app.exception
    assert any("not yet implemented" in item.message for item in app.warning)
