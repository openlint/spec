# OpenLint Specification

**The specification and JSON Schema for OpenLint rulesets: the Spectral ruleset format, specified on its own.**

A ruleset is a set of rules for checking JSON and YAML documents. Each rule selects values in a document with a JSONPath expression and checks each selected value with a function. Organizations publish their API style guides, security baselines and design standards as rulesets, then run them in CI against every OpenAPI, AsyncAPI, Arazzo and JSON Schema document they ship.

The format has never been specified. It existed only as configuration for one linter, versioned with that tool. This repository treats the ruleset as an artifact in its own right: an independently versioned specification with a portable JSON Schema and conformance tests, so rules can be written, validated, shared and run by any linter.

|                              |                                                                                                                                                |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Specification**            | [`v1/index.bs`](v1/index.bs), the working draft of 1.x. It will be published at `https://spec.openlint.org/v1/draft/`, which is not served yet |
| **JSON Schema**              | [`v1/ruleset.schema.json`](v1/ruleset.schema.json) (draft 2020-12)                                                                             |
| **Conformance tests**        | [`v1/conformance/`](v1/conformance/), one directory per test                                                                                   |
| **Reference implementation** | [openlint/openlint](https://github.com/openlint/openlint)                                                                                      |
| **Website**                  | [openlint.org/spec](https://openlint.org/spec/)                                                                                                |

> **Status: working draft.** The specification states the format as Spectral and OpenLint behave today, as identified requirements with conformance tests that pass against both. Where that behavior could be better, an issue in the draft proposes the change. There is no release yet.

## Versions

Each release will live at its own URL that never changes, such as `https://spec.openlint.org/1.0.0/`, with its schema at `https://spec.openlint.org/1.0.0/ruleset.schema.json`. A fix ships as a new patch release. Each major version has a working draft in a folder of its own, published at `https://spec.openlint.org/v<major>/draft/`.

`https://spec.openlint.org/v1/` will serve the latest 1.x release. Editors that follow the newest release can point at `https://spec.openlint.org/v1/ruleset.schema.json`. Until 1.0.0 is released, it serves the draft's schema. Each schema's `$id` is the URL it is published at, so the schema of every release has an identity of its own.

Within a major version, changes are additive and backward-compatible: new optional properties, newly registered format identifiers, clarified descriptions. A change that rejects a previously valid ruleset goes into the draft of the next major version. What counts as a breaking change is discussed in [#12](https://github.com/orgs/openlint/discussions/12).

## Validate a ruleset

```bash
npx ajv-cli validate --spec=draft2020 --strict=false \
  -s v1/ruleset.schema.json \
  -d ruleset.yaml
```

Editor setup is in Appendix D of the draft, Using the schema.

## Contribute

[CONTRIBUTING.md](CONTRIBUTING.md) explains the layout of this repository, how to build and check the draft, how to write requirements, issues, and tests, and how to run the conformance tests against a linter.

## What this format is for

**Governing structured documents, not only OpenAPI.** A rule selects nodes in a JSON or YAML document with a path expression and asserts something about them. Nothing in that is specific to APIs, and the format is already used on CI workflows, Kubernetes manifests and other configuration. Support for documents that aren't API descriptions is a goal, and a change that's correct only for API descriptions is a defect. Which document types to support is being discussed in [#5](https://github.com/orgs/openlint/discussions/5).

## Why this is separate from the linter

When the format ships only as part of one linter, it stops moving when the linter does. A team's governance rules usually outlast the CLI, the vendor, and often the API itself. So the rules stand on their own: specified, versioned independently, and implementable by anyone. The reference implementation follows this document, and other linters, such as [vacuum](https://github.com/daveshanley/vacuum), are welcome to implement it too. A written specification with a public conformance suite is what lets several linters agree.

## Work in progress

| Topic                                                            | Discussion                                             |
| ---------------------------------------------------------------- | ------------------------------------------------------ |
| Formalizing the specification: the principles this draft applies | [#13](https://github.com/orgs/openlint/discussions/13) |
| Backwards compatibility: what we promise, and to whom            | [#12](https://github.com/orgs/openlint/discussions/12) |
| Document types ("formats")                                       | [#5](https://github.com/orgs/openlint/discussions/5)   |
| Aliases                                                          | [#2](https://github.com/orgs/openlint/discussions/2)   |
| Rules testing                                                    | [#7](https://github.com/orgs/openlint/discussions/7)   |

## Where things go

| What                                                  | Where                                                                   |
| ----------------------------------------------------- | ----------------------------------------------------------------------- |
| Problems with the format, the schema or this document | [openlint/spec issues](https://github.com/openlint/spec/issues)         |
| Problems with the linter                              | [openlint/openlint issues](https://github.com/openlint/openlint/issues) |
| Ideas, direction and questions                        | [OpenLint discussions](https://github.com/orgs/openlint/discussions)    |

The most useful contribution is a ruleset that behaves differently from what this document says. That's a bug in the specification.

## Provenance and license

The format originates in [Spectral](https://github.com/stoplightio/spectral) by Stoplight, licensed Apache-2.0. The specification and schema were derived from Spectral's internal validation meta-schemas and guides, first drafted by the OpenLint community, before it took its name, in [api-commons](https://github.com/api-commons/spotlight-spec), and moved here.

Licensed [Apache-2.0](LICENSE). Everyone taking part follows the [OpenLint Code of Conduct](https://github.com/openlint/.github/blob/main/CODE_OF_CONDUCT.md).
