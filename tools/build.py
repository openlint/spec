#!/usr/bin/env python3
"""Build every version of the specification into site/.

Usage:
  tools/build.py            build all versions
  tools/build.py v1         build one version: a draft (v1) or a release (1.0.0)
  tools/build.py --check    run every check, Bikeshed included, and write nothing

Each major version has a working draft in v<major>/: index.bs, its boilerplate
includes, formats.json, the ruleset schema as ruleset.schema.json, and a
conformance/ directory with one test per subdirectory. A release is a snapshot
of those under releases/<semver>/. A draft is published at /v<major>/draft/, a
release at /<semver>/. /v<major>/ is a copy of the latest release of that major
version; until it has one, /v<major>/ruleset.schema.json is the draft's schema.

The document declares conformance classes, requirements, recommendations, and
permissions as blocks:

  <div class=class id="/conf/linter-core" data-target=linter data-depends="ruleset-core">
  <div class=req id="/req/given/no-match" data-class=linter-core>
  <div class=rec id="/rec/then/prefer-core-functions" data-class=ruleset-core>
  <div class=per id="/per/ruleset/extension-properties" data-class=ruleset-core>

Tests are data: conformance/<topic>/<name>/test.json names the requirements
it covers, a purpose, fixture files, and the expected outcome.

Before Bikeshed runs, this script enforces what a document can check
mechanically:

  * every block has a permanent, well-formed ID
  * every requirement belongs to one conformance class, which has one target
  * a requirement uses MUST, a recommendation SHOULD, a permission MAY
  * BCP 14 keywords in capitals appear only inside those blocks
  * every requirement has at least one test; every test covers requirements
    that exist and belong to the same class; every fixture file exists
  * a ruleset requirement has a valid and an invalid test; a linter
    requirement has a test that expects results; a permission has a test
    that shows the permitted thing is accepted; a recommendation has none.
    Tests are listed with what conforms first: valid or results, then
    invalid, no results, or rejected
  * an example block that names a fixture (data-fixture) is identical to it
  * fixture names stay inside their test directory and are plain files; a
    test.json has the field types the registry schema describes
  * an include names a file next to the draft or one the build generates
  * formats.json and the schema's Format enum list the same identifiers
  * emphasis is written *text*, not _text_, and a discussion is always linked
  * ids are unique, classes depend only on declared classes, blocks are closed
    and do not nest, and a removed requirement names the removing version
  * the issues index is linked only while issues remain, since Bikeshed
    generates it only then
  * identifiers are permanent: every requirement a release lists is still in
    the draft of its major version and of every later one, current or removed with
    data-removed=<version>; a text change to a released requirement is
    reported for the editor to judge
  * a change made in one draft is not missed in another: every requirement of
    a draft is in each later draft, and one that both list as current has the
    same kind, class, status, and source text in both; a test that differs
    between them, or that the later draft lacks, is reported
  * requirements.json matches schema/registry.schema.json
  * the ruleset schema's $id is the URL it is published at, so each release's
    schema has an identity of its own
  * every property in a table generated from the ruleset schema has a
    description, and no description uses a BCP 14 keyword
  * implementations are named only in issues and the provenance appendix,
    never in requirements, informative text, schema descriptions, or test
    purposes, so a release states every rule as its own
  * a test's expectation matches its class's target
  * the parts of the document hold one target each: the ruleset format holds
    ruleset requirements, Documents, Linting, and Functions linter ones

It then expands the blocks with their visible headers, replaces each
<div class=schema-table data-def="..."></div> with a property table generated
from the ruleset schema, generates the requirements index, the formats table,
the conformance test appendix, and the list of requirements the schema cannot
express, and writes a machine-readable registry (requirements.json) with its
schema next to each built document. The site gets a versions index, an
index.html in every published conformance/ directory, and /v<major>/ as a copy
of each major version's latest release.
Every conformance/ directory it publishes gets an index.html, because GitHub
Pages lists no directories.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from specbuild.checks import check_across_versions
from specbuild.config import ROOT, SITE, SpecError, schema_file
from specbuild.site import build_version, latest_releases, remove_tree, write_versions_index
from specbuild.versions import discover_versions, parse_version


def main(argv: list[str]) -> int:
    options = [a for a in argv if a.startswith("-")]
    names = [a for a in argv if not a.startswith("-")]
    if set(options) - {"--check"} or len(names) > 1:
        print(__doc__, file=sys.stderr)
        return 2
    check_only = "--check" in options
    only = names[0] if names else None
    try:
        all_versions = [parse_version(name, path) for name, path in discover_versions(None)]
        versions = [v for v in all_versions if only in (None, v.name)]
        if not versions:
            raise SpecError(f"no version named {only!r}")
        cross, notices = check_across_versions(all_versions)
        for n in notices:
            print(f"notice: {n}")
        if cross:
            raise SpecError("\n".join(cross))
        if check_only:
            with tempfile.TemporaryDirectory() as scratch:
                for v in versions:
                    build_version(v, site=Path(scratch) / "site", build=Path(scratch) / "build")
        for v in versions:
            n_req = sum(1 for r in v.requirements if r.kind == "req")
            print(f"{v.name}: {len(v.classes)} classes, {n_req} requirements, "
                  f"{len(v.requirements) - n_req} recommendations and permissions, {len(v.tests)} tests, checks passed")
        if check_only:
            return 0
        if not only:
            remove_tree(SITE)
        SITE.mkdir(exist_ok=True)
        shutil.copytree(ROOT / "assets", SITE / "assets", dirs_exist_ok=True)
        for v in versions:
            print(f"built {build_version(v).relative_to(ROOT)}")
        if not only:
            print(f"wrote {write_versions_index(all_versions).relative_to(ROOT)}")
            newest = latest_releases(all_versions)
            for line in sorted({v.major for v in all_versions}):
                alias = SITE / f"v{line}"
                if line in newest:
                    shutil.copytree(SITE / newest[line].site_path, alias, dirs_exist_ok=True)
                    print(f"wrote {alias.relative_to(ROOT)}/ from site/{newest[line].site_path}/, the latest {line}.x release")
                else:
                    draft = next(v for v in all_versions if v.is_draft and v.major == line)
                    shutil.copy(schema_file(draft.source_dir), alias / "ruleset.schema.json")
                    print(f"wrote {alias.relative_to(ROOT)}/ruleset.schema.json from {draft.name}/, which has no release yet")
        return 0
    except SpecError as e:
        print(f"error:\n{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
