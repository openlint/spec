"""Where the sources and the output live, and the error every check raises."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


SITE = ROOT / "site"


BUILD = ROOT / ".build"


RELEASES = ROOT / "releases"


BASE_URL = "https://spec.openlint.org"


DRAFT_NAME = re.compile(r"v([1-9][0-9]*)")


SCHEMA_REQUIREMENT = "/req/ruleset/schema"


BIKESHED = shutil.which("bikeshed") or next((str(p) for p in (ROOT / ".venv/bin/bikeshed", Path.home() / ".local/bin/bikeshed") if p.exists()), "bikeshed")


def rel_path(source_dir: Path, name: str) -> str:
    """A path for messages: relative to the repository root when the source is under it, as given otherwise."""
    try:
        rel = source_dir.relative_to(ROOT)
    except ValueError:
        return str(source_dir / name)
    return name if str(rel) == "." else f"{rel}/{name}"


def schema_file(source_dir: Path) -> Path:
    return source_dir / "ruleset.schema.json"


def published_path(name: str) -> str:
    """Where a version is published, relative to the site root: v1/draft for a draft, 1.0.0 for a release."""
    return f"{name}/draft" if DRAFT_NAME.fullmatch(name) else name


class SpecError(Exception):
    pass


REGISTRY_SCHEMA = ROOT / "schema" / "registry.schema.json"


def semver_key(name: str) -> tuple:
    return tuple(int(p) for p in name.split("."))
