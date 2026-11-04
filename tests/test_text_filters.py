"""The em dash filter applied to every answer."""

import pytest

from text_filters import remove_em_dashes

EM = "—"
EN = "–"


@pytest.mark.parametrize(
    "before, after",
    [
        # From the live app's answers on 26 Oct
        (f"*Sort of {EM} but it's complicated.*", "*Sort of, but it's complicated.*"),
        (
            f"**Do** drink enough water (~2L/day) {EM} your skin needs it.",
            "**Do** drink enough water (~2L/day), your skin needs it.",
        ),
        (f"PM2.5 {EM} the particle most relevant", "PM2.5, the particle most relevant"),
        # Placement
        (f"{EM} a leading dash", "a leading dash"),
        (f"  {EM} an indented one", "  an indented one"),
        (f"Ends with a dash {EM}", "Ends with a dash"),
        (f"Before a full stop {EM}.", "Before a full stop."),
        (f"Line one {EM}\nLine two", "Line one\nLine two"),
        (f"word{EM}word", "word, word"),
        (f"Two dashes {EM}{EM} here", "Two dashes, here"),
        (f"Note: {EM} this matters", "Note: this matters"),
        (f"({EM} aside)", "(aside)"),
        ("Horizontal bar ― too", "Horizontal bar, too"),
        # Spaced en dash used as an em dash
        (f"Dry today {EN} see the sources", "Dry today, see the sources"),
        # En dashes that are ranges stay
        (f"10{EN}20% concentration", f"10{EN}20% concentration"),
        (f"UV 3 {EN} 5 is Moderate", f"UV 3 {EN} 5 is Moderate"),
        # Nothing to change
        ("No dashes here, and a hyphen-word.", "No dashes here, and a hyphen-word."),
        ("", ""),
    ],
)
def test_remove_em_dashes(before, after):
    assert remove_em_dashes(before) == after


def test_result_never_contains_an_em_dash():
    messy = f"{EM}Start {EM} middle{EM}end {EM}\n{EM}{EM}\n(x {EM}) {EM}."
    assert EM not in remove_em_dashes(messy)


def test_none_passes_through():
    assert remove_em_dashes(None) is None
