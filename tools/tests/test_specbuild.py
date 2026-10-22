"""Unit tests for the build tooling. Run with: python3 -m unittest discover -s tools/tests"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import conformance
import release
from specbuild.checks import check_discussion_links, check_issues_index, check_underscore_emphasis, compare_drafts
from specbuild.config import SpecError
from specbuild.fixtures import fixture_path
from specbuild.fixtures import load_tests as read_tests
from specbuild.model import Requirement, Test, Version
from specbuild.render import quote_markup, source_text
from specbuild.scan import parse_attrs
from specbuild.schema_tables import schema_table, type_cell
from specbuild.versions import parse_version

SRC = Path("src")


def requirement(rid: str, body: str, status: str = "", kind: str = "req", klass: str = "linter-core", line: int = 1) -> Requirement:
    return Requirement(id=rid, kind=kind, klass=klass, target="linter", since="", removed="", status=status,
                       section_id="s", section_title="S", line=line, text=body, body=body)


def version(name: str, reqs: list[Requirement], tests: list[Test] | None = None) -> Version:
    return Version(name=name, source_dir=SRC / name, metadata={}, classes=[], requirements=reqs, tests=tests or [], expanded="")


class Attributes(unittest.TestCase):
    def test_every_quoting(self):
        attrs = parse_attrs(' id="/req/a/b" data-class=linter-core data-status=\'proposed\'')
        self.assertEqual(attrs, {"id": "/req/a/b", "data-class": "linter-core", "data-status": "proposed"})


class Fixtures(unittest.TestCase):
    def test_subpath_is_allowed_and_escapes_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.assertEqual(fixture_path(d, "legacy/doc.yaml"), d / "legacy/doc.yaml")
            for bad in ("../x.yaml", "/etc/hosts", "a/../../x", ""):
                with self.assertRaises(ValueError, msg=bad):
                    fixture_path(d, bad)

    def test_load_tests_reads_ids_and_reports_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            good = root / "conformance/given/present"
            good.mkdir(parents=True)
            (good / "ruleset.yaml").write_text("rules: {}\n")
            (good / "test.json").write_text(json.dumps({"for": "/req/given/evaluate", "purpose": "Runs.", "expect": {"ruleset": "valid"}}))
            bad = root / "conformance/given/broken"
            bad.mkdir()
            (bad / "test.json").write_text(json.dumps({"for": ["/req/x/y"], "purpose": "", "ruleset": "../../x.yaml", "expect": {"nope": 1}}))
            tests, errors = read_tests(root)
            self.assertEqual([t.id for t in tests], ["/conf/given/broken", "/conf/given/present"])
            self.assertEqual(tests[1].covers, ["/req/given/evaluate"])
            joined = "\n".join(errors)
            self.assertIn("'purpose' is missing", joined)
            self.assertIn("relative path inside the test directory", joined)
            self.assertIn("'expect' keys must be among", joined)


class Escaping(unittest.TestCase):
    def test_source_text_escapes_outside_code_spans(self):
        self.assertEqual(source_text("a <b> `x<y>` c"), "a &lt;b&gt; `x<y>` c")

    def test_quote_markup_strips_links_and_keeps_code(self):
        self.assertEqual(quote_markup("A [=linter=] MUST see `$ref` [[!RFC8259]]"), "A linter MUST see <code>$ref</code> RFC8259")


SCHEMA = {
    "$defs": {
        "Severity": {"title": "Severity", "enum": ["error", "warn"]},
        "Thing": {"type": "object", "properties": {
            "severity": {"$ref": "#/$defs/Severity", "description": "How bad it is."},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Labels."},
            "secret": {"type": "string"},
            "loud": {"type": "string", "description": "A linter MUST shout."},
        }, "required": ["severity"]},
    }
}


class SchemaTables(unittest.TestCase):
    def test_type_cell_links_defined_values_and_describes_the_rest(self):
        self.assertEqual(type_cell(SCHEMA, {"$ref": "#/$defs/Severity"}), "string, see [[#rule-severity|Severity]]")
        self.assertEqual(type_cell(SCHEMA, {"type": "array", "items": {"type": "string"}}), "array of strings")

    def test_table_reports_missing_descriptions_and_keywords(self):
        html, problems = schema_table(SCHEMA, "Thing")
        self.assertIn("<code>severity</code></td><td>string, see [[#rule-severity|Severity]]</td><td>yes</td>", html)
        self.assertIn("'secret' has no description", "\n".join(problems))
        self.assertIn("'loud' uses a BCP 14 keyword", "\n".join(problems))


class LineChecks(unittest.TestCase):
    def test_discussion_mentions_need_their_link(self):
        ok = 'See <a href="https://github.com/orgs/openlint/discussions/13">discussion #13</a>.'
        self.assertEqual(check_discussion_links(SRC, ok), [])
        self.assertEqual(len(check_discussion_links(SRC, "See discussion #13.")), 1)
        self.assertEqual(len(check_discussion_links(SRC, ok.replace("/13", "/12"))), 1)

    def test_underscore_emphasis_is_caught_outside_code(self):
        self.assertEqual(check_underscore_emphasis(SRC, "x `_a_` y"), [])
        self.assertEqual(len(check_underscore_emphasis(SRC, "_This is informative._")), 1)

    def test_issues_index_link_needs_an_issue(self):
        self.assertEqual(check_issues_index(SRC, "Issue: open.\n\nSee [[#issues-index]]."), [])
        self.assertEqual(len(check_issues_index(SRC, "See [[#issues-index]].")), 1)


class AcrossDrafts(unittest.TestCase):
    def test_a_later_draft_lists_the_same_requirements(self):
        a = requirement("/req/a/b", "A linter MUST x.")
        notices: list[str] = []
        self.assertEqual(compare_drafts(version("v1", [a]), version("v2", [a]), notices), [])
        missing = compare_drafts(version("v1", [a]), version("v2", []), notices)
        self.assertIn("is missing from the v2 draft", missing[0])
        changed = compare_drafts(version("v1", [a]), version("v2", [requirement("/req/a/b", "A linter MUST y.")]), notices)
        self.assertIn("differs between the v1 and v2 drafts", changed[0])
        removed_later = compare_drafts(version("v1", [a]), version("v2", [requirement("/req/a/b", "A linter MUST x.", status="removed")]), notices)
        self.assertEqual(removed_later, [])
        current_again = compare_drafts(version("v1", [requirement("/req/a/b", "x", status="removed")]), version("v2", [a]), notices)
        self.assertIn("stays removed", current_again[0])


class Runner(unittest.TestCase):
    def test_results_match_on_named_fields_and_order_when_asked(self):
        doc = Path("/tmp/doc.yaml")
        actual = [{"code": "b", "path": ["x"], "severity": 1, "source": "/tmp/doc.yaml"}, {"code": "a", "path": [], "severity": 0}]
        self.assertIsNone(conformance.compare([{"code": "a"}, {"code": "b", "has": ["severity"], "source": "${document}"}], actual, doc))
        self.assertIn("result 0 does not match", conformance.compare([{"code": "a"}, {"code": "b"}], actual, doc, ordered=True))
        self.assertIn("expected 1 results", conformance.compare([{"code": "a"}], actual, doc))

    def test_a_linter_that_breaks_the_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "r.yaml").write_text("rules: {}\n")
            (d / "d.yaml").write_text("{}\n")
            quiet = conformance.run_linter([sys.executable, "-c", "print('nope')"], d / "r.yaml", d / "d.yaml", d)
            self.assertEqual(quiet[0], "broken")
            rejected = conformance.run_linter([sys.executable, "-c", "import sys; sys.exit(2)"], d / "r.yaml", d / "d.yaml", d)
            self.assertEqual(rejected[0], "rejected")
            fine = conformance.run_linter([sys.executable, "-c", "print('[{\"code\": \"r\"}]')"], d / "r.yaml", d / "d.yaml", d)
            self.assertEqual(fine[:2], ("results", [{"code": "r"}]))


class Release(unittest.TestCase):
    def test_stamping_and_metadata(self):
        src = ('<div class=req id="/req/a/b" data-class=x>\n</div>\n<div class=req id="/req/a/c" data-class=x data-status="proposed">\n</div>\n'
               '<div class=req id="/req/a/d" data-class=x data-since="0.9.0">\n</div>\n')
        out, stamped = release.stamp_since(src, "1.0.0")
        self.assertEqual(stamped, {"/req/a/b"})
        self.assertIn('data-class=x data-since="1.0.0">', out)
        meta = "<pre class='metadata'>\nTitle: T\nWarning: custom\n</pre>\nbody\n"
        edited = release.edit_metadata(meta, {"Date": "2026-01-01", "Title": "U"}, {"Warning"})
        self.assertEqual(edited, "<pre class='metadata'>\nTitle: U\nDate: 2026-01-01\n</pre>\nbody\n")


MINIMAL_BS = """<pre class='metadata'>
Title: Tiny
Text Macro: VERSIONLABEL Working Draft 1.x
</pre>

