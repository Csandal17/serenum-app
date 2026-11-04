"""tools.is_trusted_url: only real pages on the trusted domains count.

Includes the bypass an independent review found on 4 Nov 2026: Python's
URL parser reads "https://evil.com\\@www.nhs.uk" as nhs.uk, but browsers
and requests go to evil.com.
"""

import pytest

import tools

TRUSTED = ["nhs.uk", "nice.org.uk", "bad.org.uk", "skinhealthinfo.org.uk"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.nhs.uk/conditions/eczema/",
        "https://nhs.uk/conditions/eczema/",
        "https://bnf.nice.org.uk/drugs/aciclovir/",
        "https://www.skinhealthinfo.org.uk/condition/rosacea/",
        "https://WWW.NHS.UK/conditions/acne/",
        "https://www.nhs.uk./conditions/acne/",
        "https://www.nhs.uk:443/conditions/acne/",
        "https://www.nhs.uk/search?q=sun%20safety",
    ],
)
def test_trusted(url):
    assert tools.is_trusted_url(url, TRUSTED)


@pytest.mark.parametrize(
    "url",
    [
        # Look-alike hosts
        "https://notnhs.uk/page",
        "https://nhs.uk.example.com/page",
        "https://example.com/?next=https://www.nhs.uk/",
        # Parser differentials: Python and browsers disagree on the host
        "https://evil.com\\@www.nhs.uk/x",
        "https://evil.com\\.www.nhs.uk/x",
        "https://evil.com@www.nhs.uk/x",
        "https://user:pass@www.nhs.uk/x",
        "https://www.nhs.uk%2eevil.com/x",
        "https://evil.com%2fwww.nhs.uk/x",
        "https://www.nhs.uk :443/x",
        "https://www.nhs.uk/\nhttps://evil.com",
        "https://www.nhs.uk\t/x",
        "https://www.nhs.uk:99999/x",
        "https://www.nhs.uk:abc/x",
        "https://www.нhs.uk/x",  # Cyrillic "н"
        # Not web pages
        "ftp://www.nhs.uk/file",
        "javascript://www.nhs.uk/%0aalert(1)",
        "//www.nhs.uk/x",
        "not a url",
        "",
        None,
    ],
)
def test_not_trusted(url):
    assert not tools.is_trusted_url(url, TRUSTED)
