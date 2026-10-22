"""requirements.json, the machine-readable registry, and its validation against registry.schema.json."""

from __future__ import annotations

import json
import re
from datetime import date

from .config import REGISTRY_SCHEMA, SpecError
from .model import KIND_NAME, Version


def registry(version: Version) -> dict:
    return {
        "$schema": "registry.schema.json",
        "specification": version.title,
        "version": "draft" if version.is_draft else version.name,
        "line": version.major,
        "label": version.label,
        "generated": version.metadata.get("Date") or date.today().isoformat(),
        "classes": [
            {"id": c.id, "name": c.name, "target": c.target, "depends": c.depends,
             "members": c.members, "tests": c.tests, "text": c.text}
            for c in version.classes
        ],
        "requirements": [
            {
                "id": r.id, "kind": KIND_NAME[r.kind], "class": r.klass, "target": r.target,
                "status": r.status or "current", "since": r.since or "draft",
                **({"removed": r.removed} if r.removed else {}),
                "section": r.section_id, "tests": r.tests, "text": r.text,
            }
            for r in version.requirements
        ],
        "tests": [
            {
                "id": t.id, "for": t.covers, "class": t.klass, "target": t.target, "purpose": t.purpose,
                "dir": f"conformance{t.id[len('/conf'):]}", "ruleset": t.ruleset,
                "document": t.document, "files": t.files, "expect": t.expect,
            }
            for t in version.tests
        ],
    }


def validate(schema: dict, data, path: str = "$") -> list[str]:
    """Check data against the subset of JSON Schema the registry schema uses."""
    errors: list[str] = []
    if "const" in schema and data != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and data not in schema["enum"]:
        errors.append(f"{path}: {data!r} is not one of {schema['enum']}")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        py = {"object": dict, "array": list, "string": str, "null": type(None), "boolean": bool, "number": (int, float), "integer": int}
        if not any(isinstance(data, py[t]) for t in types):
            errors.append(f"{path}: expected {' or '.join(types)}, got {type(data).__name__}")
            return errors
    if isinstance(data, str) and "pattern" in schema and not re.search(schema["pattern"], data):
        errors.append(f"{path}: {data!r} does not match {schema['pattern']}")
    if isinstance(data, dict):
        for key in schema.get("required", []):
            if key not in data:
                errors.append(f"{path}: missing {key!r}")
        props = schema.get("properties", {})
        for key, value in data.items():
            if key in props:
                errors.extend(validate(props[key], value, f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected property {key!r}")
    if isinstance(data, list) and "items" in schema:
        for i, item in enumerate(data):
            errors.extend(validate(schema["items"], item, f"{path}[{i}]"))
    return errors


def check_registry(reg: dict, name: str) -> None:
    problems = validate(json.loads(REGISTRY_SCHEMA.read_text(encoding="utf-8")), reg)
    if problems:
        raise SpecError(f"{name}: requirements.json does not match schema/registry.schema.json:\n  " + "\n  ".join(problems[:20]))
