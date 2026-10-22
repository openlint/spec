#!/usr/bin/env python3
"""Cut an immutable release from the working draft of its major version.

Usage:
  tools/release.py 1.0.0

A release is cut from the draft of its major version: 1.1.0 from v1/, 2.0.0
from v2/. What it does, in order:

  1. Runs every check of the build, Bikeshed and the comparison across
     versions included. Refuses when any requirement is still marked
     data-status=proposed, or when any Issue block remains: a release carries only settled requirements and answered
     questions. An issue that is an accepted limitation becomes a Note first.
     Once the last issue is gone, the draft can no longer link to the issues
     index, which Bikeshed generates only while issues remain.
  2. Stamps data-since="<version>" on every requirement in v<major>/index.bs
     that has no data-since yet, and on the same requirements in every later
     draft. The stamp stays in the drafts: from now on those requirements are
     "since <version>" everywhere.
  3. Snapshots index.bs, the includes, formats.json, conformance/, and the
     schema into releases/<version>/ and rewrites the copy's metadata so that it
     describes itself as that release: label, fixed date, its own URL, no
     working-draft warning, and a pointer to the draft. The schema's $id
     becomes the release's URL.
  4. Points "Previous Version" and "Latest release" at the new release, in the
     draft of its major version and in every later draft whose major version has no release yet.

The release directory is never edited again. A fix becomes a new patch release.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specbuild.checks import check_across_versions, with_id
from specbuild.config import BASE_URL, RELEASES, ROOT, SpecError
from specbuild.scan import METADATA_OPEN, open_issues, parse_attrs
from specbuild.site import build_version
from specbuild.versions import discover_versions, parse_version

REQ_OPEN = re.compile(r'^(\s*<div\s+class=(?:req|rec|per)\b)(?P<attrs>[^>]*)>\s*$')


def stamp_since(source: str, version: str, only: set[str] | None = None) -> tuple[str, set[str]]:
    """Stamp every settled requirement, recommendation, and permission that has no data-since yet, or only those named."""
    stamped = set()
    out = []
    for line in source.split("\n"):
        m = REQ_OPEN.match(line)
        attrs = parse_attrs(m.group("attrs")) if m else {}
        bid = attrs.get("id", "")
        if (m and "data-since" not in attrs and attrs.get("data-status") not in ("example", "proposed")
                and (only is None or bid in only)):
            line = f'{m.group(1)}{m.group("attrs")} data-since="{version}">'
            stamped.add(bid)
        out.append(line)
    return "\n".join(out), stamped


def edit_metadata(source: str, set_keys: dict[str, str], drop_keys: set[str]) -> str:
    """Rewrite the metadata block: replace or append set_keys, remove drop_keys."""
    lines = source.split("\n")
    start = next((i for i, l in enumerate(lines) if METADATA_OPEN.match(l)), None)
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("</pre>")), None) if start is not None else None
    if end is None:
        raise SpecError("index.bs has no complete <pre class='metadata'> block")
    block = lines[start + 1:end]
    seen = set()
    new_block = []
    for line in block:
        key = line.split(":", 1)[0].strip()
        if key in drop_keys:
            continue
        if key in set_keys:
            new_block.append(f"{key}: {set_keys[key]}")
            seen.add(key)
        else:
            new_block.append(line)
    for key, value in set_keys.items():
        if key not in seen:
            new_block.append(f"{key}: {value}")
    return "\n".join(lines[: start + 1] + new_block + lines[end:])


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not re.fullmatch(r"\d+\.\d+\.\d+", argv[0]):
        print(__doc__, file=sys.stderr)
        return 2
    version = argv[0]
    line = int(version.split(".")[0])
    draft_dir = ROOT / f"v{line}"
    release_dir = RELEASES / version
    if not (draft_dir / "index.bs").is_file():
        print(f"error: there is no working draft of {line}.x in v{line}/", file=sys.stderr)
        return 1
    if release_dir.exists():
        print(f"error: releases/{version}/ already exists. Releases are immutable; cut a new version instead.", file=sys.stderr)
        return 1
    try:
        versions = [parse_version(name, path) for name, path in discover_versions(None)]
        draft = next(v for v in versions if v.name == f"v{line}")
        cross, notices = check_across_versions(versions)
        for n in notices:
            print(f"notice: {n}")
        if cross:
            raise SpecError("\n".join(cross))
        with tempfile.TemporaryDirectory() as scratch:
            build_version(draft, site=Path(scratch) / "site", build=Path(scratch) / "build")
    except SpecError as e:
        print(f"error: the draft does not pass its checks:\n{e}", file=sys.stderr)
        return 1
    proposed = [r.id for r in draft.requirements if r.status == "proposed"]
    if proposed:
        print("error: a release cannot carry proposed requirements. Settle or remove:", file=sys.stderr)
        for rid in proposed:
            print(f"  {rid}", file=sys.stderr)
    issues = open_issues((draft_dir / "index.bs").read_text(encoding="utf-8"))
    if issues:
        print("error: a release cannot carry open issues. Resolve each in the text, or demote it to a note that states the accepted limitation:", file=sys.stderr)
        for line_no, text in issues:
            print(f"  v{line}/index.bs:{line_no}: {text[:90]}", file=sys.stderr)
    if proposed or issues:
        return 1

    today = date.today().isoformat()
    draft_source = (draft_dir / "index.bs").read_text(encoding="utf-8")
    draft_source, stamped = stamp_since(draft_source, version)
    pointers = {
        "Previous Version": f"{BASE_URL}/{version}/",
        "!Latest release": f'<a href="{BASE_URL}/{version}/">{BASE_URL}/{version}/</a>',
    }
    try:
        schema_text = with_id((draft_dir / "ruleset.schema.json").read_text(encoding="utf-8"), f"{BASE_URL}/{version}/ruleset.schema.json")
        release_source = edit_metadata(
            draft_source,
            set_keys={
                "Text Macro": f"VERSIONLABEL Release {version}",
                "Date": today,
                "ED": f"{BASE_URL}/{version}/",
                "Logo": "../assets/openlint-icon.svg",
                "Favicon": "../assets/openlint-icon.svg",
                "!Working draft": f'<a href="{BASE_URL}/v{line}/draft/">{BASE_URL}/v{line}/draft/</a>',
            },
            drop_keys={"Warning", "Custom Warning Title", "Custom Warning Text", "!Latest release"},
        )
        drafts = {draft_dir: edit_metadata(draft_source, pointers, set())}
        pointed = [f"v{line}"]
        released_lines = {v.major for v in versions if not v.is_draft}
        for name, later_dir in discover_versions(None):
            later = re.fullmatch(r"v(\d+)", name)
            if not later or int(later.group(1)) <= line:
                continue
            source, _ = stamp_since((later_dir / "index.bs").read_text(encoding="utf-8"), version, only=stamped)
            if not any(line < n <= int(later.group(1)) for n in released_lines):
                source = edit_metadata(source, pointers, set())
                pointed.append(name)
            drafts[later_dir] = source
    except SpecError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    # The release is assembled next to its final place and moved there whole, so a failure leaves nothing behind.
    RELEASES.mkdir(exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=RELEASES))
    try:
        for include in draft_dir.glob("*.include"):
            shutil.copy(include, staging / include.name)
        shutil.copy(draft_dir / "formats.json", staging / "formats.json")
        shutil.copytree(draft_dir / "conformance", staging / "conformance")
        (staging / "ruleset.schema.json").write_text(schema_text, encoding="utf-8")
        (staging / "index.bs").write_text(release_source, encoding="utf-8")
        staging.rename(release_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    for path, source in drafts.items():
        (path / "index.bs").write_text(source, encoding="utf-8")

    print(f"released releases/{version}/ from v{line}/ ({len(stamped)} requirements stamped since {version}, dated {today})")
    print(f"listed as Previous Version and Latest release in: {', '.join(pointed)}")
    print("next: tools/build.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
