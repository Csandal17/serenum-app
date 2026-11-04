"""The trusted sources Sērēnum's evidence search is limited to.

This is the one place the list lives for the Chainlit app. Subdomains
count, so www.nhs.uk and bnf.nice.org.uk are included. tools.py checks
every search result against this list, so a page from anywhere else is
never returned.

(The MCP server on the mcp-server branch has its own copy of this list
in serenum_mcp.py. Once both branches are merged, it should import this
one instead, so the two can't drift apart.)
"""

TRUSTED_DOMAINS = [
    "nhs.uk",  # NHS
    "nice.org.uk",  # NICE, including the BNF and CKS
    "bad.org.uk",  # British Association of Dermatologists
    "skinhealthinfo.org.uk",  # the BAD's patient information site
]
