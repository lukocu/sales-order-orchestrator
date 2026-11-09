#!/usr/bin/env node
/**
 * Stack-agnostic dependency-graph signals from a normalized edge list.
 *
 * No dependencies. Reads one CSV of `from,to[,kind]` edges (header optional; kind is
 * runtime, type or build, default runtime), folds files into modules or capabilities,
 * applies "tame the hairball" levers as graph operations and prints coupling
 * metrics (Ca, Ce, instability), cycles, entry candidates and leaves — the same numbers
 * whichever tool or language produced the edges. Errors go to stderr, exit code 1.
 *
 * Usage: see USAGE below, or run with --help.
 */
import { readFileSync } from "node:fs";

const USAGE = `usage: graph-metrics.mjs <edges.csv> [options]

  --modules <file>        fold files into groups; one "<pattern>[<TAB><label>]" per line. A
                          pattern is a path prefix matched on whole segments, or a glob
                          with * (any chars except /) or ** (any chars). Globs win, then the
                          longest prefix (module roots or capabilities.tsv)
  --unmapped keep|group|drop
                          files matching no prefix: keep at file level (default), group into
                          "(unmapped)", or drop; the count is always reported
  --collapse-depth <n>    fold by the first n path segments (instead of --modules)
  --kind runtime|type|build|all
                          keep only edges of this kind (default all)
  --exclude <regex>       drop edges whose either end matches
  --focus <node>          keep the neighbourhood of a node or path prefix
  --direction out|in|both neighbourhood direction for --focus (default out)
  --depth <n>             neighbourhood depth for --focus (default 1)
  --reaches <node>        keep everything upstream of a node
  --min-degree <n>        keep only nodes with at least n edges (hubs)
  --top <n>               rows per table (default 10)
  --format md|json        report format (default md)
  --emit mermaid|dot      print the filtered graph instead of the report
  --help                  this text`;

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function parseArgs(argv) {
  const opts = {
    depth: 1,
    top: 10,
    format: "md",
    direction: "out",
    kind: "all",
    unmapped: "keep",
  };
  const valued = new Set([
    "modules",
    "collapse-depth",
    "exclude",
    "focus",
    "depth",
    "reaches",
    "min-degree",
    "top",
    "format",
    "emit",
    "direction",
    "kind",
    "unmapped",
  ]);
  const positional = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (!arg.startsWith("--")) {
      positional.push(arg);
      continue;
    }
    const key = arg.slice(2);
    if (key === "help") {
      process.stdout.write(`${USAGE}\n`);
      process.exit(0);
    }
    if (!valued.has(key)) fail(`unknown option --${key}\n${USAGE}`);
    const value = argv[++i];
    if (value === undefined) fail(`--${key} needs a value\n${USAGE}`);
    opts[key] = value;
  }
  if (positional.length !== 1) fail(USAGE);
  opts.edges = positional[0];
  for (const key of ["collapse-depth", "depth", "min-degree", "top"]) {
    if (opts[key] === undefined) continue;
    const n = Number(opts[key]);
    if (!Number.isInteger(n) || n < 0) fail(`--${key} must be a non-negative integer`);
    opts[key] = n;
  }
  if (!["md", "json"].includes(opts.format)) fail("--format must be md or json");
  if (!["out", "in", "both"].includes(opts.direction)) fail("--direction must be out, in or both");
  if (!["runtime", "type", "build", "all"].includes(opts.kind))
    fail("--kind must be runtime, type, build or all");
  if (!["keep", "group", "drop"].includes(opts.unmapped))
    fail("--unmapped must be keep, group or drop");
  if (opts.emit !== undefined && !["mermaid", "dot"].includes(opts.emit))
    fail("--emit must be mermaid or dot");
  if (opts.modules !== undefined && opts["collapse-depth"] !== undefined) {
    fail("use either --modules or --collapse-depth, not both");
  }
  if (opts.exclude !== undefined) {
    try {
      opts.exclude = new RegExp(opts.exclude);
    } catch (error) {
      fail(`--exclude is not a valid regex: ${error.message}`);
    }
  }
  return opts;
}

