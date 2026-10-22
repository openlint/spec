"""What the build enforces beyond the block syntax: fixtures, examples, issues, schema ids, and the comparison across versions."""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path

from .config import BASE_URL, SpecError, published_path, rel_path, schema_file, semver_key
from .model import Version, test_files
from .scan import open_issues
from .schema_tables import load_formats

SCHEMA_ID = re.compile(r'"\$id": "[^"]*"')


def with_id(schema_text: str, url: str) -> str:
    """The schema with its one $id set to url, the rest of the file unchanged."""
    if len(SCHEMA_ID.findall(schema_text)) != 1:
        raise SpecError("the schema needs exactly one $id")
    return SCHEMA_ID.sub(f'"$id": "{url}"', schema_text)


INCLUDE_PATH = re.compile(r"^path:\s*(?P<path>\S+)\s*$")
GENERATED_INCLUDES = {"requirements-index.include", "conformance-tests.include", "formats-table.include", "schema-gaps.include"}


def check_includes(source_dir: Path, source: str) -> list[str]:
    """An include names a file next to the draft or one the build generates, never a path."""
    errors = []
    in_include = False
    for n, line in enumerate(source.split("\n"), start=1):
        if re.match(r"""^<pre class=["']?include["']?>""", line.strip()):
            in_include = True
            continue
        if in_include and line.strip().startswith("</pre>"):
            in_include = False
            continue
        m = INCLUDE_PATH.match(line.strip()) if in_include else None
        if m and ("/" in m.group("path") or "\\" in m.group("path") or (m.group("path") not in GENERATED_INCLUDES and not (source_dir / m.group("path")).is_file())):
            errors.append(f"{rel_path(source_dir, 'index.bs')}:{n}: include {m.group('path')!r} has to be a file next to the draft or one the build generates")
    return errors


def check_schema_id(name: str, source_dir: Path) -> list[str]:
    url = f"{BASE_URL}/{published_path(name)}/ruleset.schema.json"
    found = json.loads(schema_file(source_dir).read_text(encoding="utf-8")).get("$id")
    if found != url:
        return [f"{rel_path(source_dir, 'ruleset.schema.json')}: $id is {found!r}; it has to be {url!r}, the URL the schema is published at"]
    return []


def check_formats(source_dir: Path) -> list[str]:
    """The identifiers in formats.json and the schema's enum are the same set."""
    try:
        listed = {f for family in load_formats(source_dir).values() for f in family}
    except FileNotFoundError:
        return [f"{rel_path(source_dir, 'formats.json')}: file missing"]
    schema = json.loads(schema_file(source_dir).read_text(encoding="utf-8"))
    fmt = schema["$defs"]["Format"]
    enum = set(fmt.get("enum", [])).union(*(alt.get("enum", []) for alt in fmt.get("anyOf", [])))
    errors = []
    for f in sorted(listed - enum):
        errors.append(f"{rel_path(source_dir, 'formats.json')}: {f!r} is not in the schema's format enum")
    for f in sorted(enum - listed):
        errors.append(f"{rel_path(source_dir, 'formats.json')}: the schema lists {f!r}, which formats.json does not")
    return errors


FIXTURE_EXAMPLE = re.compile(r'<div class=example data-fixture="([^"]+)">\n```[a-z]*\n(.*?)\n```\n</div>', re.DOTALL)


def check_fixture_examples(source_dir: Path, source: str) -> list[str]:
    """An example block that names a fixture file shows exactly that file's content."""
    errors = []
    for m in FIXTURE_EXAMPLE.finditer(source):
        path = source_dir / m.group(1)
        if not path.is_file():
            errors.append(f"{rel_path(source_dir, 'index.bs')}: example names fixture {m.group(1)!r}, which does not exist")
        elif path.read_text(encoding="utf-8").rstrip("\n") != m.group(2).rstrip("\n"):
            errors.append(f"{rel_path(source_dir, 'index.bs')}: the example for {m.group(1)} differs from the file; copy the file into the example")
    return errors


ISSUES_INDEX_LINK = re.compile(r"""\[\[#issues-index(?:\|[^\]]*)?\]\]|href=["']?#issues-index\b""")


