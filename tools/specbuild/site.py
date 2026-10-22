"""Writing site/: each version, the conformance pages, the versions index, and the per-major-version aliases."""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

from .config import BASE_URL, BIKESHED, BUILD, REGISTRY_SCHEMA, SCHEMA_REQUIREMENT, SITE, SpecError, schema_file, semver_key
from .model import Test, Version, test_files
from .registry import check_registry, registry
from .render import conformance_appendix, link, listing_page, outcome_badge, plain_html, quote_markup, requirements_index
from .schema_tables import formats_table


def remove_tree(path: Path) -> None:
    """Delete a directory; a missing one is fine, anything else that fails is an error."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def build_version(version: Version, site: Path = SITE, build: Path = BUILD) -> Path:
    build_dir = build / version.site_path
    out_dir = site / version.site_path
    remove_tree(build_dir)
    build_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    for include in version.source_dir.glob("*.include"):
        shutil.copy(include, build_dir / include.name)
    (build_dir / "index.bs").write_text(version.expanded, encoding="utf-8")
    (build_dir / "requirements-index.include").write_text(requirements_index(version), encoding="utf-8")
    (build_dir / "conformance-tests.include").write_text(conformance_appendix(version), encoding="utf-8")
    (build_dir / "formats-table.include").write_text(formats_table(version.source_dir), encoding="utf-8")
    gaps = [r for r in version.requirements
            if r.target == "ruleset" and r.kind == "req" and r.id != SCHEMA_REQUIREMENT and r.status != "removed"]
    (build_dir / "schema-gaps.include").write_text(
        "<ul>" + "".join(f"<li>{link(r.id)}: {quote_markup(r.body)}</li>" for r in gaps) + "</ul>", encoding="utf-8")
    reg = registry(version)
    check_registry(reg, version.name)
    out_file = out_dir / "index.html"
    result = subprocess.run(  # noqa: PLW1510, the exit code is read below
        [BIKESHED, "--die-on=link-error", "spec", str(build_dir / "index.bs"), str(out_file)],
        capture_output=True, text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SpecError(f"bikeshed failed for {version.name}")
    (out_dir / "requirements.json").write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
    reg_schema = json.loads(REGISTRY_SCHEMA.read_text(encoding="utf-8"))
    reg_schema = {"$schema": reg_schema.pop("$schema"), "$id": f"{BASE_URL}/{version.site_path}/registry.schema.json", **reg_schema}
    (out_dir / "registry.schema.json").write_text(json.dumps(reg_schema, indent=2) + "\n", encoding="utf-8")
    remove_tree(out_dir / "conformance")
    shutil.copytree(version.source_dir / "conformance", out_dir / "conformance", symlinks=True)
    write_conformance_pages(version, out_dir / "conformance")
    shutil.copy(schema_file(version.source_dir), out_dir / "ruleset.schema.json")
    return out_file


def write_conformance_pages(version: Version, root: Path) -> None:
    """An index.html for conformance/, each section, and each test, which GitHub Pages would otherwise serve as 404."""
    def item(test: Test, href: str) -> str:
        return f'<li><a class="id" href="{href}">{html.escape(test.id)}</a>: {plain_html(test.purpose)}</li>'

    sections: dict[str, list[Test]] = {}
    for test in version.tests:
        sections.setdefault(test.section, []).append(test)
    body = "".join(f'<h2><a href="{s}/">{html.escape(s)}</a></h2><ul>{"".join(item(t, f"{s}/{t.name}/") for t in ts)}</ul>'
                   for s, ts in sections.items())
    (root / "index.html").write_text(listing_page(f"Conformance tests: {version.label}", "../index.html#conformance-tests", "Back to the specification", body), encoding="utf-8")
    for s, ts in sections.items():
        body = f'<ul>{"".join(item(t, f"{t.name}/") for t in ts)}</ul>'
        (root / s / "index.html").write_text(listing_page(f"/conf/{s}/", "../", "All conformance tests", body), encoding="utf-8")
        for t in ts:
            covers = ", ".join(f'<a class="id" href="../../../index.html#{html.escape(r)}">{html.escape(r)}</a>' for r in t.covers)
            files = "".join(f'<li><a href="{html.escape(name)}">{html.escape(name)}</a></li>' for name in test_files(t))
            body = (f"<p>{plain_html(t.purpose)}</p><p>Covers {covers}. Expected: {outcome_badge(t)}.</p>"
                    f"<h2>Files</h2><ul>{files}</ul>")
            (root / s / t.name / "index.html").write_text(listing_page(t.id, "../", f"/conf/{s}/", body), encoding="utf-8")


def write_versions_index(versions: list[Version]) -> Path:
    drafts = sorted((v for v in versions if v.is_draft), key=lambda v: v.major, reverse=True)
    releases = sorted((v for v in versions if not v.is_draft), key=lambda v: semver_key(v.name), reverse=True)
    title = versions[0].title

    def card(v: Version, note: str, schema_alias: str) -> str:
        n = html.escape(v.site_path)
        reqs = sum(1 for r in v.requirements if r.kind == "req" and r.status != "removed")
        schema_note = f'<br><span class="muted">{schema_alias}</span>' if schema_alias else ""
        return f"""<li class="version">
  <div class="version-head"><a class="version-name" href="{n}/index.html">{html.escape(v.label)}</a><span class="path">/{n}/</span></div>
  <p class="note">{note}{len(v.classes)} conformance classes, {reqs} requirements, {len(v.tests)} conformance tests.</p>
  <p class="primary"><a class="button" href="{n}/index.html">Read the specification</a></p>
  <table class="links">
    <tr><th>JSON Schema</th><td><a href="{n}/ruleset.schema.json">/{n}/ruleset.schema.json</a>{schema_note}</td></tr>
    <tr><th>Registry</th><td><a href="{n}/requirements.json">/{n}/requirements.json</a><br><span class="muted">Requirements, classes, and tests as JSON, described by <a href="{n}/registry.schema.json">registry.schema.json</a>.</span></td></tr>
    <tr><th>Conformance tests</th><td><a href="{n}/conformance/">/{n}/conformance/</a><br><span class="muted">One directory per test, with its fixtures.</span></td></tr>
  </table>
