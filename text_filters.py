"""Clean-up applied to every answer before it reaches the screen or the voice.

The prompts ask the model not to use em dashes, but models slip back into
them, so this removes any that get through. It works on the finished text,
so it doesn't depend on the model following the rule.
"""

import re

# Em dash, plus the horizontal bar some models use in its place.
_EM = "\u2014\u2015"
_EN = "\u2013"

_LINE_START_DASH = re.compile(rf"(?m)^([ \t]*)[{_EM}]+[ \t]*")
_DASH_BEFORE_PUNCTUATION = re.compile(rf"(?m)[ \t]*[{_EM}]+[ \t]*(?=[.,;:!?)\]]|$)")
_ANY_EM_DASH = re.compile(rf"[ \t]*[{_EM}]+[ \t]*")
_SPACED_EN_DASH = re.compile(rf"(?<=\S)[ \t]+{_EN}[ \t]+(?=\S)")
_DOUBLE_COMMA = re.compile(r",[ \t]*,")
_COMMA_AFTER_BRACKET = re.compile(r"([(\[])[ \t]*,[ \t]*")
_COMMA_AFTER_COLON = re.compile(r":[ \t]*,[ \t]*")
_COMMA_BEFORE_CLOSER = re.compile(r"[ \t]*,[ \t]*([)\]])")


def _replace_spaced_en_dash(match: re.Match) -> str:
    """A spaced en dash between words is being used as an em dash, so it
    becomes a comma. Between two numbers ("3 [en dash] 5") it's a range, so it stays."""
    text = match.string
    before = text[match.start() - 1]
    after = text[match.end()] if match.end() < len(text) else ""
    if before.isdigit() and after.isdigit():
        return match.group(0)
    return ", "


def remove_em_dashes(text: str) -> str:
    """Replace em dashes with commas (or drop them where a comma would be wrong).

    - "Sort of [em dash] but it's complicated." becomes "Sort of, but it's complicated."
    - A dash at the start of a line, or before punctuation, is dropped.
    - A spaced en dash used the same way ("dry [en dash] use") is treated the same.
    - Unspaced en dashes in ranges ("10[en dash]20%") and spaced ones between
      numbers ("3 [en dash] 5") are left alone.
    """
    if not text:
        return text
    text = _LINE_START_DASH.sub(r"\1", text)
    text = _DASH_BEFORE_PUNCTUATION.sub("", text)
    text = _ANY_EM_DASH.sub(", ", text)
    text = _SPACED_EN_DASH.sub(_replace_spaced_en_dash, text)
    text = _DOUBLE_COMMA.sub(",", text)
    text = _COMMA_AFTER_BRACKET.sub(r"\1", text)
    text = _COMMA_AFTER_COLON.sub(": ", text)
    text = _COMMA_BEFORE_CLOSER.sub(r"\1", text)
    return text