# Conformance # {#conformance}

<div class=class id="/conf/linter-core" data-target=linter>
Everything.
</div>

# Linting # {#linting}

## Given ## {#given}

<div class=req id="/req/given/evaluate" data-class=linter-core>
A linter MUST evaluate `given`.
</div>

<div class=req id="/req/given/quiet" data-class=linter-core>
A linter SHOULD not.
</div>
"""


class Parsing(unittest.TestCase):
    def test_a_tiny_specification_is_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "v1"
            root.mkdir()
            (root / "index.bs").write_text(MINIMAL_BS)
            (root / "formats.json").write_text("{}")
            (root / "ruleset.schema.json").write_text(json.dumps({"$id": "https://spec.openlint.org/v1/draft/ruleset.schema.json",
                                                                 "$defs": {"Format": {"enum": []}}}))
            t = root / "conformance/given/evaluate"
            t.mkdir(parents=True)
            (t / "ruleset.yaml").write_text("rules: {}\n")
            (t / "document.yaml").write_text("{}\n")
            (t / "test.json").write_text(json.dumps({"for": ["/req/given/evaluate"], "purpose": "Runs.", "document": "document.yaml",
                                                     "expect": {"results": [{"code": "r"}]}}))
            with self.assertRaises(SpecError) as caught:
                parse_version("v1", root)
            message = str(caught.exception)
            self.assertIn("/req/given/quiet uses SHOULD", message)
            self.assertIn("/req/given/quiet has no conformance test", message)
            (root / "index.bs").write_text(MINIMAL_BS.replace("A linter SHOULD not.", "A linter MUST not.")
                                           .replace('id="/req/given/quiet" data-class=linter-core', 'id="/req/given/quiet" data-class=linter-core data-status=removed data-removed="1.1.0"'))
            v = parse_version("v1", root)
            self.assertEqual([r.id for r in v.requirements], ["/req/given/evaluate", "/req/given/quiet"])
            self.assertEqual(v.tests[0].klass, "linter-core")
            self.assertIn('<em class="rfc2119">MUST</em>', v.expanded)


if __name__ == "__main__":
    unittest.main()