def check_issues_index(source_dir: Path, source: str) -> list[str]:
    """Bikeshed generates the issues index only while issues remain, so a link to it breaks with the last one."""
    if open_issues(source):
        return []
    errors = []
    in_fence = False
    for n, line in enumerate(source.split("\n"), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and ISSUES_INDEX_LINK.search(line):
            errors.append(f"{rel_path(source_dir, 'index.bs')}:{n}: links to the issues index, but no issue is left, so Bikeshed "
                          "generates no index; rewrite the sentence without the link")
    return errors


UNDERSCORE_EMPHASIS = re.compile(r"(?<![\w/])_(?=\S)[^_]+?(?<=\S)_(?![\w/])")


def check_underscore_emphasis(source_dir: Path, source: str) -> list[str]:
    """Bikeshed reads *text* as emphasis and prints _text_ as it is, underscores included."""
    errors = []
    in_fence = in_pre = False
    for n, line in enumerate(source.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if stripped.startswith("<pre") and "</pre>" not in stripped:
            in_pre = True
        elif in_pre and "</pre>" in stripped:
            in_pre = False
            continue
        if in_fence or in_pre:
            continue
        if UNDERSCORE_EMPHASIS.search(re.sub(r"`[^`]*`", "", line)):
            errors.append(f"{rel_path(source_dir, 'index.bs')}:{n}: _text_ is printed with its underscores; write *text* for emphasis")
    return errors


DISCUSSION = re.compile(r'(?:<a href="https://github\.com/orgs/openlint/discussions/(\d+)">)?discussion #(\d+)\b')


def check_discussion_links(source_dir: Path, source: str) -> list[str]:
    """A discussion is always mentioned as a link, so a reader can follow it from any version."""
    errors = []
    for n, line in enumerate(source.split("\n"), start=1):
        for m in DISCUSSION.finditer(line):
            if m.group(1) != m.group(2):
                errors.append(f"{rel_path(source_dir, 'index.bs')}:{n}: discussion #{m.group(2)} needs a link to "
                              f"https://github.com/orgs/openlint/discussions/{m.group(2)}")
    return errors


def check_across_versions(versions: list[Version]) -> tuple[list[str], list[str]]:
    """Identifiers are permanent, and a change made in one draft is not missed in a later one."""
    drafts = sorted((v for v in versions if v.is_draft), key=lambda v: v.major)
    errors: list[str] = []
    notices: list[str] = []
    for rel in sorted((v for v in versions if not v.is_draft), key=lambda v: semver_key(v.name)):
        for draft in (d for d in drafts if d.major >= rel.major):
            current = {r.id: r for r in draft.requirements}
            for r in rel.requirements:
                d = current.get(r.id)
                if d is None:
                    errors.append(f"{r.id} was released in {rel.name} but is gone from the {draft.name} draft; keep it with data-status=removed data-removed=<version>")
                    continue
                if d.kind != r.kind or d.target != r.target:
                    errors.append(f"{r.id} changed kind or target in the {draft.name} draft since {rel.name}; that is a new requirement with a new identifier")
                if draft.major == rel.major and d.status != "removed" and d.text != r.text:
                    notices.append(f"{r.id}: text differs from {rel.name}; if what conforms changed, give it a new identifier and remove this one")
            if draft.major == rel.major:
                draft_tests = {t.id for t in draft.tests}
                for t in rel.tests:
                    if t.id not in draft_tests:
                        notices.append(f"{t.id}: test released in {rel.name} is gone from the {draft.name} draft")
    for earlier, later in itertools.pairwise(drafts):
        errors.extend(compare_drafts(earlier, later, notices))
    return errors, notices


def compare_drafts(earlier: Version, later: Version, notices: list[str]) -> list[str]:
    """The next draft lists every requirement of this one: removed stays removed, and current is the same unless removed there."""
    errors = []
    later_reqs = {r.id: r for r in later.requirements}
    here = rel_path(earlier.source_dir, "index.bs")
    there = rel_path(later.source_dir, "index.bs")
    for r in earlier.requirements:
        s = later_reqs.get(r.id)
        if s is None:
            errors.append(f"{here}:{r.line}: {r.id} is missing from the {later.name} draft; add it there too, "
                          f"or list it there with data-status=removed data-removed=<version>")
        elif s.status == "removed":
            continue
        elif r.status == "removed":
            errors.append(f"{there}:{s.line}: {r.id} is removed in the {earlier.name} draft but current in {later.name}; "
                          f"a removed requirement stays removed in every later draft")
        elif (r.kind, r.klass, r.status) != (s.kind, s.klass, s.status) or " ".join(r.body.split()) != " ".join(s.body.split()):
            errors.append(f"{here}:{r.line} and {there}:{s.line}: {r.id} differs between the {earlier.name} and {later.name} drafts; "
                          f"make the same change in both, or give the {later.major}.x requirement a new identifier and remove this one there")
    later_tests = {t.id: t for t in later.tests}
    for t in earlier.tests:
        u = later_tests.get(t.id)
        if u is None:
            notices.append(f"{t.id}: test in the {earlier.name} draft is not in {later.name}")
        elif test_files(t) != test_files(u):
            notices.append(f"{t.id}: test differs between the {earlier.name} and {later.name} drafts")
    return errors
