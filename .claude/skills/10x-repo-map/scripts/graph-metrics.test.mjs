/** Tests for the edge-list graph metrics, driven through its real entry point: a node process. */
import { afterEach, beforeEach, test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const script = fileURLToPath(new URL("./graph-metrics.mjs", import.meta.url));

let root;

function run(edges, args = [], files = {}) {
  const edgesPath = join(root, "edges.csv");
  writeFileSync(edgesPath, edges);
  for (const [name, content] of Object.entries(files)) writeFileSync(join(root, name), content);
  const resolved = args.map((arg) => (arg.startsWith("@") ? join(root, arg.slice(1)) : arg));
  return spawnSync(process.execPath, [script, edgesPath, ...resolved], { encoding: "utf8" });
}

function json(edges, args = [], files = {}) {
  const result = run(edges, [...args, "--format", "json"], files);
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function byNode(report) {
  return Object.fromEntries(report.metrics.map((m) => [m.node, m]));
}

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "10x-graph-metrics-"));
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

test("computes Ca, Ce and instability per node, with an optional header", () => {
  const report = json("from,to\napp/a.ts,lib/x.ts\napp/b.ts,lib/x.ts\nlib/x.ts,lib/y.ts\n");
  const m = byNode(report);
  assert.equal(report.nodes, 4);
  assert.equal(report.edges, 3);
  assert.deepEqual([m["lib/x.ts"].ca, m["lib/x.ts"].ce, m["lib/x.ts"].instability], [2, 1, 0.33]);
  assert.equal(m["app/a.ts"].instability, 1);
  assert.equal(m["lib/y.ts"].instability, 0);
});

test("finds a cycle as one strongly connected component", () => {
  const report = json("a,b\nb,c\nc,a\nc,d\n");
  assert.deepEqual(report.cycles, [["a", "b", "c"]]);
  assert.deepEqual(
    report.leaves.top.map((m) => m.node),
    ["d"],
  );
});

test("folds files into the longest matching module root and drops internal edges", () => {
  const report = json(
    "server/app/post.go,server/store/store.go\nserver/store/sql/post.go,server/store/store.go\nweb/src/x.ts,web/src/y.ts\n",
    ["--modules", "@modules.txt"],
    { "modules.txt": "server/store\nserver/store/sql\nserver/app\nweb\n" },
  );
  const m = byNode(report);
  assert.equal(report.edges, 2);
  assert.equal(m["server/store"].ca, 2);
  assert.equal(m["web"].ca + m["web"].ce, 0);
});

test("collapse depth folds by path segments and reveals module-level cycles", () => {
  const report = json("a/one.ts,b/one.ts\nb/two.ts,a/two.ts\n", ["--collapse-depth", "1"]);
  assert.deepEqual(report.cycles, [["a", "b"]]);
});

test("focus keeps the downstream neighbourhood to the given depth", () => {
  const report = json("x,a\na,b\nb,c\ny,c\n", ["--focus", "a", "--depth", "1"]);
  assert.deepEqual(report.metrics.map((m) => m.node).sort(), ["a", "b"]);
});

test("reaches keeps everything upstream of a node", () => {
  const report = json("x,a\na,b\nb,c\ny,c\nc,z\n", ["--reaches", "b"]);
  assert.deepEqual(report.metrics.map((m) => m.node).sort(), ["a", "b", "x"]);
});

test("exclude removes edges touching matching paths", () => {
  const report = json("src/a.ts,src/b.ts\nsrc/a.test.ts,src/a.ts\n", ["--exclude", "\\.test\\."]);
  assert.equal(report.nodes, 2);
});

test("min-degree keeps only hubs", () => {
  const report = json("a,hub\nb,hub\nhub,c\nd,e\n", ["--min-degree", "3"]);
  assert.deepEqual(
    report.metrics.map((m) => m.node),
    ["hub"],
  );
});

test("emits mermaid and dot renders of the filtered graph", () => {
  const mermaid = run("a,b\n", ["--emit", "mermaid"]);
  assert.equal(mermaid.status, 0);
  assert.match(mermaid.stdout, /^graph TB\n/);
  assert.match(mermaid.stdout, /n0 --> n1/);
  const dot = run("a,b\n", ["--emit", "dot"]);
  assert.match(dot.stdout, /rankdir="TB"/);
  assert.match(dot.stdout, /n0 -> n1;/);
});