</li>"""

    newest = latest_releases(versions)

    def alias(line: int, until: str) -> str:
        return f'Also served at <a href="v{line}/ruleset.schema.json">/v{line}/ruleset.schema.json</a> {until}.'

    items = [card(d, f"The working draft of {d.major}.x. Changes without notice. ",
                  "" if d.major in newest else alias(d.major, f"until {d.major}.x has a release"))
             for d in drafts]
    for v in releases:
        latest = newest.get(v.major) is v
        note = f'Latest {v.major}.x release, also served at <a href="v{v.major}/">/v{v.major}/</a>. ' if latest else ""
        items.append(card(v, note + f"Released {html.escape(v.metadata.get('Date', ''))}. ",
                          alias(v.major, f"while this is the latest {v.major}.x release") if latest else ""))

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}: versions</title>
<link rel="icon" href="assets/openlint-icon.svg">
<style>
  :root {{ color-scheme: light dark; --fg: #1f1f1f; --bg: #fff; --muted: #6b6b6b; --rule: #e3e3e3; --rule-strong: #c9c9c9; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --fg: #e6e6e6; --bg: #141413; --muted: #9c9c9c; --rule: #2e2e2e; --rule-strong: #444; }} }}
  body {{ margin: 0; padding: 3rem 1rem; font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--fg); background: var(--bg); }}
  main {{ max-width: 44rem; margin: 0 auto; }}
  header {{ display: flex; gap: 1rem; align-items: center; margin-bottom: 1.25rem; }}
  header img {{ width: 44px; height: 44px; border-radius: 9px; }}
  h1 {{ font-size: 1.5rem; font-weight: 650; margin: 0; letter-spacing: -.01em; }}
  p.lede {{ color: var(--muted); margin: 0 0 2rem; }}
  a {{ color: inherit; text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: .18em; }}
  a:hover {{ text-decoration-color: currentColor; }}
  ul.versions {{ list-style: none; padding: 0; margin: 0; }}
  li.version {{ border-top: 1px solid var(--rule-strong); padding: 1.5rem 0 2rem; }}
  .version-head {{ display: flex; align-items: baseline; gap: 1rem; }}
  .version-name {{ font-size: 1.25rem; font-weight: 650; text-decoration: none; }}
  .version-name:hover {{ text-decoration: underline; }}
  .path {{ margin-left: auto; font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .9rem; color: var(--muted); }}
  p.note {{ margin: .25rem 0 1rem; color: var(--muted); font-size: .95rem; }}
  p.primary {{ margin: 0 0 1.25rem; }}
  a.button {{ display: inline-block; padding: .55rem 1.1rem; border-radius: 6px; background: var(--fg); color: var(--bg); font-weight: 600; text-decoration: none; }}
  a.button::after {{ content: " →"; }}
  a.button:hover {{ opacity: .85; text-decoration: none; }}
  table.links {{ border-collapse: collapse; width: 100%; font-size: .95rem; }}
  table.links th, table.links td {{ text-align: left; vertical-align: top; padding: .55rem 0; border-top: 1px solid var(--rule); }}
  table.links th {{ width: 11rem; font-weight: 600; padding-right: 1rem; }}
  table.links td a {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .9rem; }}
  .muted {{ color: var(--muted); font-size: .9rem; }}
  .muted a {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; }}
  code {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .9em; }}
  footer {{ margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--rule-strong); font-size: .9rem; color: var(--muted); }}
</style>
</head>
<body>
<main>
<header><img src="assets/openlint-icon.svg" alt=""><h1>{html.escape(title)}</h1></header>
<p class="lede">Every release lives at its own path and never changes once published. Fixes ship as a new patch release. Each major version has a working draft, where its changes land first.</p>
<ul class="versions">
{chr(10).join(items)}
</ul>
<footer>Source: <a href="https://github.com/openlint/spec">openlint/spec</a>.</footer>
</main>
</body>
</html>
"""
    SITE.mkdir(exist_ok=True)
    path = SITE / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def latest_releases(versions: list[Version]) -> dict[int, Version]:
    """The newest release of each line that has one."""
    newest: dict[int, Version] = {}
    for v in sorted((v for v in versions if not v.is_draft), key=lambda v: semver_key(v.name)):
        newest[v.major] = v
    return newest
