#!/usr/bin/env node
/**
 * Inspect change targets independently; narrowly advance existing change metadata.
 *
 * No dependencies. JSON on stdout, a refusal message on stderr with exit code 1.
 * The guard never creates change.md, never reconstructs frontmatter and never writes
 * `created:` — a change folder without identity metadata belongs to /10x-new.
 * Writes use optimistic fingerprint checking and atomic replacement, not a cross-process
 * transaction with editors that do not participate in locking.
 *
 * Usage:
 *   metadata-guard.mjs inspect <change-dir> [--roadmap <path>]
 *   metadata-guard.mjs mark-planned <change-dir> --expected-sha256 <hex> --date <YYYY-MM-DD>
 *   metadata-guard.mjs mark-researched <change-dir> --expected-sha256 <hex> --date <YYYY-MM-DD>
 */
import { createHash, randomBytes } from "node:crypto";
import {
  chmodSync,
  closeSync,
  existsSync,
  fsyncSync,
  lstatSync,
  openSync,
  readFileSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  writeSync,
} from "node:fs";
import { basename, join, resolve } from "node:path";

const MISSING_CHANGE_FILE =
  "change.md is missing in this change folder; run /10x-new to create it before recording progress";

/** Both commands advance from the same early states; only the target status differs. */
const COMMANDS = {
  "mark-planned": {
    status: "planned",
    from: new Set(["new", "preparing"]),
    required: ["plan.md", "plan-brief.md"],
  },
  "mark-researched": {
    status: "preparing",
    from: new Set(["new", "preparing"]),
    required: ["research.md"],
  },
};

class GuardError extends Error {}

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function lstatOrNull(path) {
  try {
    return lstatSync(path);
  } catch {
    return null;
  }
}

function statOrNull(path) {
  try {
    return statSync(path);
  } catch {
    return null;
  }
}

function fingerprint(path) {
  return statOrNull(path)?.isFile() ? sha256(readFileSync(path)) : null;
}

/** Python's Path.resolve() tolerates missing paths; realpathSync throws ENOENT instead. */
function realPath(path) {
  try {
    return realpathSync(path);
  } catch {
    return resolve(path);
  }
}

function hasArchiveSegment(path) {
  return path.split(/[\\/]+/).some((part) => part.toLowerCase() === "archive");
}

function requireChangeFile(folder) {
  if (!existsSync(join(folder, "change.md"))) throw new GuardError(MISSING_CHANGE_FILE);
}

