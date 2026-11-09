/** Tests for the shared metadata guard, driven through its real entry point: a node process. */
import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const guard = fileURLToPath(new URL("./metadata-guard.mjs", import.meta.url));
const TODAY = "2026-09-19";
const CHANGE_ID = "delivery-retries";

let root;
let folder;

function sha(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function run(...args) {
  return spawnSync(process.execPath, [guard, ...args], { encoding: "utf8" });
}

function markResearched(target = folder, expected = sha(readFileSync(join(target, "change.md")))) {
  return run("mark-researched", target, "--expected-sha256", expected, "--date", TODAY);
}

function markPlanned(target = folder, expected = sha(readFileSync(join(target, "change.md")))) {
  return run("mark-planned", target, "--expected-sha256", expected, "--date", TODAY);
}

function write(name, contents) {
  writeFileSync(join(folder, name), contents);
}

function read(name = "change.md") {
  return readFileSync(join(folder, name), "utf8");
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "10x-metadata-guard-"));
  folder = join(root, CHANGE_ID);
  mkdirSync(folder);
  write("research.md", "# Research\n");
  write("plan.md", "# Plan\n");
  write("plan-brief.md", "# Brief\n");
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

test("existing identity fields are preserved while the owned fields advance", () => {
  write(
    "change.md",
    "---\n" +
      "change_id: delivery-retries\n" +
      "title: Inventory current retry behavior\n" +
      "status: preparing\n" +
      "created: 2026-09-09\n" +
      "updated: 2026-09-09\n" +
      "owner: platform\n" +
      "---\n" +
      "\n" +
      "## Notes\n" +
      "Keep this body.\n",
  );
  const result = markResearched();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).changed, true);
  const text = read();
  for (const line of [
    "change_id: delivery-retries",
    "title: Inventory current retry behavior",
    "created: 2026-09-09",
    "owner: platform",
    "status: preparing",
    "updated: 2026-09-19",
    "## Notes\nKeep this body.",
  ]) {
    assert.ok(text.includes(line), `missing ${line}`);
  }
  assert.ok(!text.includes("status: planned"));
});

test("missing owned fields are appended without dropping identity", () => {
  write(
    "change.md",
    "---\n" +
      "change_id: delivery-retries\n" +
      "title: Inventory current retry behavior\n" +
      "status: new\n" +
      "created: 2026-09-09\n" +
      "---\n",
  );
  assert.equal(markResearched().status, 0);
  const text = read();
  for (const line of [
    "change_id: delivery-retries",
    "title: Inventory current retry behavior",
    "created: 2026-09-09",
    "status: preparing",
    "updated: 2026-09-19",
  ]) {
    assert.ok(text.includes(line), `missing ${line}`);
  }
  assert.ok(text.startsWith("---\n"));
  assert.equal(text.split("---\n").length - 1, 2);
});

test("mark-planned advances a researched change and refreshes the date", () => {
  write(
    "change.md",
    "---\nchange_id: delivery-retries\nstatus: preparing\nupdated: 2026-09-09\n---\n",
  );
  assert.equal(markPlanned().status, 0);
  assert.equal(
    read(),
    "---\nchange_id: delivery-retries\nstatus: planned\nupdated: 2026-09-19\n---\n",
  );
});

test("mark-planned refuses while a required document is missing or empty", () => {
  write("change.md", "---\nchange_id: delivery-retries\nstatus: new\nupdated: 2026-09-09\n---\n");
  const raw = read();
  write("plan-brief.md", "");
  const result = markPlanned();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /plan-brief\.md/);
  assert.equal(read(), raw);
});

test("a stale fingerprint is refused and the file is left untouched", () => {
  const raw =
    "---\nchange_id: delivery-retries\nstatus: preparing\ncreated: 2026-09-09\nupdated: 2026-09-09\n---\n";
  write("change.md", raw);
  const result = markResearched(folder, "0".repeat(64));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Metadata changed since inspection/);
  assert.equal(read(), raw);
});

test("missing frontmatter is refused instead of reconstructed", () => {
  const raw = "# Delivery Retries\nbody\n";
  write("change.md", raw);
  const result = markResearched();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /frontmatter/i);
  assert.equal(read(), raw);
  assert.ok(!read().includes("created:"));
});

test("a change folder without change.md is refused, not created", () => {
  const result = markResearched(folder, "0".repeat(64));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /change\.md/);
  assert.match(result.stderr, /10x-new/);
  assert.equal(existsSync(join(folder, "change.md")), false);
});

