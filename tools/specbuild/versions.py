"""Finding the versions in the repository and parsing one into its checked, expanded form.

parse_version runs these steps in order and raises SpecError with every problem found:

  1. scan_source: read the Bikeshed source line by line, find the blocks, the headings, and the
     text-level problems (keywords outside blocks, implementation names, nesting).
  2. classify_blocks: turn each block into a ConformanceClass or a Requirement, checking its id,
     status, and keywords.
  3. link_classes: resolve class dependencies and give each requirement its class and target.
  4. attach_tests: read the conformance tests and connect them to the requirements they cover.
  5. check_test_adequacy and check_part_targets: the test rules and the one-target-per-part rule.
  6. expand: add the generated headers and test lists to the source for Bikeshed.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .checks import (
    check_discussion_links,
    check_fixture_examples,
    check_formats,
    check_includes,
    check_issues_index,
    check_schema_id,
    check_underscore_emphasis,
)
from .config import DRAFT_NAME, RELEASES, ROOT, SpecError, rel_path, schema_file
from .fixtures import load_tests
from .model import KIND_NAME, KIND_WORDS, STATUSES, TARGETS, ConformanceClass, Requirement, Test, Version, expect_kind, grouped, test_groups
from .render import STYLE, class_head, class_members, link, outcome_badge, req_head, source_text
from .scan import (
    BLOCK_ID,
    HTML_HEADING,
    ISSUE_DIV,
    ISSUE_PARAGRAPH,
    KEYWORDS,
    MD_HEADING,
    MENTION,
    MENTION_ALLOWED_SECTIONS,
    METADATA_OPEN,
    OPEN_TAG,
    PART_TARGETS,
    bid_of,
    parse_attrs,
    read_metadata,
    strip_markup,
)
from .schema_tables import SCHEMA_TABLE, schema_table

OUTCOME_RANK = {"valid": 0, "results": 0, "empty": 1, "invalid": 1, "rejected": 2}


@dataclass
class Block:
    """One <div class=req|rec|per|class> in the source, with the section it sits in."""

    kind: str
    attrs: dict[str, str]
    start: int
    end: int
    body: str
    section_id: str
    section_title: str


@dataclass
class Scan:
    """What one pass over the source finds."""

    out: list[str] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    part_of_section: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def scan_source(lines: list[str], schema: dict, err) -> Scan:
    """One pass over the source: blocks, headings and parts, keyword emphasis, schema tables, and the line-level checks.

    out has exactly one entry per source line, so later steps can address lines by number.
    """
    scan = Scan()
    section_id, section_title, part = "", "", ""
    block: Block | None = None
    body: list[str] = []
    in_fence = in_pre = in_metadata = False
    in_issue: str | None = None

    for n, line in enumerate(lines, start=1):
        stripped = line.strip()
        if METADATA_OPEN.match(stripped):
            in_metadata = True
        elif in_metadata and stripped.startswith("</pre>"):
            in_metadata = False
            scan.out.append(line)
            continue
        if stripped.startswith("```"):
            in_fence = not in_fence
        if stripped.startswith("<pre") and not METADATA_OPEN.match(stripped) and "</pre>" not in stripped:
            in_pre = True
        elif in_pre and "</pre>" in stripped:
            in_pre = False
            scan.out.append(line)
            continue
        in_text = not (in_fence or in_pre or in_metadata)

        heading = MD_HEADING.match(line) or HTML_HEADING.match(line)
        if heading and in_text:
            section_id, section_title = heading.group("id"), strip_markup(heading.group("text"))
            if MD_HEADING.match(line):
                if heading.group(1) == "#":
                    part = section_id
                scan.part_of_section[section_id] = part

        table = SCHEMA_TABLE.match(line)
        if table and block is None and in_text:
            rendered, problems = schema_table(schema, table.group("def"))
            for problem in problems:
                err(n, problem)
            scan.out.append(rendered)
            continue

        opened = OPEN_TAG.match(line)
        if opened and block is None:
            block = Block(kind=opened.group("class"), attrs=parse_attrs(opened.group("attrs")), start=n, end=0, body="",
                          section_id=section_id, section_title=section_title)
            body = []
            scan.out.append(line)
            continue
        if block is not None:
            if MENTION.search(line):
                err(n, f"names an implementation inside {bid_of(block.attrs)}; requirements state the rule itself")
            if stripped == "</div>":
                scan.out.append(line)
                block.end, block.body = n, "\n".join(body)
                scan.blocks.append(block)
                block = None
                continue
            if opened:
                err(n, f"<div class={opened.group('class')}> opened inside another block; blocks do not nest")
            body.append(line)
            if block.kind in KIND_NAME:
                line = KEYWORDS.sub(r'<em class="rfc2119">\1</em>', line)
            scan.out.append(line)
            continue

        if in_text:
            if ISSUE_PARAGRAPH.match(line):
                in_issue = "paragraph"
            elif ISSUE_DIV.match(line):
                in_issue = "div"
            elif in_issue == "paragraph" and not stripped:
                in_issue = None
        if in_text and KEYWORDS.search(line):
            err(n, f"BCP 14 keyword outside an identified requirement: {stripped[:80]!r}")
        if in_text and MENTION.search(line) and in_issue is None and section_id not in MENTION_ALLOWED_SECTIONS:
            err(n, f"names an implementation outside an issue: {stripped[:80]!r}")
        if in_issue == "div" and stripped == "</div>":
            in_issue = None
        scan.out.append(line)

    if block is not None:
        err(block.start, f"<div class={block.kind}> is never closed")
    return scan


def classify_blocks(blocks: list[Block], err) -> tuple[list[ConformanceClass], list[Requirement]]:
    """Each block becomes a class or a requirement, after its id, status, and keywords are checked."""
    classes: list[ConformanceClass] = []
    requirements: list[Requirement] = []
    for b in blocks:
        text = strip_markup(b.body)
        bid = b.attrs.get("id", "")
        if b.kind == "class":
            if not BLOCK_ID["class"].match(bid):
                err(b.start, f"class id {bid!r} is not of the form /conf/<name>")
            target = b.attrs.get("data-target", "")
            if target not in TARGETS:
                err(b.start, f"class {bid} needs data-target=ruleset or data-target=linter, got {target!r}")
            classes.append(ConformanceClass(name=bid.rsplit("/", 1)[-1], id=bid, target=target, depends=b.attrs.get("data-depends", "").split(),
                                            line=b.start, text=text, end_line=b.end))
        elif b.kind in KIND_NAME:
            status = b.attrs.get("data-status", "")
            if not BLOCK_ID[b.kind].match(bid):
                err(b.start, f"{KIND_NAME[b.kind]} id {bid!r} is not of the form /{b.kind}/<topic>/<name>")
            if status not in STATUSES:
                err(b.start, f"{bid} has unknown data-status {status!r}")
            words = KEYWORDS.findall(b.body)
            if status == "removed" and not b.attrs.get("data-removed"):
                err(b.start, f"{bid} is removed but has no data-removed=<version>")
            if status != "removed":
                if not any(w in KIND_WORDS[b.kind] for w in words):
                    err(b.start, f"{KIND_NAME[b.kind]} {bid} contains none of {', '.join(KIND_WORDS[b.kind])}")
                wrong = sorted({w for w in words if w not in KIND_WORDS[b.kind]})
                if wrong:
                    err(b.start, f"{KIND_NAME[b.kind]} {bid} uses {', '.join(wrong)}, which belong to another kind of block")
            requirements.append(Requirement(
                id=bid, kind=b.kind, klass=b.attrs.get("data-class", ""), target="",
                since=b.attrs.get("data-since", ""), removed=b.attrs.get("data-removed", ""), status=status,
                section_id=b.section_id, section_title=b.section_title, line=b.start, text=text, body=b.body, end_line=b.end,
            ))
    return classes, requirements


def link_classes(classes: list[ConformanceClass], requirements: list[Requirement], err) -> tuple[dict[str, ConformanceClass], dict[str, Requirement]]:
    """Classes depend on declared classes, and each requirement takes its target from its class."""
    class_by_name: dict[str, ConformanceClass] = {}
    for c in classes:
        if c.name in class_by_name:
            err(c.line, f"duplicate class {c.id} (first at line {class_by_name[c.name].line})")
        class_by_name[c.name] = c
    for c in classes:
        for d in c.depends:
            if d not in class_by_name:
                err(c.line, f"class {c.id} depends on {d!r}, which is not declared")
            elif d == c.name:
                err(c.line, f"class {c.id} depends on itself")
    by_id: dict[str, Requirement] = {}
    for req in requirements:
        if req.id in by_id:
            err(req.line, f"duplicate id {req.id} (first at line {by_id[req.id].line})")
        by_id[req.id] = req
        if req.status == "example":
            req.target = "ruleset"
            continue
        if req.klass not in class_by_name:
            err(req.line, f"{req.id} needs data-class naming a declared class, got {req.klass!r}")
            continue
        req.target = class_by_name[req.klass].target
        class_by_name[req.klass].members.append(req.id)
    return class_by_name, by_id


def attach_tests(tests: list[Test], by_id: dict[str, Requirement], class_by_name: dict[str, ConformanceClass],
                 source_dir: Path, errors: list[str]) -> dict[str, Test]:
    """Each test joins the requirements it covers, which all belong to one class, and the class fixes what it may expect."""
    seen: dict[str, Test] = {}
    for test in tests:
        loc = rel_path(source_dir, f"conformance{test.id[len('/conf'):]}/test.json")
        seen[test.id] = test
        klasses = set()
        for rid in test.covers:
            req = by_id.get(rid)
            if req is None or req.status == "example":
                errors.append(f"{loc}: covers {rid}, which is not defined")
                continue
            if req.kind == "rec":
                errors.append(f"{loc}: covers {rid}, which is a recommendation; a SHOULD cannot be failed, so it has no conformance test")
                continue
            req.tests.append(test.id)
            klasses.add(req.klass)
        if len(klasses) > 1:
            errors.append(f"{loc}: covers requirements from several classes ({', '.join(sorted(klasses))}); a test belongs to one class")
        elif klasses:
            test.klass = klasses.pop()
            test.target = class_by_name[test.klass].target
            class_by_name[test.klass].tests.append(test.id)
            if test.target == "ruleset" and set(test.expect) != {"ruleset"}:
                errors.append(f"{loc}: a test for a ruleset requirement expects {{\"ruleset\": \"valid\" | \"invalid\"}}")
            if test.target == "linter" and "ruleset" in test.expect:
                errors.append(f"{loc}: a test for a linter requirement expects results or rejection, not ruleset validity")
    for req in by_id.values():
        by_section = grouped(req.tests)
        req.tests.sort(key=lambda tid: (seen[tid].section if by_section else "", OUTCOME_RANK.get(expect_kind(seen[tid]), 3), tid))
    return seen


def check_test_adequacy(requirements: list[Requirement], seen: dict[str, Test], err) -> None:
    """The test rules: a ruleset requirement has a valid and an invalid test, a linter requirement one that expects results, a permission one that accepts."""
    for req in requirements:
        if req.kind == "rec" or req.status in ("removed", "example"):
            continue
        if not req.tests:
            err(req.line, f"{KIND_NAME[req.kind]} {req.id} has no conformance test")
            continue
        kinds = {expect_kind(seen[t]) for t in req.tests}
        if req.kind == "per":
            if not kinds & {"valid", "results"}:
                err(req.line, f"permission {req.id} needs a test that shows the permitted thing is accepted: a valid fixture, or results")
            continue
        if req.target == "ruleset":
            for needed in ("valid", "invalid"):
                if needed not in kinds:
                    err(req.line, f"requirement {req.id} has no {needed} test; a ruleset requirement needs one of each")
        elif "results" not in kinds:
            err(req.line, f"requirement {req.id} has only tests that expect nothing; a linter requirement needs a test that expects results")


def check_part_targets(requirements: list[Requirement], part_of_section: dict[str, str], err) -> None:
    """A part of the document holds requirements of one target."""
    for req in requirements:
        if req.status == "example":
            continue
        expected = PART_TARGETS.get(part_of_section.get(req.section_id, ""))
        if expected and req.target and req.target != expected:
            err(req.line, f"{req.id} has target {req.target} but sits in part {part_of_section[req.section_id]!r}, which holds {expected} requirements only")


def expand(out: list[str], classes: list[ConformanceClass], requirements: list[Requirement], by_id: dict[str, Requirement], seen: dict[str, Test]) -> str:
    """The source with the generated headers, member counts, test lists, and stylesheet, for Bikeshed."""
    for c in classes:
        out[c.line - 1] = out[c.line - 1] + class_head(c)
        out[c.end_line - 1] = class_members(c, by_id) + "\n" + out[c.end_line - 1]
    for req in requirements:
        out[req.line - 1] = out[req.line - 1] + req_head(req)
        if req.tests:
            rows = []
            for tid, group in test_groups(req.tests, seen):
                if group:
                    rows.append(f'<tr class="test-group"><th colspan="3">{html.escape(group)}</th></tr>')
                rows.append(f'<tr><td>{link(tid, css="test-id")}</td><td class="test-purpose">{source_text(seen[tid].purpose)}</td>'
                            f'<td>{outcome_badge(seen[tid])}</td></tr>')
            n_tests = len(req.tests)
            out[req.end_line - 1] = (f'<details class="req-tests"><summary>{n_tests} test{"s" if n_tests != 1 else ""}</summary>'
                                     f'<table>{"".join(rows)}</table></details>\n' + out[req.end_line - 1])
    metadata_end = next(i for i, line in enumerate(out) if line.startswith("</pre>"))
    out.insert(metadata_end + 1, "\n" + STYLE)
    return "\n".join(out)


def parse_version(name: str, source_dir: Path) -> Version:
    """Read index.bs and conformance/, run every check, and return the version with its expanded source."""
    source = (source_dir / "index.bs").read_text(encoding="utf-8")
    lines = source.split("\n")
    metadata = read_metadata(lines)
    try:
        schema = json.loads(schema_file(source_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SpecError(f"{rel_path(source_dir, 'ruleset.schema.json')}: {e}") from e
    errors: list[str] = []

    def err(line_no: int, message: str) -> None:
        errors.append(f"{rel_path(source_dir, 'index.bs')}:{line_no}: {message}")

    scan = scan_source(lines, schema, err)
    classes, requirements = classify_blocks(scan.blocks, err)
    class_by_name, by_id = link_classes(classes, requirements, err)
    tests, test_errors = load_tests(source_dir)
    errors.extend(test_errors)
    for check in (check_formats, lambda d: check_schema_id(name, d)):
        errors.extend(check(source_dir))
    for check in (check_fixture_examples, check_issues_index, check_underscore_emphasis, check_discussion_links, check_includes):
        errors.extend(check(source_dir, source))
    seen = attach_tests(tests, by_id, class_by_name, source_dir, errors)
    check_test_adequacy(requirements, seen, err)
    check_part_targets(requirements, scan.part_of_section, err)
    if errors:
        raise SpecError("\n".join(errors))
    return Version(
        name=name, source_dir=source_dir, metadata=metadata, classes=classes,
        requirements=[r for r in requirements if r.status != "example"],
        tests=tests, expanded=expand(scan.out, classes, requirements, by_id, seen),
    )


def discover_versions(only: str | None) -> list[tuple[str, Path]]:
    found = []
    drafts = [p.parent for p in ROOT.glob("v*/index.bs") if DRAFT_NAME.fullmatch(p.parent.name)]
    for path in sorted(drafts, key=lambda p: int(p.name[1:])):
        if only in (None, path.name):
            found.append((path.name, path))
    if RELEASES.is_dir():
        for path in sorted(RELEASES.iterdir()):
            if (path / "index.bs").exists() and re.fullmatch(r"\d+\.\d+\.\d+", path.name) and only in (None, path.name):
                found.append((path.name, path))
    if not found:
        raise SpecError(f"no version named {only!r}" if only else "no versions found")
    return found
