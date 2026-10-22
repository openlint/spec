"""HTML for requirement and class blocks, the appendices, and the listing pages."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .model import KIND_NAME, ConformanceClass, Requirement, Test, Version, expect_kind, grouped, test_groups
from .scan import KEYWORDS

STYLE = "<style>\n" + Path(__file__).with_name("spec.css").read_text(encoding="utf-8") + "</style>"


def quote_markup(text: str) -> str:
    """Plain text for quoting inside the document: links stripped, code spans kept as <code>."""
    text = re.sub(r"\[=(?:[^=|]*\|)?([^=]+)=\]", r"\1", text)
    text = re.sub(r"\[\[!?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = " ".join(text.split())
    text = html.escape(text, quote=False).replace("{{", "&bs{;{").replace("[[", "&bs[;[")
    return re.sub(r"`([^`]*)`", r"<code>\1</code>", text)


def source_text(text: str) -> str:
    """Text from test.json for the Bikeshed source: markup escaped, code spans left for Bikeshed to render."""
    parts = text.split("`")
    if len(parts) % 2 == 0:
        return html.escape(text, quote=False)
    return "`".join(p if i % 2 else html.escape(p, quote=False) for i, p in enumerate(parts))


def link(target_id: str, text: str | None = None, css: str = "") -> str:
    t = html.escape(target_id)
    cls = f' class="{css}"' if css else ""
    return f'<a{cls} href="#{t}">{html.escape(text or target_id)}</a>'


def target_badge(target: str) -> str:
    return f'<span class="req-target req-target-{target}">{target}</span>'


def status_badge(status: str) -> str:
    return f'<span class="req-status req-status-{status}">{status}</span>' if status else ""


def kind_badge(kind: str) -> str:
    return f'<span class="req-kind req-kind-{kind}">{KIND_NAME[kind]}</span>' if kind != "req" else ""


def req_head(req: Requirement) -> str:
    parts = [link(req.id, css="req-id"), target_badge(req.target), status_badge(req.status)]
    if req.status != "example":
        parts.append(link(f"/conf/{req.klass}", req.klass, css="req-class"))
        parts.append(f'<span class="req-since">since {html.escape(req.since or "this draft")}</span>')
    return f'<p class="req-head">{"".join(p for p in parts if p)}</p>'


def class_head(c: ConformanceClass) -> str:
    deps = ", ".join(link(f"/conf/{d}", d) for d in c.depends) or "none"
    return (
        f'<p class="req-head">{link(c.id, css="req-id")}{target_badge(c.target)}'
        f'<span class="class-deps">depends on {deps}</span></p>'
    )


def class_members(c: ConformanceClass, requirements: dict[str, Requirement]) -> str:
    counts = {k: 0 for k in KIND_NAME}
    for rid in c.members:
        counts[requirements[rid].kind] += 1
    bits = [f"{n} {KIND_NAME[k]}{'s' if n != 1 else ''}" for k, n in counts.items() if n]
    bits.append(f"{len(c.tests)} test{'s' if len(c.tests) != 1 else ''}")
    return f'<p class="class-members">{", ".join(bits)}. {link("conf-class-" + c.name, "Tests")}, {link("index-class-" + c.name, "index")}.</p>'


def count(n: int, one: str, many: str = "") -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


def requirements_index(version: Version) -> str:
    reqs = {r.id: r for r in version.requirements}
    counts = {k: sum(1 for r in version.requirements if r.kind == k and r.status != "removed") for k in KIND_NAME}
    out = [
        (f"<p>{count(len(version.classes), 'conformance class', 'conformance classes')}, {count(counts['req'], 'requirement')}, "
         f"{count(counts['rec'], 'recommendation')}, {count(counts['per'], 'permission')}, and {count(len(version.tests), 'conformance test')}. "
         f'The same data is available as <a href="requirements.json">requirements.json</a>, and the tests '
         f'with their fixtures under <a href="conformance/">conformance/</a>.</p>')
    ]
    for c in version.classes:
        deps = ", ".join(link(f"/conf/{d}", d) for d in c.depends) or "none"
        out.append(f'<h3 class="no-num" id="index-class-{c.name}">{link(c.id)}</h3>')
        out.append(f"<p>{html.escape(c.text)} Target: {target_badge(c.target)} Depends on: {deps}.</p>")
        rows = []
        for rid in c.members:
            r = reqs[rid]
            if grouped(r.tests):
                tests = f'{link("tests" + r.id, f"{len(r.tests)} tests")}, grouped by section in [[#conformance-tests]]'
            else:
                tests = ", ".join(link(t) for t in r.tests) or ("Not tested: a recommendation." if r.kind == "rec" else "none")
            rows.append(
                "<tr>"
                f"<td>{link(r.id)}{status_badge(r.status)}</td>"
                f"<td>{link(r.section_id, r.section_title)}</td>"
                f"<td>{tests}</td>"
                f"<td>{html.escape(r.since or 'this draft')}</td>"
                "</tr>"
            )
        out.append(
            '<table class="data requirements-index">'
            "<thead><tr><th>Identifier</th><th>Section</th><th>Tests</th><th>Since</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
    return "\n".join(out)


def expectation(test: Test) -> str:
    e = test.expect
    if "ruleset" in e:
        text = ("The ruleset is valid: a linter loads it." if e["ruleset"] == "valid"
                else "The ruleset is invalid: a linter rejects it.")
        return f'<p class="test-expect">{text}</p>'
    if e.get("rejected"):
        return '<p class="test-expect">The linter rejects the ruleset and produces no results.</p>'
    results = e.get("results", [])
    if not results:
        return '<p class="test-expect">Linting produces no results.</p>'
    n = len(results)
    body = html.escape(json.dumps(results, indent=2))
    return (f'<p class="test-expect">Linting produces exactly {n} result{"s" if n != 1 else ""}, '
            f'matching on the fields given, in any order:</p><pre highlight="json">{body}</pre>')


def outcome_badge(test: Test) -> str:
    e = test.expect
    if "ruleset" in e:
        text = e["ruleset"]
    elif e.get("rejected"):
        text = "rejected"
    else:
        n = len(e.get("results", []))
        text = f"{n} result{'s' if n != 1 else ''}"
    return f'<span class="test-outcome test-outcome-{expect_kind(test)}">{text}</span>'


def highlight_for(name: str) -> str:
    """The syntax highlighting of a fixture, from its extension."""
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {"json": "json", "js": "js", "cjs": "js", "mjs": "js"}.get(suffix, "yaml")


def render_test(test: Test) -> str:
    rel = f"conformance{test.id[len('/conf'):]}"
    fixtures = [(name, highlight_for(name)) for name in [test.ruleset, *([test.document] if test.document else []), *test.files]]
    parts = [
        f'<details class="test" id="{html.escape(test.id)}">',
        f'<summary>{link(test.id, css="test-id")}<span class="test-purpose">{source_text(test.purpose)}</span>{outcome_badge(test)}</summary>',
        (f'<p class="test-for">Covers {", ".join(link(r) for r in test.covers)}. '
         f'Fixtures in <a href="{rel}/">{html.escape(rel)}/</a>.</p>'),
    ]
    for name, lang in fixtures:
        content = html.escape((test.dir / name).read_text(encoding="utf-8").rstrip("\n"))
        parts.append(f'<p class="fixture-label"><a href="{rel}/{html.escape(name)}">{html.escape(name)}</a></p>'
                     f'<pre highlight="{lang}">{content}</pre>')
    if test.target == "ruleset":
        parts.append('<p class="fixture-label">Procedure</p><p>Load the ruleset with a linter.</p>')
    else:
        doc = f"`{html.escape(test.document)}`" if test.document else "an empty document"
        parts.append(f'<p class="fixture-label">Procedure</p><p>Lint {doc} with `{html.escape(test.ruleset)}` and collect the results as JSON.</p>')
    parts.append(f'<p class="fixture-label">Expected</p>{expectation(test)}')
    parts.append("</details>")
    return "\n".join(parts)


def conformance_appendix(version: Version) -> str:
    reqs = {r.id: r for r in version.requirements}
    by_id = {t.id: t for t in version.tests}
    out = [
        ('<p class="tests-controls"><button type="button" onclick="document.querySelectorAll(\'details.test\').forEach(d => d.open = true)">Expand all</button> '
         '<button type="button" onclick="document.querySelectorAll(\'details.test\').forEach(d => d.open = false)">Collapse all</button></p>')
    ]
    for c in version.classes:
        out.append(f'<h3 class="no-num" id="conf-class-{c.name}">Conformance class {link(c.id)}</h3>')
        if not c.tests:
            out.append("<p>No tests yet.</p>")
        shown: set[str] = set()
        for rid in c.members:
            req = reqs[rid]
            if not req.tests:
                continue
            text = KEYWORDS.sub(r'<em class="rfc2119">\1</em>', quote_markup(req.body))
            out.append(f'<div class="req req-cited" id="tests{html.escape(req.id)}"><p class="req-head">{link(req.id, css="req-id")}{target_badge(req.target)}'
                       f'{status_badge(req.status)}<span class="req-back">in section {link(req.section_id, req.section_title)}</span></p>'
                       f'<p class="req-cited-text">{text}</p>')
            for tid, group in test_groups(req.tests, by_id):
                if group:
                    out.append(f'<p class="test-group">{html.escape(group)}</p>')
                if tid in shown:
                    test = by_id[tid]
                    out.append(f'<p class="test test-shared">{link(tid, css="test-id")}<span class="test-purpose">{source_text(test.purpose)}</span>'
                               f'{outcome_badge(test)}<span class="test-for">also covers {", ".join(link(r) for r in test.covers if r != rid)}; shown there</span></p>')
                    continue
                shown.add(tid)
                out.append(render_test(by_id[tid]))
            out.append("</div>")
    return "\n".join(out)


def plain_html(text: str) -> str:
    return re.sub(r"`([^`]*)`", r"<code>\1</code>", html.escape(text, quote=False))


def listing_page(title: str, up: str, up_label: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ max-width: 44rem; margin: 0 auto; padding: 2rem 1rem; font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  code, .id {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .9em; }}
  li {{ margin: .25rem 0; }}
</style>
</head>
<body>
<p><a href="{up}">{html.escape(up_label)}</a></p>
<h1>{html.escape(title)}</h1>
{body}
</body>
</html>
"""
