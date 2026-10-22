#!/usr/bin/env python3
"""Run a version's conformance tests against a linter.

Usage:
  tools/conformance.py v1 --linter 'openlint lint -r {ruleset} -f json {document}'
  tools/conformance.py v1 --linter '...' --only /conf/given

The linter command is a template. {ruleset} and {document} are replaced with
fixture paths, and the command runs in the test's directory so relative
references in fixtures resolve. The contract is small:

  * print the results for the document as a JSON array on stdout, in the
    result model of the specification (code, path, severity, message, range,
    source), with an empty array when there are none;
  * when the ruleset cannot be loaded, print nothing parseable as JSON on
    stdout and exit with a nonzero status.

A test of a requirement marked data-status=proposed states behavior ahead of
the implementations. It runs and is reported, but does not fail the run.

A linter that breaks the contract fails the test whatever it expects: it runs
longer than TIMEOUT seconds, or it exits with status 0 without printing results.
Before the tests, the runner lints a ruleset that every linter has to load; a
linter that prints no results for it is not run against the tests at all. A
relative path in the command is taken from the directory the runner starts in.

A test for a ruleset requirement runs the linter on an empty document and
passes when the linter loads (valid) or rejects (invalid) the ruleset. A test
for a linter requirement compares the results with the expectation: the same
number of results, each expected entry matching one actual result on the
fields it names, in any order unless the expectation sets "ordered". In an
expected entry, "has" lists fields that must be present and "${document}"
stands for the absolute path of the document fixture.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specbuild.config import SpecError
from specbuild.fixtures import fixture_path
from specbuild.versions import discover_versions, parse_version

TIMEOUT = 120
PREFLIGHT_RULESET = "rules:\n  preflight:\n    given: $\n    then:\n      function: truthy\n"


def linter_command(template: str) -> list[str]:
    """The template split into arguments, with a relative path that exists made absolute, since tests run elsewhere."""
    parts = shlex.split(template)
    return [str(Path(p).resolve()) if "{" not in p and not Path(p).is_absolute() and Path(p).exists() else p for p in parts]


def run_linter(cmd: list[str], ruleset: Path, document: Path, cwd: Path) -> tuple[str, list | None, str]:
    """What the linter did: "results" with the results, "rejected", or "broken" when it broke the contract."""
    cmd = [part.replace("{ruleset}", str(ruleset)).replace("{document}", str(document)) for part in cmd]
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return "broken", None, f"the linter ran longer than {TIMEOUT} seconds"
    except OSError as e:
        return "broken", None, f"the linter could not be started: {e}"
    stdout = proc.stdout.lstrip()
    if stdout.startswith("["):
        try:
            results, _ = json.JSONDecoder().raw_decode(stdout)
            if isinstance(results, list):
                return "results", results, proc.stderr.strip()
        except json.JSONDecodeError:
            pass
    detail = proc.stderr.strip() or proc.stdout.strip()
    if proc.returncode == 0:
        return "broken", None, f"the linter exited with status 0 without printing results as JSON: {detail[:200]}"
    return "rejected", None, detail or f"exit {proc.returncode}"


def matches(expected: dict, actual: dict, document: Path) -> bool:
    """Partial match: every field the expectation names must agree, nested objects recursively."""
    if not isinstance(actual, dict):
        return False
    for key, value in expected.items():
        if key == "has":
            if not all(k in actual for k in value):
                return False
            continue
        if isinstance(value, dict):
            if not matches(value, actual.get(key), document):
                return False
            continue
        if isinstance(value, str):
            value = value.replace("${document}", str(document))
        if actual.get(key) != value:
            return False
    return True


def compare(expected: list[dict], actual: list[dict], document: Path, ordered: bool = False) -> str | None:
    if len(expected) != len(actual):
        return f"expected {len(expected)} results, got {len(actual)}: {summarize(actual)}"
    if ordered:
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            if not matches(e, a, document):
                return f"result {i} does not match {json.dumps(e)}; got {summarize(actual)}"
        return None
    remaining = list(actual)
    for e in expected:
        hit = next((a for a in remaining if matches(e, a, document)), None)
        if hit is None:
            return f"no result matches {json.dumps(e)}; got {summarize(actual)}"
        remaining.remove(hit)
    return None


def summarize(results: list[dict]) -> str:
    return json.dumps([{k: r.get(k) for k in ("code", "path", "severity") if k in r} for r in results])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run a version's conformance tests against a linter.")
    parser.add_argument("version", help="a draft such as v1, or a release such as 1.0.0")
    parser.add_argument("--linter", required=True, metavar="COMMAND", help="the linter command, with {ruleset} and {document}")
    parser.add_argument("--only", default="", metavar="PREFIX", help="run only the tests whose id starts with PREFIX")
    args = parser.parse_args(argv)
    version, only = args.version, args.only
    cmd = linter_command(args.linter)
    try:
        [(_, source_dir)] = discover_versions(version)
        parsed = parse_version(version, source_dir)
    except SpecError as e:
        print(f"error: {version} does not pass its checks:\n{e}", file=sys.stderr)
        return 1
    reqs = {r.id: r for r in parsed.requirements}
    failures: list[tuple[str, str]] = []
    passed = 0
    ran: set[str] = set()
    proposed: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "empty.yaml"
        empty.write_text("{}\n")
        preflight = Path(tmp) / "preflight.yaml"
        preflight.write_text(PREFLIGHT_RULESET)
        outcome, _, detail = run_linter(cmd, preflight, empty, Path(tmp))
        if outcome != "results":
            print("error: the linter printed no results for a ruleset every linter has to load:\n  " + "\n  ".join(detail.splitlines()[:6]), file=sys.stderr)
            return 2
        for test in parsed.tests:
            if only and not test.id.startswith(only):
                continue
            ruleset = fixture_path(test.dir, test.ruleset)
            document = fixture_path(test.dir, test.document) if test.document else empty
            ran.add(test.id)
            outcome, results, detail = run_linter(cmd, ruleset, document, test.dir)
            e = test.expect
            if outcome == "broken":
                ok, reason = False, detail
            elif "ruleset" in e:
                loaded = outcome == "results"
                ok = loaded == (e["ruleset"] == "valid")
                reason = "" if ok else ("linter loaded a ruleset expected to be invalid" if loaded
                                        else f"linter rejected a ruleset expected to be valid: {detail}")
            elif e.get("rejected"):
                ok = outcome == "rejected"
                reason = "" if ok else f"linter accepted the ruleset and produced {summarize(results)}"
            elif outcome == "rejected":
                ok, reason = False, f"linter rejected the ruleset: {detail}"
            else:
                reason = compare(e.get("results", []), results, document, ordered=bool(e.get("ordered"))) or ""
                ok = not reason
            if any(reqs[r].status == "proposed" for r in test.covers):
                proposed.append((test.id, ok))
                print(f"{'pass' if ok else 'fail'}  {test.id}  (proposed requirement, not counted)")
                if not ok:
                    print(f"      {reason}")
                continue
            mark = "pass" if ok else "FAIL"
            print(f"{mark}  {test.id}")
            if ok:
                passed += 1
            else:
                print(f"      {reason}")
                failures.append((test.id, reason))

    total = passed + len(failures)
    if not total and not proposed:
        print(f"error: no test matches {only!r}", file=sys.stderr)
        return 2
    print(f"\n{passed} of {total} tests passed")
    if proposed:
        print(f"{sum(ok for _, ok in proposed)} of {len(proposed)} tests of proposed requirements pass; they do not count")
    failed_reqs = sorted({r for t, _ in failures for r in next(x for x in parsed.tests if x.id == t).covers})
    if failed_reqs:
        print("requirements with a failing test:")
        for rid in failed_reqs:
            print(f"  {rid}  ({reqs[rid].klass})")
    failed = {t for t, _ in failures}
    classes_ok = [c.id for c in parsed.classes if c.tests and set(c.tests) <= ran and not set(c.tests) & failed
                  and not any(reqs[r].status == "proposed" for r in c.members)]
    if classes_ok:
        print("conformance classes passed in full: " + ", ".join(classes_ok))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
