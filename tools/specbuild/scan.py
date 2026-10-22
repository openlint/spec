"""Reading the Bikeshed source: the block and heading syntax, metadata, and the text patterns the checks look for."""

from __future__ import annotations

import re

METADATA_OPEN = re.compile(r"""^\s*<pre class=(['"])metadata\1>""")


ISSUE_PARAGRAPH = re.compile(r"^\s*Issue(\([^)]*\))?:")


ISSUE_DIV = re.compile(r"""^\s*<div\s+class=["']?issue\b""")


SEGMENT = r"[a-z0-9]+(?:-[a-z0-9]+)*"


BLOCK_ID = {
    "req": re.compile(rf"^/req(/{SEGMENT}){{2,}}$"),
    "rec": re.compile(rf"^/rec(/{SEGMENT}){{2,}}$"),
    "per": re.compile(rf"^/per(/{SEGMENT}){{2,}}$"),
    "class": re.compile(rf"^/conf/{SEGMENT}$"),
}


TEST_ID = re.compile(rf"^/conf(/{SEGMENT}){{2}}$")


PART_TARGETS = {"documents": "linter", "ruleset-format": "ruleset", "linting": "linter", "functions": "linter"}


KEYWORDS = re.compile(
    r"\b(MUST NOT|MUST|REQUIRED|SHALL NOT|SHALL|SHOULD NOT|SHOULD|"
    r"NOT RECOMMENDED|RECOMMENDED|MAY|OPTIONAL)\b"
)


OPEN_TAG = re.compile(r"^\s*<div\s+class=(?P<class>req|rec|per|class|bcp14)\b(?P<attrs>[^>]*)>\s*$")


ATTR = re.compile(r"""(?P<name>[\w-]+)=(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>[^\s>]+))""")


MD_HEADING = re.compile(r"^(#{1,6})\s+(?P<text>.*?)\s+#*\s*\{#(?P<id>[^}\s]+)[^}]*\}\s*$")


HTML_HEADING = re.compile(r"""^\s*<h[1-6][^>]*\bid=["']?(?P<id>[^"'\s>]+)["']?[^>]*>(?P<text>.*?)</h[1-6]>""")


METADATA_KEY = re.compile(r"^(?P<key>[^:]+):\s*(?P<value>.*)$")


# The specification states its rules as its own. Implementations are named only in issues, which a
# release does not carry, and in the provenance appendix.
# OpenLint the project (its community, maintainers, and the name of this specification) is not a mention of the linter.
MENTION = re.compile(r"\bSpectral\b|\bOpenLint\b(?! (?:community|maintainers|Ruleset))|\[\[!?(?:SPECTRAL|OPENLINT)\]\]|[Rr]eference implementation")


MENTION_ALLOWED_SECTIONS = {"provenance"}


def bid_of(attrs: dict[str, str]) -> str:
    return attrs.get("id", "a block")


def parse_attrs(raw: str) -> dict[str, str]:
    return {
        m.group("name"): m.group("dq") or m.group("sq") or m.group("bare") or ""
        for m in ATTR.finditer(raw)
    }


def strip_markup(text: str) -> str:
    text = re.sub(r"\[=(?:[^=|]*\|)?([^=]+)=\]", r"\1", text)
    text = re.sub(r"\[\[!?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("`", "")
    return " ".join(text.split())


def read_metadata(lines: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    inside = False
    for line in lines:
        if METADATA_OPEN.match(line):
            inside = True
            continue
        if inside and line.startswith("</pre>"):
            break
        if inside:
            m = METADATA_KEY.match(line)
            if m:
                metadata[m.group("key").strip()] = m.group("value").strip()
    return metadata


def open_issues(source: str) -> list[tuple[int, str]]:
    """Every Issue block in the document, outside code fences."""
    found = []
    in_fence = False
    for n, line in enumerate(source.split("\n"), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and (ISSUE_PARAGRAPH.match(line) or ISSUE_DIV.match(line)):
            found.append((n, line.strip()))
    return found
