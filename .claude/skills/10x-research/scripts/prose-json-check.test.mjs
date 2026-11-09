/** Tests for the bounded prose/JSON leaf checker, driven through its real entry point: a node process. */
import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const checker = fileURLToPath(new URL("./prose-json-check.mjs", import.meta.url));

let root;

function check(prose, facts) {
  const prosePath = join(root, "research.md");
  const factsPath = join(root, "facts.json");
  writeFileSync(prosePath, prose);
  writeFileSync(factsPath, typeof facts === "string" ? facts : JSON.stringify(facts));
  return spawnSync(process.execPath, [checker, prosePath, factsPath], { encoding: "utf8" });
}

function missingByPath(result) {
  return Object.fromEntries(JSON.parse(result.stderr).missing.map((row) => [row.path, row.token]));
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "10x-prose-json-check-"));
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

test("a number and a boolean absent from the prose are both reported", () => {
  const result = check("HTTP retries four times. Queue does not forward Retry-After.", {
    http: { max_attempts: 4 },
    queue: { retry_after_forwarded: false },
  });
  assert.equal(result.status, 1);
  const missing = missingByPath(result);
  assert.equal(missing["http.max_attempts"], "4");
  assert.equal(missing["queue.retry_after_forwarded"], "false");
});

test("leaves present in the prose pass and are counted", () => {
  const result = check("http.max_attempts is 4 and retry_after_forwarded is false.", {
    http: { max_attempts: 4 },
    queue: { retry_after_forwarded: false },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), { ok: true, checked: 2 });
});

test("list items flatten onto the parent path", () => {
  const result = check("Two of the three ports are open: 80 and 443.", { ports: [80, 443, 8080] });
  assert.equal(result.status, 1);
  assert.deepEqual(JSON.parse(result.stderr).missing, [{ path: "ports", token: "8080" }]);
});

test("an integral float is sought as a bare integer and strings carry no token", () => {
  const result = check(
    "The timeout is 30 seconds and the sampled ratio is 0.5.",
    '{"timeout_s": 30.0, "ratio": 0.5, "note": "never checked"}',
  );
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), { ok: true, checked: 2 });
});

test("an unreadable facts file is refused instead of counted as clean", () => {
  writeFileSync(join(root, "research.md"), "# Research\n");
  const result = spawnSync(
    process.execPath,
    [checker, join(root, "research.md"), join(root, "absent.json")],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Cannot read facts file/);
  assert.equal(result.stdout, "");
});

test("malformed JSON is refused instead of counted as clean", () => {
  const result = check("# Research\n", "{not json");
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Cannot parse facts file/);
  assert.equal(result.stdout, "");
});

test("the checker takes exactly two paths", () => {
  const result = spawnSync(process.execPath, [checker, join(root, "research.md")], {
    encoding: "utf8",
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Usage: prose-json-check\.mjs/);
});
