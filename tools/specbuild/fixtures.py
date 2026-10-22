"""Reading the conformance tests from their directories."""

from __future__ import annotations

import json
from pathlib import Path

from .config import rel_path
from .model import Test
from .scan import MENTION, TEST_ID


def fixture_path(test_dir: Path, name: str) -> Path:
    """The file a fixture name refers to, which has to stay inside the test's directory."""
    if not isinstance(name, str) or not name or name.startswith(('/', '\\')) or '..' in Path(name).parts or ':' in name:
        raise ValueError(f"fixture name {name!r} has to be a relative path inside the test directory")
    path = test_dir / name
    if not path.resolve().is_relative_to(test_dir.resolve()):
        raise ValueError(f"fixture name {name!r} leaves the test directory")
    return path


def load_tests(source_dir: Path) -> tuple[list[Test], list[str]]:
    tests: list[Test] = []
    errors: list[str] = []
    conf_dir = source_dir / "conformance"
    if not conf_dir.is_dir():
        return tests, [f"{rel_path(source_dir, 'conformance')}: directory missing"]
    for spec_file in sorted(conf_dir.glob("*/*/test.json")):
        test_dir = spec_file.parent
        tid = f"/conf/{test_dir.parent.name}/{test_dir.name}"
        loc = rel_path(source_dir, f"conformance/{test_dir.parent.name}/{test_dir.name}/test.json")
        try:
            data = json.loads(spec_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            errors.append(f"{loc}: {e}")
            continue
        if not TEST_ID.match(tid):
            errors.append(f"{loc}: directory names do not form a test id of the form /conf/<topic>/<name>")
        if not isinstance(data, dict):
            errors.append(f"{loc}: test.json has to be an object")
            continue
        covers = data.get("for", [])
        if isinstance(covers, str):
            covers = [covers]
        if not isinstance(covers, list) or not all(isinstance(c, str) for c in covers):
            errors.append(f"{loc}: 'for' must be a requirement identifier or a list of them")
            covers = [c for c in covers if isinstance(c, str)] if isinstance(covers, list) else []
        if not covers:
            errors.append(f"{loc}: 'for' must name at least one requirement")
        purpose = data.get("purpose", "")
        if not isinstance(purpose, str):
            errors.append(f"{loc}: 'purpose' must be a string")
            purpose = ""
        purpose = purpose.strip()
        if not purpose:
            errors.append(f"{loc}: 'purpose' is missing")
        elif MENTION.search(purpose):
            errors.append(f"{loc}: the purpose names an implementation; tests state what conforms")
        ruleset = data.get("ruleset", "ruleset.yaml")
        document = data.get("document")
        files = data.get("files", [])
        if not isinstance(files, list):
            errors.append(f"{loc}: 'files' must be a list of fixture names")
            files = []
        if not isinstance(ruleset, str):
            errors.append(f"{loc}: 'ruleset' must be a fixture name")
            ruleset = "ruleset.yaml"
        if document is not None and not isinstance(document, str):
            errors.append(f"{loc}: 'document' must be a fixture name")
            document = None
        if not all(isinstance(f, str) for f in files):
            errors.append(f"{loc}: 'files' must be a list of fixture names")
            files = [f for f in files if isinstance(f, str)]
        for name in [ruleset, document, *files]:
            if name is None:
                continue
            try:
                exists = fixture_path(test_dir, name).is_file()
            except ValueError as e:
                errors.append(f"{loc}: {e}")
                continue
            if not exists:
                errors.append(f"{loc}: fixture {name!r} does not exist")
        for path in test_dir.rglob("*"):
            if path.is_symlink():
                errors.append(f"{loc}: {path.relative_to(test_dir)} is a symbolic link; fixtures are plain files")
        expect = data.get("expect")
        if not isinstance(expect, dict) or not expect:
            errors.append(f"{loc}: 'expect' is missing")
            expect = {}
        known = {"ruleset", "rejected", "results", "ordered"}
        if not set(expect) <= known:
            errors.append(f"{loc}: 'expect' keys must be among {sorted(known)}, got {sorted(expect)}")
        if "ruleset" in expect and expect["ruleset"] not in ("valid", "invalid"):
            errors.append(f"{loc}: expect.ruleset must be 'valid' or 'invalid'")
        if "results" in expect and not (isinstance(expect["results"], list) and all(isinstance(r, dict) for r in expect["results"])):
            errors.append(f"{loc}: expect.results must be a list of objects")
            expect["results"] = [r for r in expect.get("results", []) if isinstance(r, dict)] if isinstance(expect.get("results"), list) else []
        tests.append(Test(id=tid, covers=covers, purpose=purpose, ruleset=ruleset, document=document,
                          files=files, expect=expect, dir=test_dir))
    return tests, errors
