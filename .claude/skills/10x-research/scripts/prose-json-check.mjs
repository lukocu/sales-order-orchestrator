#!/usr/bin/env node
/**
 * Detect JSON number and boolean leaves that never appear in the research prose.
 *
 * No dependencies. Reads only the two paths given. JSON on stdout; a refusal or the
 * missing-leaf report on stderr with exit code 1.
 *
 * This is an absence detector, not a consistency proof: a token found anywhere as a
 * substring says nothing about the sentence around it, and nothing here parses Markdown
 * structure or checks quantifiers. A clean run only means no leaf is plainly missing.
 *
 * Usage:
 *   prose-json-check.mjs <research.md> <facts.json>
 */
import { readFileSync } from "node:fs";

const USAGE = "Usage: prose-json-check.mjs <research.md> <facts.json>";

class CheckError extends Error {}

/** Lists flatten onto their parent's path; strings, null and empty containers carry no token. */
function* leaves(value, prefix = "") {
  if (Array.isArray(value)) {
    for (const item of value) yield* leaves(item, prefix);
  } else if (value !== null && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      yield* leaves(child, prefix + (prefix ? "." : "") + key);
    }
  } else if (typeof value === "boolean") {
    yield { path: prefix, token: value ? "true" : "false" };
  } else if (typeof value === "number") {
    // An integral float serializes without a trailing `.0`, so 4.0 is sought in prose as "4".
    yield { path: prefix, token: String(value) };
  }
}

function read(path, label) {
  try {
    return readFileSync(path, "utf8");
  } catch (error) {
    throw new CheckError(`Cannot read ${label}: ${error.message}`);
  }
}

function parseArguments(argv) {
  if (argv.length !== 2) throw new CheckError(USAGE);
  for (const path of argv) {
    if (path.startsWith("--")) throw new CheckError(`Unsupported option: ${path}\n${USAGE}`);
  }
  return { prosePath: argv[0], factsPath: argv[1] };
}

function main() {
  try {
    const { prosePath, factsPath } = parseArguments(process.argv.slice(2));
    const prose = read(prosePath, "research document");
    const raw = read(factsPath, "facts file");
    let data;
    try {
      data = JSON.parse(raw);
    } catch (error) {
      throw new CheckError(`Cannot parse facts file: ${error.message}`);
    }
    const missing = [];
    let checked = 0;
    for (const leaf of leaves(data)) {
      checked += 1;
      if (!prose.includes(leaf.token)) missing.push(leaf);
    }
    if (missing.length) {
      process.stderr.write(`${JSON.stringify({ ok: false, missing })}\n`);
      process.exitCode = 1;
      return;
    }
    console.log(JSON.stringify({ ok: true, checked }));
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}

main();
