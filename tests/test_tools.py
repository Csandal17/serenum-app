"""tools.py: trusted-domain filtering, and the Chainlit app's search staying as it was."""

import ast
from pathlib import Path

import pytest

import tools

ROOT = Path(__file__).resolve().parent.parent
TRUSTED = ["nhs.uk", "nice.org.uk", "bad.org.uk", "skinhealthinfo.org.uk"]


@pytest.mark.parametrize(
    "url, trusted",
    [
        ("https://www.nhs.uk/conditions/eczema/", True),
        ("https://nhs.uk/conditions/eczema/", True),
        ("https://bnf.nice.org.uk/drugs/aciclovir/", True),
        ("https://www.skinhealthinfo.org.uk/condition/rosacea/", True),
        ("https://WWW.NHS.UK/conditions/acne/", True),
        ("https://notnhs.uk/page", False),
        ("https://nhs.uk.example.com/page", False),
        ("https://www.kiehls.com/skincare-advice/vitamin-c.html", False),
        ("https://example.com/?next=https://www.nhs.uk/", False),
        ("ftp://www.nhs.uk/file", False),
        ("not a url", False),
        ("", False),
    ],
)
def test_is_trusted_url(url, trusted):
    assert tools.is_trusted_url(url, TRUSTED) is trusted


def test_search_with_trusted_domains_asks_tavily_for_them_and_drops_anything_else(fake_tavily):
    results = tools.search_skincare_evidence("vitamin c serum", include_domains=TRUSTED)

    assert fake_tavily.calls[0]["include_domains"] == TRUSTED
    assert [r["url"] for r in results] == [
        "https://www.nhs.uk/live-well/seasonal-health/sunscreen-and-sun-safety/",
        "https://www.skinhealthinfo.org.uk/condition/atopic-eczema/",
    ]


def test_search_without_trusted_domains_is_unchanged(fake_tavily):
    """What agent.py (the Chainlit app) gets: the open web, minus three sites, as before."""
    results = tools.search_skincare_evidence("vitamin c serum")

    (search_args,) = fake_tavily.calls
    assert "include_domains" not in search_args
    assert search_args["exclude_domains"] == ["reddit.com", "quora.com", "pinterest.com"]
    assert search_args["max_results"] == 3
    assert len(results) == 3


def test_agent_still_searches_without_trusted_domains():
    """agent.py calls the search with the query only, so the Chainlit app is unchanged by this PR.

    The planned app update will switch the app to trusted domains too; update this test then.
    """
    tree = ast.parse((ROOT / "agent.py").read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "search_skincare_evidence"
    ]
    assert calls, "agent.py no longer calls search_skincare_evidence"
    for node in calls:
        assert len(node.args) == 1 and not node.keywords


def test_weather_requests_have_a_timeout(fake_owm):
    tools.get_weather("London")
    tools.get_air_quality(51.5, -0.1)
    tools.get_uv_index(51.5, -0.1)

    assert len(fake_owm) == 3
    assert all(c["timeout"] == tools.REQUEST_TIMEOUT for c in fake_owm)