/** Split one CSV line into fields, honouring double quotes. */
function splitCsvLine(line) {
  const fields = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (quoted) {
      if (ch === '"' && line[i + 1] === '"') {
        field += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") {
      fields.push(field);
      field = "";
    } else field += ch;
  }
  fields.push(field);
  return fields.map((f) => f.trim());
}

const KINDS = new Set(["runtime", "type", "build"]);

function readEdges(path) {
  let text;
  try {
    text = readFileSync(path, "utf8");
  } catch (error) {
    fail(`cannot read ${path}: ${error.message}`);
  }
  const edges = [];
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    if (line.trim() === "") return;
    const [from, to, kind = ""] = splitCsvLine(line);
    if (index === 0 && from === "from" && to === "to") return;
    if (!from || !to) fail(`${path}:${index + 1}: expected "from,to[,kind]"`);
    const edgeKind = kind === "" ? "runtime" : kind;
    if (!KINDS.has(edgeKind)) fail(`${path}:${index + 1}: kind must be runtime, type or build`);
    edges.push([from, to, edgeKind]);
  });
  return edges;
}

function stripSlash(path) {
  return path.replace(/^\.\//, "").replace(/\/+$/, "");
}

/** `**` matches anything, `*` anything but a slash; everything else is literal. */
function globToRegExp(glob) {
  const body = glob
    .split("**")
    .map((part) =>
      part
        .split("*")
        .map((literal) => literal.replace(/[.+?^${}()|[\]\\]/g, "\\$&"))
        .join("[^/]*"),
    )
    .join(".*");
  return new RegExp(`^${body}$`);
}

function makeFolder(opts) {
  if (opts.modules !== undefined) {
    let roots;
    try {
      roots = readFileSync(opts.modules, "utf8")
        .split(/\r?\n/)
        .filter((line) => line.trim() !== "" && !line.trim().startsWith("#"))
        .map((line) => {
          const [pattern, label] = line.split("\t").map((part) => part.trim());
          const root = stripSlash(pattern);
          const glob = root.includes("*") ? globToRegExp(root) : null;
          return { root, glob, label: label || root };
        });
    } catch (error) {
      fail(`cannot read ${opts.modules}: ${error.message}`);
    }
    const globs = roots.filter((r) => r.glob);
    const prefixes = roots.filter((r) => !r.glob).sort((a, b) => b.root.length - a.root.length);
    return (node) => {
      const path = stripSlash(node);
      const match =
        globs.find(({ glob }) => glob.test(path)) ??
        prefixes.find(({ root }) => root === "." || path === root || path.startsWith(`${root}/`));
      return match ? match.label : null;
    };
  }
  if (opts["collapse-depth"] !== undefined && opts["collapse-depth"] > 0) {
    const depth = opts["collapse-depth"];
    return (node) => stripSlash(node).split("/").slice(0, depth).join("/");
  }
  return (node) => stripSlash(node);
}

class Graph {
  constructor() {
    this.out = new Map();
    this.in = new Map();
  }
  addNode(node) {
    if (!this.out.has(node)) this.out.set(node, new Set());
    if (!this.in.has(node)) this.in.set(node, new Set());
  }
  addEdge(from, to) {
    this.addNode(from);
    this.addNode(to);
    this.out.get(from).add(to);
    this.in.get(to).add(from);
  }
  nodes() {
    return [...this.out.keys()];
  }
  edges() {
    return this.nodes().flatMap((from) => [...this.out.get(from)].map((to) => [from, to]));
  }
  induced(keep) {
    const g = new Graph();
    for (const node of keep) g.addNode(node);
    for (const [from, to] of this.edges()) if (keep.has(from) && keep.has(to)) g.addEdge(from, to);
    return g;
  }
}

function resolveNode(graph, name) {
  const target = stripSlash(name);
  if (graph.out.has(target)) return [target];
  const prefixed = graph.nodes().filter((n) => n.startsWith(`${target}/`));
  if (prefixed.length === 0) fail(`node not found in the graph: ${name}`);
  return prefixed;
}

function walk(graph, starts, direction, maxDepth) {
  const seen = new Set(starts);
  let frontier = [...starts];
  for (
    let level = 0;
    frontier.length > 0 && (maxDepth === undefined || level < maxDepth);
    level++
  ) {
    const next = [];
    for (const node of frontier) {
      const neighbours =
        direction === "both"
          ? [...graph.out.get(node), ...graph.in.get(node)]
          : graph[direction].get(node);
      for (const neighbour of neighbours) {
        if (!seen.has(neighbour)) {
          seen.add(neighbour);
          next.push(neighbour);
        }
      }
    }
    frontier = next;
  }
  return seen;
}

/** Strongly connected components with more than one node — iterative Tarjan. */
function cycles(graph) {
  let index = 0;
  const indices = new Map();
  const low = new Map();
  const onStack = new Set();
  const stack = [];
  const result = [];
  for (const start of graph.nodes()) {
    if (indices.has(start)) continue;
    const work = [[start, [...graph.out.get(start)], 0]];
    indices.set(start, index);
    low.set(start, index);
    index++;
    stack.push(start);
    onStack.add(start);
    while (work.length > 0) {
      const frame = work[work.length - 1];
      const [node, neighbours] = frame;
      if (frame[2] < neighbours.length) {
        const next = neighbours[frame[2]++];
        if (!indices.has(next)) {
          indices.set(next, index);
          low.set(next, index);
          index++;
          stack.push(next);
          onStack.add(next);
          work.push([next, [...graph.out.get(next)], 0]);
        } else if (onStack.has(next)) {
          low.set(node, Math.min(low.get(node), indices.get(next)));
        }
        continue;
      }
      work.pop();
      if (work.length > 0) {
        const parent = work[work.length - 1][0];
        low.set(parent, Math.min(low.get(parent), low.get(node)));
      }
      if (low.get(node) === indices.get(node)) {
        const component = [];
        let member;
        do {
          member = stack.pop();
          onStack.delete(member);
          component.push(member);
        } while (member !== node);
        if (component.length > 1) result.push(component.sort());
      }
    }
  }
  return result.sort((a, b) => b.length - a.length || a[0].localeCompare(b[0]));
}

function analyse(graph, top, stats) {
  const metrics = graph
    .nodes()
    .map((node) => {
      const ca = graph.in.get(node).size;
      const ce = graph.out.get(node).size;
      const instability = ca + ce === 0 ? null : Number((ce / (ca + ce)).toFixed(2));
      return { node, ca, ce, instability };
    })
    .sort((a, b) => b.ca + b.ce - (a.ca + a.ce) || a.node.localeCompare(b.node));
  const entries = metrics.filter((m) => m.ca === 0 && m.ce > 0).sort((a, b) => b.ce - a.ce);
  const leaves = metrics.filter((m) => m.ce === 0 && m.ca > 0).sort((a, b) => b.ca - a.ca);
  return {
    ...stats,
    nodes: metrics.length,
    edges: graph.edges().length,
    metrics: metrics.slice(0, top),
    cycles: cycles(graph),
    entryCandidates: { count: entries.length, top: entries.slice(0, top) },
    leaves: { count: leaves.length, top: leaves.slice(0, top) },
  };
}

function markdown(report, opts) {
  const lines = [];
  const applied = [];
  if (opts.modules !== undefined) applied.push(`modules from ${opts.modules}`);
  if (opts["collapse-depth"] !== undefined)
    applied.push(`collapse depth ${opts["collapse-depth"]}`);
  if (opts.exclude !== undefined) applied.push(`exclude /${opts.exclude.source}/`);
  if (opts.kind !== "all") applied.push(`${opts.kind} edges only`);
  if (opts.focus !== undefined)
    applied.push(`focus ${opts.focus} ${opts.direction} depth ${opts.depth}`);
  if (opts.reaches !== undefined) applied.push(`reaches ${opts.reaches}`);
  if (opts["min-degree"] !== undefined) applied.push(`min degree ${opts["min-degree"]}`);
  lines.push(
    `**Graph:** ${report.nodes} nodes, ${report.edges} edges` +
      (applied.length ? ` (${applied.join("; ")})` : ""),
  );
  if (opts.modules !== undefined)
    lines.push(
      `**Unmapped:** ${report.unmappedFiles} files matched no prefix (${opts.unmapped})` +
        (report.unmappedSample.length ? ` — e.g. ${report.unmappedSample.join(", ")}` : ""),
    );
  if (report.edgesSkippedByKind > 0)
    lines.push(`**Skipped:** ${report.edgesSkippedByKind} edges of other kinds`);
  lines.push(
    "",
    "### Coupling metrics",
    "",
    "| Node | Ca | Ce | Instability |",
    "| --- | --: | --: | --: |",
  );
  for (const m of report.metrics)
    lines.push(`| ${m.node} | ${m.ca} | ${m.ce} | ${m.instability ?? "–"} |`);
  lines.push("", `### Cycles (${report.cycles.length})`, "");
  if (report.cycles.length === 0) lines.push("None found in this graph.");
  for (const [i, cycle] of report.cycles.slice(0, opts.top).entries()) {
    const shown = cycle.slice(0, 10).join(", ");
    lines.push(`${i + 1}. ${cycle.length} nodes: ${shown}${cycle.length > 10 ? ", …" : ""}`);
  }
  lines.push(
    "",
    `### Entry candidates (${report.entryCandidates.count}) — nothing depends on them`,
    "",
  );
  for (const m of report.entryCandidates.top) lines.push(`- ${m.node} (Ce ${m.ce})`);
  lines.push("", `### Leaves (${report.leaves.count}) — depend on nothing in this graph`, "");
  for (const m of report.leaves.top) lines.push(`- ${m.node} (Ca ${m.ca})`);
  return `${lines.join("\n")}\n`;
}

function render(graph, kind) {
  const ids = new Map(graph.nodes().map((node, i) => [node, `n${i}`]));
  if (kind === "mermaid") {
    const lines = ["graph TB"];
    for (const [node, id] of ids) lines.push(`  ${id}["${node.replaceAll('"', "#quot;")}"]`);
    for (const [from, to] of graph.edges()) lines.push(`  ${ids.get(from)} --> ${ids.get(to)}`);
    return `${lines.join("\n")}\n`;
  }
  const lines = ["digraph G {", '  rankdir="TB";', "  node [shape=box];"];
  for (const [node, id] of ids) lines.push(`  ${id} [label="${node.replaceAll('"', '\\"')}"];`);
  for (const [from, to] of graph.edges()) lines.push(`  ${ids.get(from)} -> ${ids.get(to)};`);
  lines.push("}");
  return `${lines.join("\n")}\n`;
}

const opts = parseArgs(process.argv.slice(2));
const fold = makeFolder(opts);
const unmapped = new Set();
let edgesSkippedByKind = 0;
const place = (raw) => {
  const label = fold(raw);
  if (label !== null) return label;
  unmapped.add(stripSlash(raw));
  if (opts.unmapped === "group") return "(unmapped)";
  if (opts.unmapped === "drop") return null;
  return stripSlash(raw);
};
let graph = new Graph();
for (const [rawFrom, rawTo, kind] of readEdges(opts.edges)) {
  if (opts.exclude && (opts.exclude.test(rawFrom) || opts.exclude.test(rawTo))) continue;
  if (opts.kind !== "all" && kind !== opts.kind) {
    edgesSkippedByKind++;
    continue;
  }
  const from = place(rawFrom);
  const to = place(rawTo);
  if (from === null || to === null) continue;
  graph.addNode(from);
  graph.addNode(to);
  if (from !== to) graph.addEdge(from, to);
}
if (opts.focus !== undefined)
  graph = graph.induced(walk(graph, resolveNode(graph, opts.focus), opts.direction, opts.depth));
if (opts.reaches !== undefined)
  graph = graph.induced(walk(graph, resolveNode(graph, opts.reaches), "in"));
if (opts["min-degree"] !== undefined) {
  const keep = new Set(
    graph.nodes().filter((n) => graph.in.get(n).size + graph.out.get(n).size >= opts["min-degree"]),
  );
  graph = graph.induced(keep);
}

if (opts.emit !== undefined) process.stdout.write(render(graph, opts.emit));
else {
  const report = analyse(graph, opts.top, {
    unmappedFiles: unmapped.size,
    unmappedSample: [...unmapped].sort().slice(0, 5),
    edgesSkippedByKind,
  });
  process.stdout.write(
    opts.format === "json" ? `${JSON.stringify(report, null, 2)}\n` : markdown(report, opts),
  );
}
