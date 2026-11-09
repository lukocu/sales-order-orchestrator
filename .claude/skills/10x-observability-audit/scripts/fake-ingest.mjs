#!/usr/bin/env node
// Local fake error-tracker ingest for observability probes.
// Accepts any request, decompresses gzip/deflate/br bodies, and appends one
// JSON line per request: {at, method, url, headers, body}. Zero dependencies.
//
// Usage: node fake-ingest.mjs [--port 9876] [--host 127.0.0.1] [--out ingest.jsonl]
// Point the SDK at it, e.g. Sentry DSN http://publickey@127.0.0.1:9876/1
import http from "node:http";
import zlib from "node:zlib";
import fs from "node:fs";

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const port = Number(opt("port", "9876"));
const host = opt("host", "127.0.0.1");
const out = opt("out", "ingest.jsonl");

const decode = (buf, encoding) => {
  try {
    if (encoding === "gzip") return zlib.gunzipSync(buf);
    if (encoding === "deflate") return zlib.inflateSync(buf);
    if (encoding === "br") return zlib.brotliDecompressSync(buf);
  } catch {
    // Keep the raw body; a decode failure is itself useful to see.
  }
  return buf;
};

// Headers that may carry credentials are dropped so the capture file is safe to share.
const SAFE_HEADERS = ["content-type", "content-encoding", "user-agent", "x-sentry-auth-version"];

http
  .createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      const body = decode(Buffer.concat(chunks), req.headers["content-encoding"]).toString("utf8");
      const headers = Object.fromEntries(
        SAFE_HEADERS.filter((h) => req.headers[h]).map((h) => [h, req.headers[h]]),
      );
      fs.appendFileSync(
        out,
        JSON.stringify({
          at: new Date().toISOString(),
          method: req.method,
          url: req.url,
          headers,
          body,
        }) + "\n",
      );
      // A 200 with an id-shaped body satisfies Sentry, OTLP and most JSON intake APIs.
      res.writeHead(200, { "content-type": "application/json" });
      res.end('{"id":"00000000000000000000000000000000"}');
    });
  })
  .listen(port, host, () =>
    console.log(`fake ingest listening on http://${host}:${port} -> ${out}`),
  );
