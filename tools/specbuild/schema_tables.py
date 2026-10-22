"""Property tables generated from the ruleset schema, and the formats table."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .render import quote_markup
from .scan import KEYWORDS, MENTION


def load_formats(source_dir: Path) -> dict[str, dict[str, str]]:
    """Family -> identifier -> the condition under which a linter detects the format, in prose with code spans."""
    return json.loads((source_dir / "formats.json").read_text(encoding="utf-8"))


def formats_table(source_dir: Path) -> str:
    rows = []
    for family, ids in load_formats(source_dir).items():
        for i, (ident, condition) in enumerate(ids.items()):
            family_cell = f'<td rowspan="{len(ids)}">{html.escape(family)}</td>' if i == 0 else ""
            rows.append(f"<tr>{family_cell}<td><code>{html.escape(ident)}</code></td><td>{quote_markup(condition)}</td></tr>")
    return ('<table class="data"><thead><tr><th>Family</th><th>Identifier</th><th>Detected when</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>")


SCHEMA_TABLE = re.compile(r'^<div class=schema-table data-def="(?P<def>[^"]*)"></div>\s*$')


DEF_SECTIONS = {
    "Formats": "rule-formats", "Extends": "extends", "Aliases": "aliases", "AliasTarget": "aliases",
    "Overrides": "overrides", "ParserOptions": "parser-options", "Severity": "rule-severity",
    "Given": "rule-given", "PathExpressionList": "rule-given", "Then": "rule-then",
    "Rule": "rule-object", "Shorthand": "shorthands",
}


PLURAL = {"string": "strings", "non-empty string": "non-empty strings", "object": "objects", "boolean": "booleans", "number": "numbers"}


def either(items: list[str]) -> str:
    return " or ".join(items) if len(items) <= 2 else ", ".join(items[:-1]) + ", or " + items[-1]


def sections_for(schema: dict, node) -> list[tuple[str, str]]:
    """The sections that define the values a node accepts, through references, alternatives, arrays, and maps."""
    if not isinstance(node, dict):
        return []
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        if name in DEF_SECTIONS:
            return [(DEF_SECTIONS[name], html.escape(schema["$defs"][name].get("title", name)))]
        return sections_for(schema, schema["$defs"][name])
    found = []
    for alt in node.get("oneOf", []) + node.get("anyOf", []) + [node.get("then"), node.get("else"), node.get("items"), node.get("additionalProperties")]:
        for s in sections_for(schema, alt):
            if s not in found:
                found.append(s)
    return found


JSON_TYPE = {"string": "string", "number": "number", "integer": "integer", "boolean": "boolean", "null": "null", "object": "object"}


def coarse_type(schema: dict, node, plural: bool = False) -> str:
    """The JSON type a node accepts, in a word or two, without the detail the linked section gives."""
    if node is True:
        return "any"
    if "$ref" in node:
        return coarse_type(schema, schema["$defs"][node["$ref"].rsplit("/", 1)[-1]], plural)
    if "enum" in node:
        kinds = list(dict.fromkeys("string" if isinstance(v, str) else "number" for v in node["enum"]))
        return either([PLURAL.get(k, k + "s") if plural else k for k in kinds])
    kind = node.get("type")
    if kind == "array" and "items" not in node:
        return "arrays" if plural else "array"
    if kind == "array":
        return f"{'arrays' if plural else 'array'} of {coarse_type(schema, node['items'], plural=True)}"
    if kind == "object" and isinstance(node.get("additionalProperties"), dict):
        return f"{'maps' if plural else 'map'} of {coarse_type(schema, node['additionalProperties'], plural=True)}"
    if kind in JSON_TYPE:
        return PLURAL.get(kind, kind + "s") if plural else kind
    alts = node.get("oneOf") or node.get("anyOf") or ([node["then"], node["else"]] if "then" in node and "else" in node else None)
    if alts:
        return either(list(dict.fromkeys(coarse_type(schema, alt, plural) for alt in alts)))
    raise ValueError(f"the table generator cannot describe {json.dumps(node)[:80]}")


def schema_type(schema: dict, node, plural: bool = False) -> str:
    """The JSON shape a schema node accepts, in a few words."""
    if node is True:
        return "any"
    if "$ref" in node:
        return schema_type(schema, schema["$defs"][node["$ref"].rsplit("/", 1)[-1]], plural)
    if "enum" in node:
        values = [f"<code>{html.escape(v if isinstance(v, str) else json.dumps(v))}</code>" for v in node["enum"]]
        return either(values) if len(values) <= 2 else "one of " + ", ".join(values)
    kind = node.get("type")
    if kind == "string":
        text = "non-empty string" if node.get("minLength", 0) >= 1 else "string"
        text = PLURAL[text] if plural else text
        if "format" in node:
            return f"{text} ({'URI' if node['format'] == 'uri' else html.escape(node['format'])})"
        return f"{text} ({html.escape(node['title'])})" if "pattern" in node and "title" in node else text
    if kind == "array":
        prefix = "non-empty array" if node.get("minItems", 0) >= 1 else "array"
        return f"{prefix} of {schema_type(schema, node.get('items', True), plural=True)}"
    if kind == "object" and isinstance(node.get("additionalProperties"), dict):
        return f"{'maps' if plural else 'map'} of {schema_type(schema, node['additionalProperties'], plural=True)}"
    if kind in ("object", "boolean"):
        return PLURAL[kind] if plural else kind
    for key in ("oneOf", "anyOf"):
        if key in node:
            return either(list(dict.fromkeys(schema_type(schema, alt, plural) for alt in node[key])))
    if "if" in node and "then" in node and "else" in node:
        return either(list(dict.fromkeys(schema_type(schema, alt, plural) for alt in (node["then"], node["else"]))))
    raise ValueError(f"the table generator cannot describe {json.dumps(node)[:80]}")


def type_cell(schema: dict, prop) -> str:
    """The JSON type, with a link to the section that defines the values; the full shape when no section does."""
    sections = sections_for(schema, prop)
    if not sections:
        return schema_type(schema, prop)
    return f"{coarse_type(schema, prop)}, see {either([f'[[#{s}|{title}]]' for s, title in sections])}"


def schema_table(schema: dict, pointer: str) -> tuple[str, list[str]]:
    """The property table of one object in the ruleset schema, and what is missing to generate it."""
    node = schema if pointer == "#" else schema["$defs"].get(pointer)
    if not isinstance(node, dict) or "properties" not in node:
        return "", [f"data-def={pointer!r} names no object with properties in the ruleset schema"]
    errors = []
    required = node.get("required", [])
    rows = []
    for name in sorted(node["properties"], key=lambda n: n not in required):
        prop = node["properties"][name]
        description = prop.get("description")
        if description is None and "$ref" in prop:
            description = schema["$defs"][prop["$ref"].rsplit("/", 1)[-1]].get("description")
        if not description:
            errors.append(f"{pointer}: property {name!r} has no description in the ruleset schema, which the table is generated from")
        elif KEYWORDS.search(description):
            errors.append(f"{pointer}: the description of {name!r} uses a BCP 14 keyword, but generated tables are informative")
        elif MENTION.search(description):
            errors.append(f"{pointer}: the description of {name!r} names an implementation; that belongs in an issue")
        try:
            kind = type_cell(schema, prop)
        except ValueError as e:
            errors.append(f"{pointer}: property {name!r}: {e}")
            kind = ""
        req_cell = f"<td>{'yes' if name in required else ''}</td>" if required else ""
        rows.append(f"<tr><td><code>{html.escape(name)}</code></td><td>{kind}</td>{req_cell}<td>{quote_markup(description or '')}</td></tr>")
    if "^x-" in node.get("patternProperties", {}):
        rows.append(f'<tr><td><code>x-*</code></td><td>any</td>{"<td></td>" if required else ""}'
                    '<td>[[#extension-properties|Extension property]].</td></tr>')
    notes = []
    at_least = [alt["required"][0] for alt in node.get("anyOf", []) if list(alt) == ["required"] and len(alt["required"]) == 1]
    if at_least:
        notes.append(f"At least one of {either([f'<code>{html.escape(n)}</code>' for n in at_least])} is required.")
    if node.get("additionalProperties") is False:
        notes.append("No other properties are allowed.")
    head = "<th>Property</th><th>Type</th>" + ("<th>Required</th>" if required else "") + "<th>Description</th>"
    note = f'\n<p class="schema-source">{" ".join(notes)}</p>' if notes else ""
    return f'<table class="data schema-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>{note}', errors
