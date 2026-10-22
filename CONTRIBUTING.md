# Contributing to the specification

This guide is for anyone who edits the OpenLint ruleset specification. It covers the files you edit, how the build checks them, and the conventions the text follows. To report a problem or suggest a change without editing, see [Where things go](README.md#where-things-go).

## Set up

### Layout

| Path                                                                      | What                                                                                                                                                                                                                                            |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `v1/`                                                                     | The working draft of 1.x: `index.bs`, `ruleset.schema.json`, the format identifiers and their detection conditions in `formats.json`, the conformance tests, and the boilerplate includes.                                                      |
| `releases/<version>/`                                                     | A release: a snapshot of a draft, never edited again. There is none yet.                                                                                                                                                                        |
| `assets/`                                                                 | The logo, used by every published page.                                                                                                                                                                                                         |
| `schema/registry.schema.json`                                             | The schema of `requirements.json`, the list of classes, requirements, and tests that the build publishes next to each version.                                                                                                                  |
| `tools/build.py`                                                          | Checks every version and builds `site/`. The code is the package `tools/specbuild/`, one module per concern, with its unit tests in `tools/tests/`.                                                                                             |
| `tools/release.py <version>`                                              | Cuts a release from the draft of its major version.                                                                                                                                                                                             |
| `tools/conformance.py <version> --linter '<cmd>'`                         | Runs the conformance tests against a linter.                                                                                                                                                                                                    |
| `tools/schema-check.cjs <version>`                                        | Checks every ruleset fixture against the schema.                                                                                                                                                                                                |
| `package.json`, `package-lock.json`, `requirements.txt`, `pyproject.toml` | The pinned Node and Python dependencies of the tools, and Ruff's settings.                                                                                                                                                                      |
| `.github/workflows/check.yml`, `publish.yml`                              | `check.yml` lints and tests the tools, builds every version, checks the schema, and runs each draft's conformance tests against OpenLint and Spectral. `publish.yml` deploys the site that a passing Check run on `main` built to GitHub Pages. |
| `.github/dependabot.yml` | Weekly update pull requests for the npm and Python dependencies and the workflow actions. |
| `site/`                                                                   | Build output, the shape of `spec.openlint.org`. Never edited, never committed.                                                                                                                                                                  |

Each major version has a working draft in a folder of its own, such as `v1/` for 1.x. So far there is only `v1/`. You edit these files in it:

- `index.bs` is the working draft, in Bikeshed's Markdown-flavored source.
- `conformance/<topic>/<name>/` holds one conformance test per directory.
- `formats.json` lists the format identifiers and how each is detected.
- `ruleset.schema.json` is the ruleset schema of that major version. It is normative, and the property tables in the document are generated from its descriptions.
- `header.include` and `copyright.include` hold the boilerplate. You rarely need to change them.

The build generates the rest: the headers of requirement blocks, the property tables, the formats table, Appendix A, Appendix B, the list of requirements the schema cannot check in Appendix D, each version's `requirements.json`, and all of `site/`. Never edit `site/` or anything under `releases/`.

### Install the tools

Once, from the repository root, with Python 3.10 to 3.13 (CI uses 3.13; Bikeshed's `lxml` has no wheel for newer versions yet, so pip would try to compile it) and Node 24:

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/bikeshed update
npm ci
```

`requirements.txt` pins the Bikeshed and Ruff versions, and `package.json` pins the JSON Schema validator that the schema check uses. The build finds Bikeshed in `.venv/`, on your `PATH`, or in `~/.local/bin`, where pipx installs it.

### Build and check

Run these from the repository root. Name a draft by its folder, such as `v1`, and a release by its version, such as `1.0.0`.

| Command                                        | What it does                                                                                                                         |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `tools/build.py`                               | Checks every version and builds `site/`.                                                                                             |
| `tools/build.py --check`                       | Runs every check, Bikeshed's included, and writes nothing.                                                                           |
| `tools/build.py v1`                            | Builds the 1.x draft only.                                                                                                           |
| `node tools/schema-check.cjs v1`               | Validates every ruleset fixture of the 1.x draft against its schema. Run it after a build.                                           |
| `tools/conformance.py v1 --linter '<command>'` | Runs the conformance tests of the 1.x draft against a linter. See [Run the tests against a linter](#run-the-tests-against-a-linter). |

When a check fails, the build prints the problem with its file and line and exits with a nonzero status. It also fails on a link that Bikeshed cannot resolve. To read the result, open `site/index.html`, or run `python3 -m http.server -d site 8000` to see the pages at the paths they would have when published.

After changing a tool, run `.venv/bin/ruff check tools/` and `python3 -m unittest discover -s tools/tests`.

### What CI runs

On every pull request, `.github/workflows/check.yml` lints and tests the tools, builds every version, checks the schema, and runs each draft's conformance tests against both linters. It builds OpenLint at the commit pinned in that workflow, so update the commit when the draft follows a newer OpenLint. On `main`, `.github/workflows/publish.yml` then deploys the `site/` that run built to GitHub Pages, and only when every check passed.

## Write the document

### Where text belongs

The document has these parts, in this order:

- **Introduction, Conformance, and Terminology.** How to read the document, the conformance classes, and the defined terms.
- **The ruleset format** (part 4). It follows the order of a ruleset document: the document itself, the Ruleset Object and its properties, then the Rule Object and its properties.
- **Documents** (part 5). What a linter lints, and what happens to a document before any rule runs: parsing, reference resolution, and formats.
- **Linting** (part 6). What a linter does, in pipeline order: load the ruleset, read the document, apply overrides, work out the rule state, select documents, select nodes, apply functions, and report results.
- **Functions** (part 7). The core functions and custom functions.
- **Security and privacy considerations**, then **Appendices A to E**: the requirements index, the conformance tests, the changes since the last release, using the schema, and provenance.

Part 4 holds only `ruleset` requirements. Parts 5, 6, and 7 hold only `linter` requirements. The build fails when a requirement sits in a part of the other target.

A section opens with informative text on what the thing is and how it works. Its requirements follow. The reason for a requirement goes in the paragraph just before it. Examples and issues sit next to the requirement they belong to.

Section 6.1 introduces a running example: a base ruleset, a project ruleset that extends it, and one document. Each later section of Linting shows what happens to that example at its stage. The example is also the conformance test `/conf/linter/walkthrough`, and the example blocks show its fixtures. When you change a Linting section, check that its part of the example still holds.

The core functions double as user documentation, so a ruleset author reads these sections on their own. Each section has, in this order:

1. One sentence on what the function asserts, and one on when to use it.
2. "It applies to ...", naming the values the function checks.
3. The options table, or "This function takes no options."
4. One requirement, `/req/functions/<name>`.
5. An example rule.

### Style

- Call each thing by one name, the defined term where there is one.
- Write headings in sentence case. Object names such as Ruleset Object keep their capitals.
- Write emphasis with asterisks, `*text*`. Bikeshed prints `_text_` with its underscores, and the build fails on it. If your editor rewrites asterisks to underscores on save, turn that off for `.bs` files.
- Link a section with `[[#id]]` or `[[#id|text]]`. Link a requirement with `<a href="#/req/given/no-match">/req/given/no-match</a>`, because Bikeshed does not parse `[[#/req/...]]`.
- Link a discussion as `<a href="https://github.com/orgs/openlint/discussions/12">discussion #12</a>`. The build fails on a bare "discussion #12".

### Requirement and class blocks

Bikeshed has no notion of an identified requirement. Requirements, recommendations, permissions, and conformance classes are HTML blocks with data attributes, and the build expands them before Bikeshed runs.

| Block                                    | Identifier            | Keywords                                         | Tests                                                        |
| ---------------------------------------- | --------------------- | ------------------------------------------------ | ------------------------------------------------------------ |
| `<div class=req>`, a requirement         | `/req/<topic>/<name>` | MUST, MUST NOT, SHALL, SHALL NOT, REQUIRED       | At least one, as [the test rules](#the-test-rules) describe. |
| `<div class=rec>`, a recommendation      | `/rec/<topic>/<name>` | SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED | None. The build rejects a test for a recommendation.         |
| `<div class=per>`, a permission          | `/per/<topic>/<name>` | MAY, OPTIONAL                                    | At least one that shows the permitted thing is accepted.     |
| `<div class=class>`, a conformance class | `/conf/<name>`        | None                                             | None.                                                        |

A requirement looks like this:

```html
<div
  class="req"
  id="/req/given/no-match"
  data-class="linter-core"
  data-since="1.0.0"
>
  A [=linter=] MUST NOT produce a [=result=] for a [=rule=] whose `given`
  matches no node in the [=document=].
</div>
```

- Put the opening tag and `</div>` each on a line of its own. Blocks do not nest.
- Set `data-class` to the conformance class. The class fixes the target, so a requirement has no target of its own.
- Leave `data-since` off a new requirement. `tools/release.py` adds it when it cuts the first release that contains the requirement.
- Leave `data-status` off a settled requirement. Set it to `proposed` for one that states behavior ahead of the implementations: its tests run but do not count in the conformance run, and a release refuses to include it, so a proposed requirement is a decision the community has to take before the next release. Set it to `removed`, with `data-removed=<version>`, for one that is withdrawn; a removed requirement stays listed. The value `example` keeps a block out of the registry, and only the sample block in "How to read this document" uses it.
- Give a class block `data-target`, either `ruleset` or `linter`, and `data-depends` with the names of the classes it depends on. Its body says what the class covers.

The identifier is the block's `id`, so `#/req/given/no-match` links to the requirement in every version that has it. It is permanent:

- `<topic>` is what the requirement is about, usually a ruleset key or a step of linting, such as `given`, `overrides`, or `result`. It is not a section of the document, so moving a block does not change its identifier.
- `<topic>` and `<name>` are lowercase words joined by hyphens.
- Never reuse an identifier, and never change what a requirement means under the same identifier. When a change alters what conforms, give the requirement a new identifier and mark the old one removed.

The build compares each draft with every release of its major version and of earlier ones. A released identifier that is missing from a draft fails the build, and so does one whose kind or target changed. A released requirement whose text changed in the draft of its major version is reported, and you decide whether the change alters what conforms. The form of identifiers is an open question in the draft, so it can still change.

### Requirements

**Make each requirement one testable statement about one target.** The target is the subject: "A [=linter=] MUST ..." or "A [=ruleset=] MUST ...". Two sections take the thing the requirement constrains as subject instead, because that reads better: a core function's requirement, "`truthy` MUST fail when ...", and a result's, "The `code` of a [=result=] MUST be ...". A sentence without a keyword is allowed inside a block only to define a term the keyword sentence uses, such as which regular expression dialect `match` is written in. A rule of its own gets a keyword.

**Use BCP 14 keywords in capitals only inside blocks, and only those of the block's kind.** The build fails on a keyword in capitals anywhere else. In informative text, write "has to" and "can". Avoid a lowercase "must" or "may" that a reader could take for a requirement.

**Use the defined terms.** Link a term with `[=term=]`. Define a new term with `<dfn>` in Terminology. Bikeshed fails the build on a link to a term that does not exist.

**State the format as it behaves today.** The draft describes the format as Spectral and OpenLint behave, and every test passes against both. Probe both linters before you write a requirement. When the behavior could be better, write the requirement as the behavior is, and propose the change in an issue next to it.

**Leave structure to the schema.** `/req/ruleset/schema` makes the ruleset schema normative, so the structure of a ruleset lives there. Write a ruleset requirement only for what a JSON Schema cannot express, such as a name that has to refer to something declared elsewhere, a cycle, or the options of a named function. The build lists those requirements in Appendix D.

**State a constraint once.** A constraint on rulesets is a ruleset requirement. A linter's duties toward all of them are `/req/linter/reject-invalid` and `/req/linter/accept-valid`, so a ruleset constraint never gets a linter twin. The one exception is what a linter checks in an override only for the documents the override applies to, which is `/req/overrides/checked-when-applied`.

**Name no implementation.** Spectral and OpenLint appear only in issues and in the provenance appendix, and an issue says OpenLint, not "the reference implementation". The build fails on a mention anywhere else, including schema descriptions and test purposes. Identifiers that rulesets use, such as `spectral:oas`, are not mentions.

**Name a programming language only where the format takes something from it.** A requirement can pin semantics the format borrows from a language, such as the ECMAScript regular expressions of `pattern`. A language binding names its language, such as the JavaScript binding of custom functions. Nowhere else does the text assume what a linter is written in.

**Pin references.** `[[!RFC8259]]` is a normative reference and `[[RFC9535]]` an informative one. When Bikeshed's bibliography lacks the exact version, add an entry to the `<pre class=biblio>` block at the top of `index.bs`.

### Issues and notes

Start a paragraph with `Issue:` for an open question or a proposed change. Bikeshed collects issues into the issues index.

- Issues live only in the drafts. `tools/release.py` refuses to cut a release while one remains. Before a release, resolve each issue in the text, or turn it into a note that states the accepted limitation.
- When you resolve the last issue in a draft, also rewrite the sentence in "How to read this document" that links to the issues index. Bikeshed generates the index only while issues remain, so the build and `tools/release.py` fail on the link until you do.
- An issue that proposes a breaking change cannot be resolved in its own major version. Before that major version's next release, turn it into a note there, and resolve the issue in the later draft.
- An issue that proposes a change says what happens today, then what the change would do: "`then: []` is accepted, and the rule then asserts nothing and never reports a result. Rejecting an empty array would catch a rule left unfinished."
- An issue can name the implementation whose behavior it describes.

Start a paragraph with `Note:` for a remark a reader could otherwise miss, such as two places that write severities differently. The reason for a requirement is not a note. It goes in the paragraph before the requirement.

### Examples

Put an example in `<div class=example>` with a fenced code block. YAML is the default highlighting. Give rules descriptive names, such as `operation-summary`, so the example reads as a real ruleset. Test fixtures can use short names such as `r`.

An example that shows a fixture names the file in `data-fixture`, relative to the draft's folder. The build fails when the example and the file differ, so copy the file into the example:

````html
<div class="example" data-fixture="conformance/linter/walkthrough/ruleset.yaml">
  ```yaml extends: ./acme-base.yaml ... ```
</div>
````

### Tables generated from the schema

Each draft's schema, `v<major>/ruleset.schema.json`, is written in JSON Schema 2020-12. Its `$id` is the URL it is published at, such as `https://spec.openlint.org/v1/draft/ruleset.schema.json`. A release's copy takes the release's URL, such as `https://spec.openlint.org/1.0.0/ruleset.schema.json`, so the schema of each release has an identity of its own. The build fails when a schema's `$id` differs from its URL. `/v<major>/ruleset.schema.json` serves the schema of the latest release of a major version, for editors that follow the newest release; until that major version has a release, it serves the draft's schema.

To show the properties of an object, put a table marker on a line of its own. `data-def="#"` is the root object, and any other value names a definition under `$defs`:

```html
<div class="schema-table" data-def="Rule"></div>
```

The build generates the table from the schema, so the descriptions in the schema are text of the specification:

- Every property needs a `description`. The build fails without one.
- Write each description as informative text: whole sentences, no BCP 14 keywords, and no implementation names.
- The Type column gives the JSON type. When a section of the document defines the value, the cell links to it with "see", and the detail lives there, not in the table.
- When you add a definition that a table links to, add it to `DEF_SECTIONS` in `tools/specbuild/schema_tables.py`. That map links each definition to the section that explains it.

The `format` enum in the schema and `formats.json` list the same identifiers. The build generates the formats table from `formats.json`, with each identifier's detection condition, and fails when the two differ.

The schema always matches the specification. A change to the schema and the matching change to the text go in the same pull request. After you change the schema, run `schema-check.cjs`. Every ruleset fixture has to keep its verdict, and CI runs the same check on every pull request.

## Write tests

### Tests as data

Every requirement has tests, and every test is data. The build renders Appendix B, and the test list in each requirement block, from the same files that `tools/conformance.py` runs.

A test is a directory, `conformance/<topic>/<name>/` in the draft's folder, and its identifier is `/conf/<topic>/<name>`. Its topic is the ruleset key or linting step the test exercises, which can differ from its requirements' topic: most tests of `/req/ruleset/schema` are filed under the key they check. The directory holds `test.json` and the fixtures. A test for a ruleset requirement expects the ruleset to be valid or invalid:

```json
{
  "for": ["/req/given/alias-defined"],
  "purpose": "A rule referencing an alias the ruleset does not declare is invalid.",
  "ruleset": "ruleset.yaml",
  "expect": { "ruleset": "invalid" }
}
```

A test for a linter requirement expects results, or expects the linter to reject the ruleset:

```json
{
  "for": ["/req/result/severity"],
  "purpose": "A rule with `severity: hint` reports `severity: 3`.",
  "ruleset": "ruleset.yaml",
  "document": "document.yaml",
  "expect": { "results": [{ "severity": 3 }, { "severity": 3 }] }
}
```

| Field      | Meaning                                                                                                                                                        |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `for`      | The requirements the test covers. They all belong to one class.                                                                                                |
| `purpose`  | One sentence that says what conforms.                                                                                                                          |
| `ruleset`  | The ruleset fixture. The default is `ruleset.yaml`.                                                                                                            |
| `document` | The document fixture, for a linter test. A ruleset test has none, and the runner lints an empty document.                                                      |
| `files`    | Other fixtures the test needs, such as an extended ruleset or a custom function.                                                                               |
| `expect`   | `{"ruleset": "valid"}`, `{"ruleset": "invalid"}`, `{"rejected": true}`, or `{"results": [...]}`, with `"ordered": true` when the order of the results matters. |

The linter has to produce as many results as `results` lists. Each listed entry has to match one actual result on the fields the entry names. `"has"` lists fields that have to be present, whatever their value. `"${document}"` stands for the absolute path of the document fixture. Fixture names are paths inside the test directory; a name that leaves it, or a symbolic link, fails the build.

Write the purpose as one sentence in the present tense that states the outcome, such as "A rule whose `given` is an object is invalid." Name no implementation in it.

You never order or group tests by hand. The build lists each requirement's tests with the conforming side first. It groups a list of more than ten tests by section when the tests come from several sections.

### The test rules

1. A ruleset requirement has at least one invalid test and at least one valid test. The invalid fixture violates the requirement and is rejected. The valid fixture uses the same property and is loaded.
2. A linter requirement has at least one test that expects results, because a linter that does nothing passes a test that expects none. When a requirement says that something does not happen, add a control test in which the same mechanism produces results.
3. A permission has a test in which a fixture uses what is permitted and is accepted. Where a requirement forbids the same thing elsewhere, add a test that puts it there and is rejected.
4. An invalid fixture violates one requirement only, so that its rejection proves that requirement and not another.
5. A recommendation has no test.

The build fails when a requirement lacks the tests that rule 1 or rule 2 asks for, and when a permission has no test that accepts it. `tools/schema-check.cjs` checks rule 4 against the schema:

- For a test of `/req/ruleset/schema`, the schema's verdict has to equal the expectation.
- Every other ruleset fixture that parses has to pass the schema. Otherwise an invalid fixture for another requirement would violate the schema requirement too.
- The ruleset of a linter test that expects it to load has to pass the schema.

### Run the tests against a linter

The conformance runner takes the linter as a command template. `{ruleset}` and `{document}` stand for the fixture paths, and a relative path in the command is taken from the directory you run it in. Before the tests, the runner checks that the linter prints results for a ruleset every linter has to load, and stops when it does not.

```sh
# OpenLint, after `yarn && yarn build` in a checkout of openlint/openlint next to this one
tools/conformance.py v1 --linter 'node ../openlint/packages/cli/dist/index.js lint -r {ruleset} -f json {document}'

# Spectral, after `npm install @stoplight/spectral-cli@6.17.0` in a scratch directory (the version CI pins)
tools/conformance.py v1 --linter 'node <scratch>/node_modules/@stoplight/spectral-cli/dist/index.js lint -r {ruleset} -f json {document}'
```

A full run takes about ten minutes per linter. While you work, add `--only <prefix>` to run only the tests whose identifier starts with that prefix, such as `--only /conf/given`.

Run a new test against both linters before you rely on it. A test that fails on either linter means that the test or the requirement is wrong, because the draft states the current behavior. Tests of a `proposed` requirement are the exception: the runner reports them and does not count them.

## Manage versions

### Several drafts

This section applies once there is more than one draft. Most changes apply to every major version: a clarification, a fixed test, or a new feature that keeps existing rulesets valid. Make such a change in each draft, in the same pull request.

A change that breaks what an earlier major version allows goes into the later draft only:

- To change what a requirement means in 2.x, mark it `data-status=removed` with `data-removed="2.0.0"` in `v2/index.bs`, and add the new behavior under a new identifier.
- To leave a requirement out of 2.x, mark it removed in `v2/index.bs` the same way. Never delete it from a later draft.
- To add something to 2.x only, add it to `v2/` alone.

The community has not agreed yet on what counts as a breaking change.

The build checks that no change is missed:

- Every requirement of a draft is in the next draft, current or removed, and a removed requirement stays removed.
- A requirement that both drafts list as current has the same kind, class, status, and source text in both. Otherwise the build fails and names the line in each draft.
- A test that differs between the drafts, or that the later draft lacks, is reported.

The build does not compare informative text. To see every difference between two drafts, run `diff v1/index.bs v2/index.bs`. Apart from what 2.x changes on purpose, the drafts differ only where they name their major version: the metadata, the schema URLs in Appendix D, and the schema's `$id`.

### Start a new major version

Start the next draft only when the community accepts the first change that breaks the current major version. To start it:

1. Copy the latest draft folder, such as `v2/` to `v3/`.
2. Set the `$id` in the new `ruleset.schema.json` to the URL the draft's schema is published at, such as `https://spec.openlint.org/v3/draft/ruleset.schema.json`. The build fails until you do.
3. In the new `index.bs`, update every place that names the major version: `ED`, the `VERSIONLABEL` text macro, `Custom Warning Text`, and the schema URLs in Appendix D. A `diff` with the old draft shows these places.

The build finds the new draft by its folder name and publishes it at `/v<major>/draft/`.

### Cut a release

A release is a snapshot under `releases/<version>/`, and nobody edits it again. A fix ships as a new patch release.

To cut a release, run `tools/release.py <version>`. It cuts the release from the draft of its major version, such as `1.1.0` from `v1/` and `2.0.0` from `v2/`. The tool does these steps in order:

1. It runs every check of the build, Bikeshed included, and refuses when an issue or a `proposed` requirement remains.
2. It adds `data-since="<version>"` to every requirement in the draft that has none, and to the same requirements in every later draft.
3. It copies `index.bs`, the includes, `formats.json`, `conformance/`, and `ruleset.schema.json` into `releases/<version>/`. It rewrites the copy's metadata with the version label, the date, its own URL, a link to the draft, and no draft warning, and sets the schema's `$id` to the release's URL.
4. It points "Previous Version" and "Latest release" at the new release, in the draft of its major version and in every later draft whose major version has no release yet.

It refuses to overwrite a release that exists. Record what changed since the last release in Appendix C of the draft.

## Before you open a pull request

1. Run `tools/build.py`, and fix every problem it reports.
2. Run `node tools/schema-check.cjs v1`, and again for every other draft.
3. Run the tests you added or changed against OpenLint and Spectral with `--only`.
4. After changing a tool, run `.venv/bin/ruff check tools/` and `python3 -m unittest discover -s tools/tests`.
5. Read the sections you changed in `site/v1/draft/index.html`.
6. Say in the pull request how AI was used, if it was.
