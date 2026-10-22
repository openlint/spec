"""The things a version of the specification is made of: classes, requirements, tests, and the version itself."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import DRAFT_NAME, published_path

TARGETS = ("ruleset", "linter")


STATUSES = ("", "proposed", "removed", "example")


KIND_NAME = {"req": "requirement", "rec": "recommendation", "per": "permission"}


KIND_WORDS = {
    "req": ("MUST NOT", "MUST", "SHALL NOT", "SHALL", "REQUIRED"),
    "rec": ("SHOULD NOT", "SHOULD", "NOT RECOMMENDED", "RECOMMENDED"),
    "per": ("MAY", "OPTIONAL"),
}


@dataclass
class ConformanceClass:
    name: str
    id: str
    target: str
    depends: list[str]
    line: int
    text: str
    end_line: int = 0
    members: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)


@dataclass
class Requirement:
    id: str
    kind: str
    klass: str
    target: str
    since: str
    removed: str
    status: str
    section_id: str
    section_title: str
    line: int
    text: str
    body: str = ""
    end_line: int = 0
    tests: list[str] = field(default_factory=list)


@dataclass
class Test:
    id: str
    covers: list[str]
    purpose: str
    ruleset: str
    document: str | None
    files: list[str]
    expect: dict
    dir: Path
    klass: str = ""
    target: str = ""

    @property
    def section(self) -> str:
        return self.id.split("/")[2]

    @property
    def name(self) -> str:
        return self.id.split("/")[3]


@dataclass
class Version:
    name: str
    source_dir: Path
    metadata: dict[str, str]
    classes: list[ConformanceClass]
    requirements: list[Requirement]
    tests: list[Test]
    expanded: str

    @property
    def is_draft(self) -> bool:
        return DRAFT_NAME.fullmatch(self.name) is not None

    @property
    def major(self) -> int:
        """The major version: a draft's number, or a release's first number."""
        return int(self.name[1:]) if self.is_draft else int(self.name.split(".")[0])

    @property
    def site_path(self) -> str:
        return published_path(self.name)

    @property
    def title(self) -> str:
        return self.metadata.get("Title", self.name)

    @property
    def label(self) -> str:
        macro = self.metadata.get("Text Macro", "")
        return macro.split(" ", 1)[1] if macro.startswith("VERSIONLABEL ") else self.name


GROUP_ABOVE = 10


def grouped(test_ids: list[str]) -> bool:
    """Whether a requirement's tests are shown by section: a list too long to scan that spans several sections."""
    return len(test_ids) > GROUP_ABOVE and len({tid.split("/")[2] for tid in test_ids}) > 1


def test_groups(test_ids: list[str], tests: dict[str, Test]) -> list[tuple[str, str]]:
    """Each test with the heading to show before it, which is its section when the tests are grouped."""
    is_grouped = grouped(test_ids)
    out, previous = [], None
    for tid in test_ids:
        section = tests[tid].section
        out.append((tid, f"/conf/{section}/" if is_grouped and section != previous else ""))
        previous = section
    return out


def expect_kind(test: Test) -> str:
    """valid, invalid, rejected, results (at least one), or empty."""
    e = test.expect
    if "ruleset" in e:
        return e["ruleset"]
    if e.get("rejected"):
        return "rejected"
    return "results" if e.get("results") else "empty"


def test_files(test: Test) -> dict[str, bytes]:
    return {str(p.relative_to(test.dir)): p.read_bytes() for p in sorted(test.dir.rglob("*")) if p.is_file()}
