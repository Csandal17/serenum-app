"""What users read: starters, prompts and pages, checked without starting Chainlit."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EM = "—"


def string_constants(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def starters():
    """(label, message) for each cl.Starter in app.py."""
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "Starter":
            kwargs = {kw.arg: kw.value.value for kw in node.keywords}
            found.append((kwargs["label"], kwargs["message"]))
    return found


def test_no_em_dashes_in_user_facing_strings():
    for path in ["app.py", "agent.py", "voice.py", "forecast.py"]:
        for text in string_constants(path):
            assert EM not in text, f"{path}: {text[:60]!r}"


def test_no_em_dashes_in_pages():
    for path in ["README.md", "chainlit.md"]:
        assert EM not in (ROOT / path).read_text(encoding="utf-8"), path


def test_starters():
    labels = [label for label, _ in starters()]
    assert labels == ["🌤️ My skin brief today", "🌍 Travel mode", "🌿 What sources say today", "🔬 Myth buster"]


def test_starters_ask_for_conditions_and_sources_not_advice():
    for label, message in starters():
        lowered = message.lower()
        assert "routine" not in lowered, label
        assert "should i" not in lowered, label
        assert "recommend" not in lowered, label


def test_chainlit_readme_is_about_serenum():
    text = (ROOT / "chainlit.md").read_text(encoding="utf-8")
    assert "Welcome to Chainlit" not in text
    assert "GP or pharmacist" in text
    assert "Open-Meteo" in text and "CC BY 4.0" in text  # attribution the licence requires


def test_readme_credits_open_meteo():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Open-Meteo" in text and "CC BY 4.0" in text
