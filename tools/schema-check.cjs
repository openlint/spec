#!/usr/bin/env node
// Validates the ruleset fixtures of a version against the ruleset schema of that version.
//
// Usage: node tools/schema-check.cjs <version> [node_modules dir with ajv, ajv-formats, yaml]
//   npm ci && node tools/schema-check.cjs v1
//
// Run tools/build.py first: the registry it writes says which fixtures exist and what they
// cover. /req/ruleset/schema makes the schema normative, so for a test of that requirement the
// schema has to give the expected verdict. Every other ruleset fixture has to pass the schema:
// a valid one because it is a valid ruleset, an invalid one because it is meant to violate a
// requirement the schema cannot express, and a fixture the schema rejects would violate two.
// A fixture that does not parse is outside what the schema can judge. The ruleset of a linter
// test that expects the ruleset to load has to pass the schema too. A YAML file with several
// documents is judged by its first document; that it has several is beyond the schema.
const fs = require('fs'), path = require('path');
const SCHEMA_REQUIREMENT = '/req/ruleset/schema';
const root = path.resolve(__dirname, '..');
const [version, nm = path.join(root, 'node_modules')] = process.argv.slice(2);
if (!version) { console.error('usage: node tools/schema-check.cjs <version> [node_modules dir]'); process.exit(2); }
const req = name => require(path.resolve(nm, name));
const Ajv2020 = req('ajv/dist/2020').default, addFormats = req('ajv-formats'), yaml = req('yaml');
const draft = /^v[1-9][0-9]*$/.test(version);
const site = draft ? path.join(root, 'site', version, 'draft') : path.join(root, 'site', version);
const source = draft ? path.join(root, version) : path.join(root, 'releases', version);
if (!fs.existsSync(path.join(site, 'requirements.json'))) { console.error(`no build for ${version}: run tools/build.py first`); process.exit(2); }
const registry = JSON.parse(fs.readFileSync(path.join(site, 'requirements.json'), 'utf8'));
const ajv = new Ajv2020({ strict: false }); addFormats(ajv);
const validate = ajv.compile(JSON.parse(fs.readFileSync(path.join(site, 'ruleset.schema.json'), 'utf8')));
const fixture = (t, name) => {
  const dir = path.resolve(source, t.dir), file = path.resolve(dir, name);
  if (path.isAbsolute(name) || !file.startsWith(dir + path.sep)) throw new Error(`${t.id}: fixture ${name} leaves the test directory`);
  return file;
};
const documents = t => {
  const file = fixture(t, t.ruleset), text = fs.readFileSync(file, 'utf8');
  if (file.endsWith('.json')) {
    try { const data = JSON.parse(text); return [{ errors: [], toJSON: () => data }]; } catch { return [{ errors: ['invalid JSON'] }]; }
  }
  return yaml.parseAllDocuments(text);
};
const parses = docs => docs.length > 0 && docs.every(doc => doc.errors.length === 0);
const passes = docs => parses(docs) && validate(docs[0].toJSON());
const failures = [], counts = { schema: 0, beyond: 0, linter: 0 };
for (const t of registry.tests) {
  const docs = documents(t);
  if (t.target === 'ruleset' && t.for.includes(SCHEMA_REQUIREMENT)) {
    counts.schema++;
    const verdict = passes(docs) ? 'valid' : 'invalid';
    if (verdict !== t.expect.ruleset) failures.push(`${t.id}: expected ${t.expect.ruleset}, the schema says ${verdict}`);
  } else if (t.target === 'ruleset') {
    counts.beyond++;
    if (parses(docs) && !passes(docs)) failures.push(`${t.id}: the schema rejects this ${t.expect.ruleset} fixture for ${t.for.join(', ')}; it has to violate only what the schema cannot express`);
  } else if (!t.expect.rejected) {
    counts.linter++;
    if (!passes(docs)) failures.push(`${t.id}: the linter test expects its ruleset to load, but the schema rejects it`);
  }
}
console.log(`${version}: ${counts.schema + counts.beyond + counts.linter} ruleset fixtures checked against the schema`);
console.log(`  ${counts.schema} for ${SCHEMA_REQUIREMENT}, where the schema has to give the expected verdict`);
console.log(`  ${counts.beyond} for requirements beyond the schema, which have to pass it`);
console.log(`  ${counts.linter} from linter tests, which have to pass it`);
for (const f of failures) console.log(`  FAIL ${f}`);
process.exit(failures.length ? 1 : 0);