function inspect(folder, roadmap) {
  const absolute = resolve(folder);
  requireChangeFile(absolute);
  const probes = new Map(
    ["change.md", "research.md", "plan.md", "plan-brief.md"].map((name) => [
      name,
      join(absolute, name),
    ]),
  );
  if (roadmap !== undefined) probes.set("roadmap", resolve(roadmap));
  // Each probe is independent: a missing plan cannot hide an existing roadmap.
  return Object.fromEntries(
    [...probes].map(([name, path]) => [
      name,
      { path, exists: existsSync(path), sha256: fingerprint(path) },
    ]),
  );
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Python's \w is unicode-aware; JavaScript's \w is ASCII-only, so an accented scalar such as
 * `status: zażółć` would otherwise be refused as unsupported syntax instead of being read.
 */
function scalar(line, key) {
  const pattern = new RegExp(
    `^(${escapeRegExp(key)}:[ \\t]*)([\\p{L}\\p{N}_-]+|"[\\p{L}\\p{N}_-]+"|'[\\p{L}\\p{N}_-]+')([ \\t]*(?:#[^\\r\\n]*)?)(\\r?\\n)?$`,
    "u",
  );
  const match = pattern.exec(line);
  if (!match || match[0] !== line)
    throw new GuardError(
      `Unsupported scalar syntax for ${key}; preserve the file and inspect it directly`,
    );
  return { match, value: match[2].replace(/^["']|["']$/g, "") };
}

function rewrite(match, value) {
  return `${match[1]}${value}${match[3]}${match[4] ?? ""}`;
}

/** Reproduces date.fromisoformat: exact shape plus a calendar round-trip (rejects 2026-02-30). */
function requireIsoDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) throw new GuardError(`Unsupported date: ${value}; use YYYY-MM-DD`);
  const [year, month, day] = match.slice(1).map(Number);
  const probe = new Date(Date.UTC(year, month - 1, day));
  if (
    probe.getUTCFullYear() !== year ||
    probe.getUTCMonth() !== month - 1 ||
    probe.getUTCDate() !== day
  )
    throw new GuardError(`Unsupported date: ${value}; use a real calendar day`);
  return value;
}

function decodeUtf8(raw) {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(raw);
  } catch {
    throw new GuardError("change.md is not valid UTF-8; preserve the file and inspect it directly");
  }
}

function metadataBytes(raw, changeId, today, command) {
  const text = decodeUtf8(raw);
  // Python's splitlines() also breaks on \v, \f and U+2028; keep those inside their line.
  const lines = text.split(/(?<=\n)/);
  if (!lines.length || lines[0].trim() !== "---")
    throw new GuardError("Existing YAML frontmatter is required; do not reconstruct metadata");
  let end = -1;
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === "---") {
      end = i;
      break;
    }
  }
  if (end < 0) throw new GuardError("Unclosed frontmatter");
  const positions = new Map();
  for (let i = 1; i < end; i += 1) {
    if (/^['"?%]|^<<:/.test(lines[i]))
      throw new GuardError(
        "Unsupported top-level YAML key syntax; preserve metadata and inspect directly",
      );
    const match = /^([A-Za-z_][\p{L}\p{N}_-]*):/u.exec(lines[i]);
    if (!match && lines[i].trim() && !/^[ \t#]/.test(lines[i]))
      throw new GuardError(
        "Unsupported top-level YAML syntax; preserve metadata and inspect directly",
      );
    if (match) {
      if (positions.has(match[1])) throw new GuardError(`Duplicate frontmatter key: ${match[1]}`);
      positions.set(match[1], i);
    }
  }
  for (const key of ["change_id", "status"]) {
    if (!positions.has(key)) throw new GuardError(`Missing identity/status field: ${key}`);
  }
  if (scalar(lines[positions.get("change_id")], "change_id").value !== changeId)
    throw new GuardError("Change identity does not match target folder");
  const status = scalar(lines[positions.get("status")], "status");
  if (status.value === "archived") throw new GuardError("Archived change");
  // Includes later and unknown lifecycle states; never downgrade, never touch the file.
  if (!command.from.has(status.value)) return raw;
  lines[positions.get("status")] = rewrite(status.match, command.status);
  if (positions.has("updated")) {
    lines[positions.get("updated")] = rewrite(
      scalar(lines[positions.get("updated")], "updated").match,
      today,
    );
  } else {
    lines.splice(end, 0, `updated: ${today}${lines[0].endsWith("\r\n") ? "\r\n" : "\n"}`);
  }
  return Buffer.from(lines.join(""), "utf8");
}

function replaceAtomically(folder, target, raw, updated) {
  let temporary = join(folder, `.change-${process.pid}-${randomBytes(8).toString("hex")}`);
  try {
    const handle = openSync(temporary, "wx", 0o600);
    try {
      for (let written = 0; written < updated.length; ) {
        written += writeSync(handle, updated, written, updated.length - written);
      }
      fsyncSync(handle);
    } finally {
      closeSync(handle);
    }
    chmodSync(temporary, statSync(target).mode & 0o777);
    // Second verification read: the window between fingerprinting and replacement is not locked.
    if (lstatSync(target).isSymbolicLink() || !readFileSync(target).equals(raw))
      throw new GuardError("Metadata changed before replacement; preserve the new content");
    renameSync(temporary, target);
    temporary = null;
  } finally {
    if (temporary !== null) rmSync(temporary, { force: true });
  }
  if (!readFileSync(target).equals(updated))
    throw new GuardError("Persisted metadata differs from intended bytes");
}

function mark(folder, expected, today, name) {
  const command = COMMANDS[name];
  const absolute = resolve(folder);
  if (
    hasArchiveSegment(absolute) ||
    hasArchiveSegment(realPath(absolute)) ||
    lstatOrNull(absolute)?.isSymbolicLink()
  )
    throw new GuardError("Archived or symlink target");
  const target = join(absolute, "change.md");
  const metadata = lstatOrNull(target);
  if (metadata?.isSymbolicLink()) throw new GuardError("Symlink metadata target");
  if (!metadata?.isFile()) throw new GuardError(MISSING_CHANGE_FILE);
  for (const required of command.required) {
    const document = statOrNull(join(absolute, required));
    if (!document?.isFile() || !document.size)
      throw new GuardError(
        `Save and verify required documents before advancing metadata: ${required}`,
      );
  }
  const raw = readFileSync(target);
  if (sha256(raw) !== expected)
    throw new GuardError("Metadata changed since inspection; reread and preserve the new content");
  const updated = metadataBytes(raw, basename(absolute), today, command);
  if (updated.equals(raw)) return { changed: false, sha256: expected };
  replaceAtomically(absolute, target, raw, updated);
  return { changed: true, sha256: fingerprint(target) };
}

function parseArguments(argv) {
  const [name, ...rest] = argv;
  if (name !== "inspect" && !(name in COMMANDS))
    throw new GuardError(
      `Unknown command: ${name ?? "(none)"}; expected inspect, mark-planned or mark-researched`,
    );
  const allowed = name === "inspect" ? ["roadmap"] : ["expected-sha256", "date"];
  const positional = [];
  const options = {};
  for (let i = 0; i < rest.length; i += 1) {
    if (!rest[i].startsWith("--")) {
      positional.push(rest[i]);
      continue;
    }
    const separator = rest[i].indexOf("=");
    const key = separator === -1 ? rest[i].slice(2) : rest[i].slice(2, separator);
    if (!allowed.includes(key)) throw new GuardError(`Unsupported option for ${name}: --${key}`);
    if (separator !== -1) {
      options[key] = rest[i].slice(separator + 1);
      continue;
    }
    if (i + 1 >= rest.length) throw new GuardError(`Option --${key} requires a value`);
    options[key] = rest[i + 1];
    i += 1;
  }
  if (positional.length !== 1)
    throw new GuardError(`${name} takes exactly one change directory argument`);
  if (name !== "inspect") {
    for (const key of allowed) {
      if (options[key] === undefined) throw new GuardError(`Option --${key} is required`);
    }
    requireIsoDate(options.date);
  }
  return { name, folder: positional[0], options };
}

function main() {
  try {
    const { name, folder, options } = parseArguments(process.argv.slice(2));
    const result =
      name === "inspect"
        ? inspect(folder, options.roadmap)
        : mark(folder, options["expected-sha256"], options.date, name);
    console.log(JSON.stringify(result));
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}

main();