test("markdown output names the applied levers", () => {
  const result = run("a/x,b/y\n", ["--collapse-depth", "1"]);
  assert.equal(result.status, 0);
  assert.match(result.stdout, /\*\*Graph:\*\* 2 nodes, 1 edges \(collapse depth 1\)/);
});

test("refuses malformed input and unknown nodes", () => {
  assert.equal(run("only-one-column\n").status, 1);
  const missing = run("a,b\n", ["--focus", "nope"]);
  assert.equal(missing.status, 1);
  assert.match(missing.stderr, /node not found/);
  assert.equal(run("a,b\n", ["--bogus", "1"]).status, 1);
});

test("modules file with labels folds prefixes into capabilities and reports unmapped files", () => {
  const files = {
    "caps.tsv": "src/orders\torders\nsrc/payments\tpayments\nsrc/orders/refunds\tpayments\n",
  };
  const edges =
    "src/orders/cart.ts,src/payments/charge.ts\nsrc/orders/refunds/p.ts,src/payments/charge.ts\nsrc/util/x.ts,src/orders/cart.ts\n";
  const kept = json(edges, ["--modules", "@caps.tsv"], files);
  assert.equal(kept.unmappedFiles, 1);
  assert.deepEqual(kept.unmappedSample, ["src/util/x.ts"]);
  assert.equal(byNode(kept)["payments"].ca, 1);
  assert.equal(byNode(kept)["src/util/x.ts"].ce, 1);
  const grouped = json(edges, ["--modules", "@caps.tsv", "--unmapped", "group"], files);
  assert.equal(byNode(grouped)["(unmapped)"].ce, 1);
  const dropped = json(edges, ["--modules", "@caps.tsv", "--unmapped", "drop"], files);
  assert.deepEqual(dropped.metrics.map((m) => m.node).sort(), ["orders", "payments"]);
});

test("focus with direction both keeps callers and callees of a hub", () => {
  const report = json("x,hub\nhub,y\ny,z\nw,v\n", ["--focus", "hub", "--direction", "both"]);
  assert.deepEqual(report.metrics.map((m) => m.node).sort(), ["hub", "x", "y"]);
});

test("kind filter separates runtime edges from type-only and build edges", () => {
  const edges = "from,to,kind\na,b,runtime\nb,a,type\nc,dist/index.mjs,build\nd,e\n";
  const runtime = json(edges, ["--kind", "runtime"]);
  assert.equal(runtime.cycles.length, 0);
  assert.equal(runtime.edgesSkippedByKind, 2);
  assert.deepEqual(json(edges).cycles, [["a", "b"]]);
  assert.equal(run("a,b,weird\n").status, 1);
});

test("help prints usage and exits cleanly", () => {
  const result = spawnSync(process.execPath, [script, "--help"], { encoding: "utf8" });
  assert.equal(result.status, 0);
  assert.match(result.stdout, /--direction out\|in\|both/);
});

test("glob patterns win over prefixes and match shared directories by file name", () => {
  const files = {
    "caps.tsv": "db\tplatform\ndb/migrations/*invoice*\tbilling\nsrc/**/*.billing.ts\tbilling\n",
  };
  const edges =
    "db/migrations/001_invoice.sql,db/schema.sql\nsrc/a/b/x.billing.ts,db/migrations/002_users.sql\n";
  const report = json(edges, ["--modules", "@caps.tsv"], files);
  assert.equal(report.unmappedFiles, 0);
  assert.deepEqual(report.metrics.map((m) => m.node).sort(), ["billing", "platform"]);
  assert.equal(byNode(report)["billing"].ce, 1);
});

test("prefixes match whole path segments only", () => {
  const files = { "caps.tsv": "src/billing\tbilling\n" };
  const report = json(
    "src/billing-legacy/a.ts,src/billing/b.ts\n",
    ["--modules", "@caps.tsv"],
    files,
  );
  assert.equal(report.unmappedFiles, 1);
  assert.deepEqual(report.unmappedSample, ["src/billing-legacy/a.ts"]);
});
