# OpenLint Specification

**The specification and JSON Schema for OpenLint rulesets: the Spectral ruleset format, specified on its own.**

A ruleset says where to look in a JSON or YAML document and what must hold there. Organizations publish their API style guides, security baselines and design standards as rulesets, then run them in CI against every OpenAPI, AsyncAPI, Arazzo and JSON Schema document they ship.

The format has never been specified. It existed only as configuration for one linter, versioned with that tool. This repository treats the ruleset as an artifact in its own right: an independently versioned specification with a portable JSON Schema, so rules can be written, validated, shared and run by any tool.

| | |
| -- | -- |
| **Specification** | [SPECIFICATION.md](SPECIFICATION.md) |
| **JSON Schema** | [`schema/v1/ruleset.schema.json`](schema/v1/ruleset.schema.json) (draft 2020-12), served at `https://openlint.org/schema/v1/ruleset.schema.json` |
| **Reference implementation** | [openlint/openlint](https://github.com/openlint/openlint) |
| **Website** | [openlint.org/spec](https://openlint.org/spec/) |

> **Status: draft.** The document describes the format as implemented today, faithfully and without extension. It is not yet a formal specification. The `v1` schema identity is stable: see [Versioning](SPECIFICATION.md#versioning).

## Validate a ruleset

```bash
npx ajv-cli validate --spec=draft2020 \
  -s schema/v1/ruleset.schema.json \
  -d .spectral.yaml
```

Editor setup is in [Using the schema](SPECIFICATION.md#using-the-schema).

## What this format is for

**Governing structured documents, not only OpenAPI.** A rule selects nodes in a JSON or YAML document with a path expression and asserts something about them. Nothing in that is specific to APIs, and the format is already used on CI workflows, Kubernetes manifests and other configuration. Support for documents that aren't API descriptions is a goal, and a change that's correct only for API descriptions is a defect. Which document types to support is being discussed in [#5](https://github.com/orgs/openlint/discussions/5).

## Why this is separate from the linter

When the format ships only as part of one linter, it stops moving when the linter does. A team's governance rules usually outlast the CLI, the vendor, and often the API itself. So the rules stand on their own: specified, versioned independently, and implementable by anyone. The reference implementation follows this document, and other engines, such as [vacuum](https://github.com/daveshanley/vacuum), are welcome to implement it too. A written specification with a public conformance suite is what lets several engines agree.

## Work in progress

| Topic | Discussion |
| -- | -- |
| Formalizing the specification: normative language, requirement IDs, conformance tests | [#13](https://github.com/orgs/openlint/discussions/13) |
| Backwards compatibility: what we promise, and to whom | [#12](https://github.com/orgs/openlint/discussions/12) |
| Document types ("formats") | [#5](https://github.com/orgs/openlint/discussions/5) |
| Aliases | [#2](https://github.com/orgs/openlint/discussions/2) |
| Rules testing | [#7](https://github.com/orgs/openlint/discussions/7) |

## Where things go

| What | Where |
| -- | -- |
| Problems with the format, the schema or this document | [openlint/spec issues](https://github.com/openlint/spec/issues) |
| Problems with the linter | [openlint/openlint issues](https://github.com/openlint/openlint/issues) |
| Ideas, direction and questions | [OpenLint discussions](https://github.com/orgs/openlint/discussions) |

The most useful contribution is a ruleset that behaves differently from what this document says. That's a bug in the specification.

## Provenance and license

The format originates in [Spectral](https://github.com/stoplightio/spectral) by Stoplight, licensed Apache-2.0. The specification and schema were derived from Spectral's internal validation meta-schemas and guides, first published by the Spotlight effort at [api-commons/spotlight-spec](https://github.com/api-commons/spotlight-spec), and carried over here when the project took the OpenLint name.

Licensed [Apache-2.0](LICENSE). Everyone taking part follows the [OpenLint Code of Conduct](https://github.com/openlint/.github/blob/main/CODE_OF_CONDUCT.md).
