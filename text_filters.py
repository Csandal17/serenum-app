"""Clean-up applied to every answer before it reaches the screen or the voice.

The prompts ask the model not to use em dashes, but models slip back into
them, so this removes any that get through. It works on the finished text,
so it doesn't depend on the model following the rule.
"""

import re

# Em dash, plus the horizontal bar some models use in its place.
_EM = "—―"
_EN = "–"

# Links are left exactly as they are: a dash inside a URL is part of the address.
_URL = re.compile(r"https?://[^\s<>()\[\]]+")
_MASK_BASE = 0xE000  # private-use characters stand in for links while the text is cleaned

_LINE_START_DASH = re.compile(rf"(?m)^([ \t]*)[{_EM}]+[ \t]*")
_DASH_BEFORE_PUNCTUATION = re.compile(rf"(?m)[ \t]*[{_EM}]+[ \t]*(?=[.,;:!?)\]]|$)")
_ANY_EM_DASH = re.compile(rf"[ \t]*[{_EM}]+[ \t]*")
# A spaced en dash followed by a lowercase word is standing in for an em dash
# ("dry today [en dash] see the sources"). Followed by a number or a capital,
# it's a range ("12°C [en dash] 15°C", "Monday [en dash] Friday") and stays.
_SPACED_EN_DASH_IN_SENTENCE = re.compile(rf"(?<=\S)[ \t]+{_EN}[ \t]+(?=[a-z])")
_DOUBLE_COMMA = re.compile(r",[ \t]*,")
_COMMA_AFTER_BRACKET = re.compile(r"([(\[])[ \t]*,[ \t]*")
_COMMA_AFTER_COLON = re.compile(r":[ \t]*,[ \t]*")
_COMMA_BEFORE_CLOSER = re.compile(r"[ \t]*,[ \t]*([)\]])")


def remove_em_dashes(text: str) -> str:
    """Replace em dashes with commas (or drop them where a comma would be wrong).

    - "Sort of [em dash] but it's complicated." becomes "Sort of, but it's complicated."
    - A dash at the start of a line, or before punctuation, is dropped.
    - A spaced en dash before a lowercase word ("dry [en dash] use") is treated the same.
    - Ranges stay: "10[en dash]20%", "12°C [en dash] 15°C", "Monday [en dash] Friday".
    - Links are never changed.
    """
    if not text:
        return text

    links = []

    def mask(match):
        links.append(match.group(0))
        return chr(_MASK_BASE + len(links) - 1)

    text = _URL.sub(mask, text)
    text = _LINE_START_DASH.sub(r"\1", text)
    text = _DASH_BEFORE_PUNCTUATION.sub("", text)
    text = _ANY_EM_DASH.sub(", ", text)
    text = _SPACED_EN_DASH_IN_SENTENCE.sub(", ", text)
    text = _DOUBLE_COMMA.sub(",", text)
    text = _COMMA_AFTER_BRACKET.sub(r"\1", text)
    text = _COMMA_AFTER_COLON.sub(": ", text)
    text = _COMMA_BEFORE_CLOSER.sub(r"\1", text)
    for i, link in enumerate(links):
        text = text.replace(chr(_MASK_BASE + i), link)
    return text