test("inspect refuses a folder without change.md without leaking an absolute path", () => {
  const result = run("inspect", folder);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /change\.md/);
  assert.ok(!result.stderr.replace("/10x-new", "").includes("/"), result.stderr);
  assert.ok(!result.stderr.includes(root));
});

test("identity fields missing from existing frontmatter are refused", () => {
  const raw = "---\ntitle: Inventory current retry behavior\n---\n";
  write("change.md", raw);
  const result = markResearched();
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Missing identity\/status field/);
  assert.equal(read(), raw);
});

test("a later status is never downgraded by either command", () => {
  const raw =
    "---\nchange_id: delivery-retries\nstatus: implementing\ncreated: 2026-09-09\nupdated: 2026-09-09\n---\n";
  write("change.md", raw);
  for (const result of [markResearched(), markPlanned()]) {
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).changed, false);
  }
  assert.equal(read(), raw);
});

test("a non-ASCII status is read, left alone and reported without an error", () => {
  const raw = "---\nchange_id: delivery-retries\nstatus: zażółć\nupdated: 2026-09-09\n---\n";
  write("change.md", raw);
  const result = markPlanned();
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).changed, false);
  assert.equal(read(), raw);
});

test("CRLF metadata keeps its line endings", () => {
  write("change.md", "---\r\nchange_id: delivery-retries\r\nstatus: new\r\n---\r\n");
  assert.equal(markPlanned().status, 0);
  const text = read();
  assert.equal(
    text,
    "---\r\nchange_id: delivery-retries\r\nstatus: planned\r\nupdated: 2026-09-19\r\n---\r\n",
  );
  assert.ok(!/(^|[^\r])\n/.test(text));
});

test("inspect probes every target independently", () => {
  write("change.md", "---\nchange_id: delivery-retries\nstatus: new\n---\n");
  rmSync(join(folder, "plan.md"));
  const roadmap = join(root, "roadmap.md");
  writeFileSync(roadmap, "# Roadmap\n");
  const result = run("inspect", folder, "--roadmap", roadmap);
  assert.equal(result.status, 0, result.stderr);
  const snapshot = JSON.parse(result.stdout);
  assert.deepEqual(Object.keys(snapshot), [
    "change.md",
    "research.md",
    "plan.md",
    "plan-brief.md",
    "roadmap",
  ]);
  assert.equal(snapshot["research.md"].exists, true);
  assert.equal(snapshot["plan.md"].exists, false);
  assert.equal(snapshot["plan.md"].sha256, null);
  assert.equal(snapshot["change.md"].sha256, sha(readFileSync(join(folder, "change.md"))));
  assert.equal(snapshot.roadmap.exists, true);
});

test("inspect without a roadmap reports exactly the four change documents", () => {
  write("change.md", "---\nchange_id: delivery-retries\nstatus: new\n---\n");
  const result = run("inspect", folder);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(Object.keys(JSON.parse(result.stdout)).length, 4);
});

test("an impossible calendar date is refused before anything is read", () => {
  write("change.md", "---\nchange_id: delivery-retries\nstatus: new\n---\n");
  const raw = read();
  const result = run(
    "mark-planned",
    folder,
    "--expected-sha256",
    sha(Buffer.from(raw)),
    "--date",
    "2026-02-30",
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /2026-02-30/);
  assert.equal(read(), raw);
});

test("an archived path is refused on any casing", () => {
  const archived = join(root, "Archive", CHANGE_ID);
  mkdirSync(archived, { recursive: true });
  for (const name of ["change.md", "research.md", "plan.md", "plan-brief.md"]) {
    writeFileSync(
      join(archived, name),
      name === "change.md" ? "---\nchange_id: delivery-retries\nstatus: new\n---\n" : "# Doc\n",
    );
  }
  const raw = readFileSync(join(archived, "change.md"), "utf8");
  const result = markPlanned(archived);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Archived or symlink target/);
  assert.equal(readFileSync(join(archived, "change.md"), "utf8"), raw);
});

test("a symlinked change.md is refused rather than followed", () => {
  const real = join(root, "elsewhere.md");
  const raw = "---\nchange_id: delivery-retries\nstatus: new\n---\n";
  writeFileSync(real, raw);
  symlinkSync(real, join(folder, "change.md"));
  const result = markPlanned(folder, sha(Buffer.from(raw)));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Symlink metadata target/);
  assert.equal(readFileSync(real, "utf8"), raw);
});

test("a symlinked change folder is refused rather than followed", () => {
  write("change.md", "---\nchange_id: delivery-retries\nstatus: new\n---\n");
  const link = join(root, "linked-change");
  symlinkSync(folder, link);
  const result = markPlanned(link);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Archived or symlink target/);
});
