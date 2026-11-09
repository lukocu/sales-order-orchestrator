#!/usr/bin/env node
// 10x-ray: the observer maps the target skill's anatomy (steps, loops,
// fan-outs, human gates), the worker tags every event with the map node it is
// in, and the views render the skill concept by concept, not tool call by
// tool call.
//
//   init   <skill> [args...] [--lang en|pl]        -> prints a fresh log path
//   map    <log> <map.json>                        -> validates and stores the skill map
//   emit   <log> <kind> <node|-> <title> [detail] [--iter i/n]
//   ask    <log> <node|-> <payload.json>           -> worker hands an interaction to the parent
//   answer <log> <text>                            -> parent records what the user replied
//   watch  <log> [--quiet] [--verbose]             -> renders new frames, exits on done/fail
//   serve  <log> [port]                            -> live page at http://127.0.0.1:<port> (SSE)
//   export <log> [out.html]                        -> standalone snapshot of the run
//
// Map: {"summary":"…","nodes":[{"id","title","pattern","concept","parent"?,"when"?}]}
// Ask payload: {"mode":"choice","questions":[…AskUserQuestion questions…]}
//           or {"mode":"text","prompt":"<verbatim message the skill would wait on>"}
//
// Notifications reach the host with leading whitespace trimmed, so every
// terminal line starts at column 0 and hangs off a left rail.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import { fileURLToPath } from "node:url";

const WIDTH = 62; // inner width of a block, between the borders
const TEMPLATE = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "assets",
  "xray.html",
);

const GLYPHS = {
  input: "▹",
  context: "◈",
  decompose: "⋔",
  gate: "?",
  "fan-out": "⇉",
  loop: "↻",
  branch: "◇",
  synthesize: "⊕",
  artifact: "▤",
  verify: "✓",
  handoff: "→",
  step: "•",
};
// Everything the user reads comes from here, in the language of the
// conversation (`init --lang`). Each pattern carries a fixed lesson: the agent
// limitation it answers and why a skill author reaches for it. The views show
// it the first time the pattern appears in a run; the map's concept then only
// adds what is specific to the skill.
const I18N = {
  en: {
    patterns: {
      input: {
        label: "INPUT",
        limit:
          "An agent knows only what is in its context window. It can't guess which file you mean or what you count as done.",
        why: "The skill first gathers the args, files and request you gave it, and reads them itself before delegating anything. Everything after builds on this material.",
      },
      context: {
        label: "CONTEXT",
        limit:
          "Every session starts from zero. The model doesn't remember yesterday's decisions or the mistakes the team has already fixed once.",
        why: "The author has the skill load written-down knowledge (lessons, project docs, config), so the agent doesn't rediscover what is already known. It's memory the model doesn't have on its own.",
      },
      decompose: {
        label: "DECOMPOSE",
        limit:
          "A big task done in one go gets blurry. The longer an agent works in one stretch, the easier it loses threads.",
        why: "The author splits the work into pieces that can be done and checked separately. The split decides the shape of the run: how many agents start, how many rounds follow.",
      },
      gate: {
        label: "HUMAN GATE",
        limit:
          "The agent doesn't know your priorities. When information is missing, it guesses, and in a confident tone.",
        why: "The author stops the skill where a wrong guess is expensive. A question takes a moment; a wrong answer would waste all the work that follows it.",
      },
      "fan-out": {
        label: "FAN-OUT",
        limit:
          "The context window is finite. An agent that reads everything itself fills it with raw files and reasons worse towards the end.",
        why: "Each sub-agent works in its own clean context. Only conclusions come back to the main agent, not the thousands of lines behind them. They also run at once, so it's faster.",
      },
      loop: {
        label: "LOOP",
        limit:
          "An agent tends to declare success after the first attempt and can quietly skip an item.",
        why: "The same step runs for every phase or item, or until a condition holds. Work ends when the condition is met, not when the agent decides it's enough.",
      },
      branch: {
        label: "BRANCH",
        limit:
          "A rigid procedure spends time and tokens on steps that add nothing in a given situation.",
        why: "This step depends on a condition written into the skill. The skill adapts to the situation, and the agent doesn't have to invent when to skip something.",
      },
      synthesize: {
        label: "SYNTHESIZE",
        limit:
          "Each sub-agent sees only its own slice. None of them notices links between areas or contradictions between findings.",
        why: "The main agent waits for every result and only then puts them together. Links, priorities and resolved contradictions appear here, and no single slice could give them.",
      },
      artifact: {
        label: "ARTIFACT",
        limit:
          "The conversation disappears with the session. The next agent, or you a week later, won't see what was decided.",
        why: "The result lands in a file with a fixed format. It outlives the session, can be reviewed in a PR and becomes input for the next skill.",
      },
      verify: {
        label: "VERIFY",
        limit:
          "A model can claim with full confidence that something works when it doesn't. Its own judgement is not evidence.",
        why: "Something outside the model decides: tests, build, linter, or a check against the requirements. A failing result sends the run back, so the agent gets hard feedback instead of its own impression.",
      },
      handoff: {
        label: "HANDOFF",
        limit:
          "A long session drags all its accumulated context along, and you don't have time to read the whole run.",
        why: "The skill ends with a short summary and a pointer to the next step. The next stage starts in a fresh session with clean context, and you decide whether it starts at all.",
      },
      step: { label: "STEP" },
    },
    kinds: {
      start: "START",
      load: "LOAD",
      read: "READ",
      search: "SEARCH",
      think: "REASON",
      plan: "PLAN",
      edit: "WRITE",
      run: "RUN",
      delegate: "DELEGATE",
      check: "VERIFY",
      ask: "NEEDS INPUT",
      answer: "ANSWER",
      resume: "RESUME",
      decide: "DECISION",
      result: "FINDING",
      warn: "WARNING",
      step: "STEP",
      done: "DONE",
      fail: "FAILED",
    },
    nouns: {
      step: { one: "step", other: "steps" },
      question: { one: "question", other: "questions" },
    },
    ui: {
      args: "args: {args}",
      mapped: "{n} {steps} mapped · revealed as the skill reaches them",
      mappedPage: "{n} {steps} mapped · each one is revealed when the skill reaches it",
      step: "STEP",
      again: "again",
      inside: "inside step {no} · {title}",
      when: "taken when: {when}",
      limit: "Agent limitation",
      why: "Why the author added it",
      here: "In this skill",
      progress: "step {i} of {n}",
      handed: "CONTROL HANDED TO YOU",
      answered: "ANSWERED · CONTROL BACK WITH THE SKILL",
      freeText: "free-text reply",
      reply: "a reply",
      questions: "{n} {questions}",
      question: "question",
      polls: "{tool} polls you for {what}",
      polled: "{tool} polled you for {what}",
      inTerminal: "answer in the Claude Code terminal",
      asksTitle: "Skill asks {n} {questions}",
      waitsTitle: "Skill waits for a reply",
      youAnswered: "You answered",
      anatomy: "SKILL ANATOMY",
      anatomyTitle: "Skill anatomy",
      fullMap: "full map",
      legend: "✓ visited · ×n iterations · – not taken this run",
      outside: "{n} events outside the map",
      complete: "COMPLETE",
      aborted: "ABORTED",
      totals: "X-RAY {verdict} · {seen}/{all} nodes · {time} total",
      pageTotals: "{verdict} · {seen}/{all} nodes visited · T+{time}",
      tickStep: "step",
      running: "running",
      connecting: "connecting",
      reconnecting: "reconnecting",
      empty: "empty",
      missionComplete: "mission complete",
      waiting: "waiting for you",
      stepNo: "step {i} / {n}",
      ahead: "{n} more {steps} beyond the horizon · revealed when reached",
      lastStep: "last mapped step",
      trace: "agent trace · {n}",
      jump: "↓ new activity",
      whenShort: "when {when}",
    },
  },
  pl: {
    patterns: {
      input: {
        label: "WEJŚCIE",
        limit:
          "Agent wie tylko to, co trafiło do jego okna kontekstu. Nie zgadnie, o który plik chodzi ani co uznajesz za „gotowe”.",
        why: "Skill najpierw zbiera argumenty, wskazane pliki i polecenie, i czyta je sam, zanim cokolwiek zleci dalej. Na tym materiale opiera się cała reszta.",
      },
      context: {
        label: "PAMIĘĆ PROJEKTU",
        limit:
          "Każda sesja zaczyna się od zera. Model nie pamięta wczorajszych ustaleń ani błędów, które zespół już raz naprawił.",
        why: "Autor każe wczytać zapisaną wiedzę: lekcje, dokumenty projektu, konfigurację. Agent nie musi wtedy odkrywać na nowo tego, co już wiadomo. To pamięć, której model sam nie ma.",
      },
      decompose: {
        label: "PODZIAŁ NA CZĘŚCI",
        limit:
          "Duże zadanie robione w jednym ciągu się rozmywa. Im dłużej agent pracuje bez przerwy, tym łatwiej gubi wątki.",
        why: "Autor dzieli pracę na kawałki, które da się zrobić i sprawdzić osobno. Ten podział wyznacza przebieg całego skilla: ilu agentów ruszy i ile będzie rund.",
      },
      gate: {
        label: "TWOJA DECYZJA",
        limit:
          "Agent nie zna twoich priorytetów. Gdy brakuje mu informacji, zgaduje, i to pewnym tonem.",
        why: "Autor zatrzymuje skill tam, gdzie pomyłka byłaby droga. Pytanie zajmuje chwilę, a zła odpowiedź zmarnowałaby całą pracę, która po nim następuje.",
      },
      "fan-out": {
        label: "RÓWNOLEGLI AGENCI",
        limit:
          "Okno kontekstu ma swój limit. Agent, który czyta wszystko sam, zapycha je surowymi plikami i pod koniec rozumuje gorzej.",
        why: "Każdy podagent pracuje we własnym, czystym kontekście. Do głównego agenta wracają same wnioski, bez tysięcy linii, z których powstały. Przy okazji jest szybciej, bo podagenci działają jednocześnie.",
      },
      loop: {
        label: "PĘTLA",
        limit:
          "Agent chętnie ogłasza sukces po pierwszej próbie i potrafi po cichu pominąć któryś element.",
        why: "Ten sam krok wykonuje się dla każdej fazy lub elementu albo do spełnienia warunku. Praca kończy się, gdy warunek jest spełniony, a nie wtedy, gdy agent uzna, że wystarczy.",
      },
      branch: {
        label: "KROK WARUNKOWY",
        limit:
          "Sztywna procedura marnuje czas i tokeny na kroki, które w danej sytuacji nic nie dają.",
        why: "Ten krok zależy od warunku zapisanego wprost w skillu. Skill dopasowuje się do sytuacji, a agent nie musi sam wymyślać, kiedy coś pominąć.",
      },
      synthesize: {
        label: "ŁĄCZENIE WYNIKÓW",
        limit:
          "Każdy podagent widzi tylko swój fragment. Żaden nie zauważy powiązań między obszarami ani sprzeczności między ustaleniami.",
        why: "Główny agent czeka na wszystkie wyniki i dopiero wtedy je zestawia. Tu widać powiązania, priorytety i rozstrzygnięte sprzeczności, których nie da żaden pojedynczy fragment.",
      },
      artifact: {
        label: "PLIK WYNIKOWY",
        limit:
          "Rozmowa znika razem z sesją. Następny agent, ani ty za tydzień, nie zobaczy, co tu ustalono.",
        why: "Wynik ląduje w pliku o stałym formacie. Plik przetrwa sesję, da się go przejrzeć w PR i staje się wejściem dla następnego skilla.",
      },
      verify: {
        label: "SPRAWDZENIE",
        limit:
          "Model potrafi z pełnym przekonaniem twierdzić, że coś działa, choć nie działa. Jego własna ocena nie jest dowodem.",
        why: "O wyniku decyduje coś z zewnątrz: testy, build, linter albo porównanie z wymaganiami. Zły wynik cofa przebieg, więc agent dostaje twardą informację zwrotną zamiast własnego wrażenia.",
      },
      handoff: {
        label: "PRZEKAZANIE",
        limit:
          "Długa sesja ciągnie za sobą cały dotychczasowy kontekst, a ty nie masz czasu czytać całego przebiegu.",
        why: "Skill kończy się krótkim podsumowaniem i wskazaniem następnego kroku. Następny etap startuje w nowej sesji, z czystym kontekstem, a o tym, czy w ogóle ruszy, decydujesz ty.",
      },
      step: { label: "KROK" },
    },
    kinds: {
      start: "START",
      load: "WCZYTANIE",
      read: "ODCZYT",
      search: "SZUKANIE",
      think: "NAMYSŁ",
      plan: "PLAN",
      edit: "ZAPIS",
      run: "KOMENDA",
      delegate: "ZLECENIE",
      check: "KONTROLA",
      ask: "PYTANIE",
      answer: "ODPOWIEDŹ",
      resume: "POWRÓT",
      decide: "DECYZJA",
      result: "WYNIK",
      warn: "UWAGA",
      step: "KROK",
      done: "GOTOWE",
      fail: "BŁĄD",
    },
    nouns: {
      step: { one: "krok", few: "kroki", many: "kroków", other: "kroku" },
      question: { one: "pytanie", few: "pytania", many: "pytań", other: "pytania" },
    },
    ui: {
      args: "argumenty: {args}",
      mapped: "{n} {steps} na mapie · każdy odsłania się, gdy skill do niego dojdzie",
      mappedPage: "{n} {steps} na mapie · każdy odsłania się, gdy skill do niego dojdzie",
      step: "KROK",
      again: "ponownie",
      inside: "wewnątrz kroku {no} · {title}",
      when: "wykonywany, gdy: {when}",
      limit: "Ograniczenie agenta",
      why: "Dlaczego autor to dodał",
      here: "W tym skillu",
      progress: "krok {i} z {n}",
      handed: "TERAZ TWÓJ RUCH",
      answered: "ODPOWIEDZIANE · SKILL PRACUJE DALEJ",
      freeText: "Skill",
      reply: "odpowiedź tekstowa",
      questions: "{n} {questions}",
      question: "pytanie",
      polls: "{tool} · {what}",
      polled: "{tool} · {what} · odpowiedziane",
      inTerminal: "odpowiedz w terminalu Claude Code",
      asksTitle: "Skill zadaje {n} {questions}",
      waitsTitle: "Skill czeka na odpowiedź",
      youAnswered: "Twoja odpowiedź",
      anatomy: "ANATOMIA SKILLA",
      anatomyTitle: "Anatomia skilla",
      fullMap: "pełna mapa",
      legend: "✓ odwiedzony · ×n powtórzeń · – pominięty w tym przebiegu",
      outside: "zdarzenia poza mapą: {n}",
      complete: "ZAKOŃCZONY",
      aborted: "PRZERWANY",
      totals: "X-RAY {verdict} · kroki: {seen}/{all} · łącznie {time}",
      pageTotals: "{verdict} · odwiedzone kroki: {seen}/{all} · T+{time}",
      tickStep: "krok",
      running: "w toku",
      connecting: "łączenie",
      reconnecting: "ponowne łączenie",
      empty: "brak zdarzeń",
      missionComplete: "misja zakończona",
      waiting: "czeka na ciebie",
      stepNo: "krok {i} / {n}",
      ahead: "dalsze kroki: {n} · odsłonią się, gdy skill do nich dojdzie",
      lastStep: "ostatni krok na mapie",
      trace: "ślad agenta · {n}",
      jump: "↓ nowa aktywność",
      whenShort: "gdy: {when}",
    },
  },
};
let L = I18N.en;
const useLang = (meta) => (L = I18N[meta.lang] ?? I18N.en);
const fmt = (s, vars = {}) => s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m));
const say = (key, vars) => fmt(L.ui[key], vars);
const noun = (key, n) => {
  const forms = L.nouns[key];
  return forms[new Intl.PluralRules(L === I18N.pl ? "pl" : "en").select(n)] ?? forms.other;
};
// Trace kinds worth a one-liner under the current concept; the rest only
// show with --verbose (and always on the html page, collapsed).
const NOTABLE = new Set([
  "result",
  "decide",
  "edit",
  "warn",
  "delegate",
  "check",
  "resume",
  "answer",
]);
const TERMINAL = new Set(["done", "fail"]);

const [, , cmd, ...rawArgs] = process.argv;
const flags = new Set(rawArgs.filter((a) => a === "--quiet" || a === "--verbose"));
// Valued options: `--iter i/n` on emit, `--lang en|pl` on init.
const valueAt = new Map(
  ["--iter", "--lang"].map((f) => [f, rawArgs.indexOf(f)]).filter(([, i]) => i >= 0),
);
const opt = (f) => (valueAt.has(f) ? rawArgs[valueAt.get(f) + 1] : undefined);
const iterArg = opt("--iter");
const taken = new Set([...valueAt.values()].flatMap((i) => [i, i + 1]));
const args = rawArgs.filter((a, i) => !flags.has(a) && !taken.has(i));

function die(msg) {
  process.stderr.write(`xray: ${msg}\n`);
  process.exit(2);
}

// ── text helpers ──────────────────────────────────────────────────────────
const chars = (s) => [...s];
const pad = (s, n) => (chars(s).length >= n ? s : s + " ".repeat(n - chars(s).length));

function wrap(text, width) {
  const out = [];
  for (const para of String(text ?? "").split(/\n/)) {
    let line = "";
    for (const word of para.split(/\s+/).filter(Boolean)) {
      let w = word;
      while (chars(w).length > width) {
        if (line) {
          out.push(line);
          line = "";
        }
        out.push(chars(w).slice(0, width).join(""));
        w = chars(w).slice(width).join("");
      }
      if (!line) line = w;
      else if (chars(line).length + 1 + chars(w).length <= width) line += ` ${w}`;
      else {
        out.push(line);
        line = w;
      }
    }
    out.push(line);
  }
  while (out.length && out[out.length - 1] === "") out.pop();
  return out;
}

function clock(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function bar(done, total, label) {
  const cells = 30;
  const filled = total ? Math.round((Math.min(done, total) / total) * cells) : 0;
  return `${"█".repeat(filled)}${"░".repeat(cells - filled)} ${label}`;
}

const row = (s) => `│ ${pad(s, WIDTH - 2)} │`;
const drow = (s) => `║ ${pad(s, WIDTH - 2)} ║`;
const bottom = () => `╰${"─".repeat(WIDTH)}╯`;
function top(left, right = "") {
  const fill = WIDTH - chars(left).length - chars(right).length;
  return `╭${left}${"─".repeat(Math.max(1, fill))}${right}╮`;
}
function dtop(left) {
  return `╔${left}${"═".repeat(Math.max(1, WIDTH - chars(left).length))}╗`;
}

// ── data ──────────────────────────────────────────────────────────────────
function readEvents(log) {
  if (!fs.existsSync(log)) return [];
  return fs
    .readFileSync(log, "utf8")
    .split("\n")
    .filter(Boolean)
    .flatMap((l) => {
      try {
        return [JSON.parse(l)];
      } catch {
        return [];
      }
    });
}

const readJson = (file, fallback) =>
  fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : fallback;
const loadMeta = (log) => readJson(`${log}.meta.json`, {});
const loadMap = (log) => readJson(`${log}.map.json`, { summary: "", nodes: [] });

function validateMap(map) {
  if (!map || !Array.isArray(map.nodes) || !map.nodes.length)
    return "map needs a non-empty nodes[]";
  const ids = new Set();
  for (const n of map.nodes) {
    if (!n.id || !n.title || !n.concept)
      return `node ${JSON.stringify(n.id)} needs id, title and concept`;
    if (ids.has(n.id)) return `duplicate node id ${n.id}`;
    if (!GLYPHS[n.pattern])
      return `node ${n.id}: pattern must be one of ${Object.keys(GLYPHS).join(", ")}`;
    if (n.parent && !ids.has(n.parent))
      return `node ${n.id}: parent ${n.parent} must be declared before it`;
    ids.add(n.id);
  }
  return null;
}

// Step numbers: top-level nodes count 1..N, children are 3.1, 3.2, …
function indexMap(map) {
  const byId = new Map(map.nodes.map((n) => [n.id, n]));
  const tops = map.nodes.filter((n) => !n.parent);
  const num = new Map();
  tops.forEach((n, i) => num.set(n.id, String(i + 1)));
  for (const n of map.nodes) {
    if (!n.parent) continue;
    const siblings = map.nodes.filter((s) => s.parent === n.parent);
    num.set(n.id, `${num.get(n.parent)}.${siblings.indexOf(n) + 1}`);
  }
  const topOf = (id) => {
    let n = byId.get(id);
    while (n?.parent) n = byId.get(n.parent);
    return n;
  };
  return { byId, tops, num, topOf };
}

// ── terminal frames ───────────────────────────────────────────────────────
const patternOf = (node) => (GLYPHS[node.pattern] ? node.pattern : "step");
const labelOf = (node) => L.patterns[patternOf(node)].label;
const patternLabel = (node) => `${GLYPHS[patternOf(node)]} ${labelOf(node)}`;
const steps = (n) => noun("step", n);

function startFrame(meta, map, idx) {
  const lines = [dtop(`═ X-RAY · /${meta.skill ?? "skill"} `)];
  if (meta.args)
    for (const t of wrap(say("args", { args: meta.args }), WIDTH - 2)) lines.push(drow(t));
  if (map.summary) {
    lines.push(drow(""));
    for (const t of wrap(map.summary, WIDTH - 2)) lines.push(drow(t));
  }
  lines.push(drow(""));
  const n = idx.tops.length;
  for (const t of wrap(say("mapped", { n, steps: steps(n) }), WIDTH - 2)) lines.push(drow(t));
  lines.push(`╚${"═".repeat(WIDTH)}╝`);
  return lines.join("\n");
}

// `lesson`: first appearance of this pattern in the run, so the fixed lesson
// (agent limitation, why authors reach for it) is shown once, before the
// skill-specific concept.
function conceptFrame(node, ev, idx, startTs, reentry, lesson = false) {
  const t = idx.topOf(node.id);
  const stepNo = idx.tops.indexOf(t) + 1;
  const total = idx.tops.length;
  const iter = ev.iter ? ` · ${ev.iter}` : "";
  const again = reentry ? ` · ${say("again")}` : "";
  const head = `─ ${say("step")} ${idx.num.get(node.id)}/${total} · ${patternLabel(node)}${iter}${again} `;
  const lines = [top(head, ` +${clock(ev.ts - startTs)} ─`)];
  for (const s of wrap(node.title, WIDTH - 2)) lines.push(row(s));
  if (node.parent)
    for (const s of wrap(
      say("inside", { no: idx.num.get(node.parent), title: idx.byId.get(node.parent).title }),
      WIDTH - 2,
    ))
      lines.push(row(s));
  if (!reentry) {
    const p = L.patterns[patternOf(node)];
    if (lesson && p.why) {
      lines.push(row(""));
      lines.push(row(`✗ ${say("limit")}`));
      for (const s of wrap(p.limit, WIDTH - 4)) lines.push(row(`  ${s}`));
      lines.push(row(`✓ ${say("why")}`));
      for (const s of wrap(p.why, WIDTH - 4)) lines.push(row(`  ${s}`));
    }
    lines.push(row(""));
    lines.push(row(`┊ ${say("here")}`));
    for (const s of wrap(node.concept, WIDTH - 4)) lines.push(row(`┊ ${s}`));
    if (node.when)
      for (const s of wrap(say("when", { when: node.when }), WIDTH - 4)) lines.push(row(`┊ ${s}`));
  }
  lines.push(row(""));
  wrap(ev.title, WIDTH - 4).forEach((s, i) => lines.push(row(`${i ? "  " : "▸ "}${s}`)));
  for (const s of wrap(ev.detail, WIDTH - 4)) lines.push(row(`  ${s}`));
  if (!reentry && !node.parent) {
    lines.push(row(""));
    lines.push(row(bar(stepNo, total, say("progress", { i: stepNo, n: total }))));
  }
  lines.push(bottom());
  return lines.join("\n");
}

// A symbolic marker of the hand-off; the real picker is shown by the
// observer in the terminal right after this frame.
function askFrame(ev) {
  const p = ev.payload ?? {};
  const qs = p.questions ?? [];
  const tool = p.tool ?? (p.mode === "text" ? say("freeText") : "AskUserQuestion");
  const n = qs.length;
  const what =
    p.mode === "text" ? say("reply") : say("questions", { n, questions: noun("question", n) });
  const lines = [top(`─ ◇ ${say("handed")} `)];
  for (const s of wrap(say("polls", { tool, what }), WIDTH - 2)) lines.push(row(s));
  if (qs.length)
    for (const s of wrap(qs.map((q) => `[${q.header || say("question")}]`).join(" "), WIDTH - 2))
      lines.push(row(s));
  lines.push(bottom());
  return lines.join("\n");
}

function traceLine(ev) {
  const label = pad(L.kinds[ev.kind] ?? L.kinds.step, 9);
  const body = wrap(ev.title, WIDTH - 12);
  const lines = body.map((s, i) => (i ? `│            ${s}` : `├─ ${label} ${s}`));
  if (["result", "decide", "answer"].includes(ev.kind)) {
    for (const s of wrap(ev.detail, WIDTH - 12)) lines.push(`│            ${s}`);
  }
  return lines.join("\n");
}

function anatomyFrame(meta, map, idx, state, events, startTs) {
  const last = events[events.length - 1];
  const lines = [dtop(`═ ${say("anatomy")} · /${meta.skill ?? "skill"} `)];
  const kindWidth = Math.max(...map.nodes.map((n) => chars(labelOf(n)).length));
  for (const n of map.nodes) {
    const no = pad(`${n.parent ? "  " : ""}${idx.num.get(n.id)}`, 6);
    const glyph = GLYPHS[patternOf(n)];
    const iters = state.maxIter.get(n.id);
    const mark = !state.seen.has(n.id) ? "–" : iters ? `✓ ×${iters}` : "✓";
    const kind = pad(labelOf(n).toLowerCase(), kindWidth);
    const indent = 6 + 2 + kindWidth + 1;
    wrap(n.title, WIDTH - 2 - indent - 8).forEach((s, i) => {
      if (i) return lines.push(drow(`${" ".repeat(indent)}${s}`));
      lines.push(drow(`${pad(`${no}${glyph} ${kind} ${s}`, WIDTH - 2 - 7)}${mark}`));
    });
  }
  const unmapped = events.filter((e) => e.node && !idx.byId.has(e.node)).length;
  lines.push(`╟${"─".repeat(WIDTH)}╢`);
  lines.push(drow(say("legend")));
  if (unmapped) lines.push(drow(say("outside", { n: unmapped })));
  const verdict = say(last.kind === "done" ? "complete" : "aborted");
  const totals = say("totals", {
    verdict,
    seen: state.seen.size,
    all: map.nodes.length,
    time: clock(last.ts - startTs),
  });
  for (const t of wrap(totals, WIDTH - 2)) lines.push(drow(t));
  lines.push(`╚${"═".repeat(WIDTH)}╝`);
  return lines.join("\n");
}

// Replays the whole log so state (current node, iterations) is exact, and
// returns frames only for events from `from` on.
function frames(log, from, { verbose = false, quiet = false } = {}) {
  const events = readEvents(log);
  const meta = loadMeta(log);
  const map = loadMap(log);
  useLang(meta);
  const idx = indexMap(map);
  const state = { cur: null, seen: new Set(), maxIter: new Map(), lastIter: new Map() };
  const taught = new Set(); // patterns whose lesson has been shown
  const firstOf = (node) => !taught.has(node.pattern) && Boolean(taught.add(node.pattern));
  const startTs = events[0]?.ts ?? Date.now();
  const out = [];
  let rendered = from > 0;
  const push = (i, frame, block) => {
    if (i < from || !frame) return;
    out.push(block && rendered ? `│\n▼\n${frame}` : frame);
    rendered = true;
  };
  events.forEach((ev, i) => {
    if (ev.kind === "start") return push(i, quiet ? null : startFrame(meta, map, idx), true);
    if (TERMINAL.has(ev.kind)) {
      const last = idx.byId.get(ev.node);
      if (last && !state.seen.has(last.id)) {
        state.seen.add(last.id);
        push(i, quiet ? null : conceptFrame(last, ev, idx, startTs, false, firstOf(last)), true);
      } else push(i, quiet ? null : traceLine(ev), false);
      return push(i, anatomyFrame(meta, map, idx, state, events.slice(0, i + 1), startTs), true);
    }
    const node = idx.byId.get(ev.node);
    if (node && ev.iter) {
      const k = Number(String(ev.iter).split("/")[0]);
      if (Number.isFinite(k))
        state.maxIter.set(node.id, Math.max(k, state.maxIter.get(node.id) ?? 0));
    }
    if (node && node.id !== state.cur) {
      const reentry = state.seen.has(node.id);
      state.cur = node.id;
      state.seen.add(node.id);
      state.lastIter.set(node.id, ev.iter);
      const lesson = !reentry && firstOf(node);
      push(i, quiet ? null : conceptFrame(node, ev, idx, startTs, reentry, lesson), true);
    } else if (node && ev.iter && ev.iter !== state.lastIter.get(node.id)) {
      state.lastIter.set(node.id, ev.iter);
      push(i, quiet ? null : conceptFrame(node, ev, idx, startTs, true), true);
    } else if (ev.kind !== "ask") {
      push(i, quiet || !(verbose || NOTABLE.has(ev.kind)) ? null : traceLine(ev), false);
    }
    if (ev.kind === "ask") push(i, askFrame(ev), true);
  });
  return { events, out };
}

// ── html ──────────────────────────────────────────────────────────────────
function page(log, { live }) {
  const meta = loadMeta(log);
  useLang(meta);
  const data = {
    live,
    meta,
    map: loadMap(log),
    lang: L === I18N.pl ? "pl" : "en",
    glyphs: GLYPHS,
    patterns: L.patterns,
    kinds: L.kinds,
    nouns: L.nouns,
    ui: L.ui,
    notable: [...NOTABLE],
    events: live ? [] : readEvents(log),
  };
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return fs.readFileSync(TEMPLATE, "utf8").replace("__XRAY_DATA__", () => json);
}

// ── commands ──────────────────────────────────────────────────────────────
function append(log, ev) {
  const n = readEvents(log).length + 1;
  fs.appendFileSync(log, `${JSON.stringify({ n, ts: Date.now(), ...ev })}\n`);
  return n;
}
const nodeArg = (v) => (v && v !== "-" ? v : undefined);

if (cmd === "init") {
  const skill = (args[0] ?? "skill").replace(/[^\w.-]/g, "_");
  const dir = path.join(os.tmpdir(), "10x-ray");
  fs.mkdirSync(dir, { recursive: true });
  const log = path.join(dir, `${skill}-${Date.now()}.ndjson`);
  fs.writeFileSync(log, "");
  fs.writeFileSync(
    `${log}.meta.json`,
    JSON.stringify({
      skill: args[0] ?? "skill",
      args: args.slice(1).join(" "),
      lang: opt("--lang") === "pl" ? "pl" : "en",
    }),
  );
  process.stdout.write(`${log}\n`);
} else if (cmd === "map") {
  const [log, file] = args;
  if (!log || !file) die("usage: map <log> <map.json>");
  let map;
  try {
    map = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    die(`unreadable map ${file}: ${e.message}`);
  }
  const err = validateMap(map);
  if (err) die(err);
  fs.writeFileSync(`${log}.map.json`, JSON.stringify(map, null, 2));
  const { tops } = indexMap(map);
  process.stdout.write(`map ok: ${map.nodes.length} nodes, ${tops.length} top-level steps\n`);
} else if (cmd === "emit") {
  const [log, kind, node, title, detail] = args;
  if (!log || !kind || !title)
    die("usage: emit <log> <kind> <node|-> <title> [detail] [--iter i/n]");
  const id = nodeArg(node);
  const n = append(log, {
    kind: L.kinds[kind] ? kind : "step",
    node: id,
    iter: iterArg,
    title,
    detail: detail || undefined,
  });
  const known = !id || loadMap(log).nodes.some((x) => x.id === id);
  process.stdout.write(`ok #${n}${known ? "" : ` (warning: node "${id}" is not on the map)`}\n`);
} else if (cmd === "ask") {
  const [log, node, file] = args;
  if (!log || !file) die("usage: ask <log> <node|-> <payload.json>");
  let payload;
  try {
    payload = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    die(`unreadable payload ${file}: ${e.message}`);
  }
  if (payload.mode !== "text" && !Array.isArray(payload.questions)) {
    die('payload needs mode "text" + prompt, or questions[]');
  }
  const payloadFile = `${log}.ask-${readEvents(log).length + 1}.json`;
  fs.writeFileSync(payloadFile, JSON.stringify(payload, null, 2));
  const count = payload.mode === "text" ? 0 : payload.questions.length;
  useLang(loadMeta(log));
  const n = append(log, {
    kind: "ask",
    node: nodeArg(node),
    title:
      payload.mode === "text"
        ? say("waitsTitle")
        : say("asksTitle", { n: count, questions: noun("question", count) }),
    payload,
    payloadFile,
  });
  process.stdout.write(`ok #${n} ${payloadFile}\n`);
} else if (cmd === "answer") {
  const [log, ...rest] = args;
  const text = rest.join(" ");
  if (!log || !text) die("usage: answer <log> <text>");
  const last = readEvents(log).findLast((e) => e.node);
  useLang(loadMeta(log));
  const n = append(log, {
    kind: "answer",
    node: last?.node,
    title: say("youAnswered"),
    detail: text,
  });
  process.stdout.write(`ok #${n}\n`);
} else if (cmd === "watch") {
  const [log] = args;
  if (!log) die("usage: watch <log> [--quiet] [--verbose]");
  const cursorFile = `${log}.cursor`;
  let cursor = Number(readJson(cursorFile, 0)) || 0;
  const tick = () => {
    const { events, out } = frames(log, cursor, {
      quiet: flags.has("--quiet"),
      verbose: flags.has("--verbose"),
    });
    if (events.length <= cursor) return;
    const fresh = events.slice(cursor);
    cursor = events.length;
    fs.writeFileSync(cursorFile, String(cursor));
    const end = fresh.some((ev) => TERMINAL.has(ev.kind));
    if (out.length) {
      // The host previews the first line of a notification; lead with a
      // plain tick line instead of a box border that would render torn.
      const idx = indexMap(loadMap(log));
      const at = fresh.findLast((e) => idx.byId.has(e.node));
      const where = at
        ? ` · ${say("tickStep")} ${idx.num.get(at.node)} ${idx.byId.get(at.node).title}`
        : "";
      const ask = fresh.findLast((e) => e.kind === "ask" && e.payloadFile);
      const tick = `x-ray tick${where}${end ? " · finished" : ""}${ask ? ` · ask=${ask.payloadFile}` : ""}`;
      // One write per tick so a burst of events lands as one notification.
      process.stdout.write(`${[tick, ...out].join("\n")}\n`);
    }
    if (end) process.exit(0);
  };
  tick();
  setInterval(tick, 400);
} else if (cmd === "serve") {
  const [log, portArg] = args;
  if (!log) die("usage: serve <log> [port]");
  let exported = false;
  const server = http.createServer((req, res) => {
    if (req.url === "/" || req.url.startsWith("/?")) {
      res.writeHead(200, {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
      });
      res.end(page(log, { live: true }));
    } else if (req.url === "/events") {
      res.writeHead(200, {
        "content-type": "text/event-stream",
        "cache-control": "no-store",
        connection: "keep-alive",
      });
      let sent = Number(req.headers["last-event-id"]) || 0;
      const push = () => {
        const events = readEvents(log);
        for (const ev of events.slice(sent))
          res.write(`id: ${ev.n}\ndata: ${JSON.stringify(ev)}\n\n`);
        sent = Math.max(sent, events.length);
      };
      push();
      const timer = setInterval(push, 300);
      const ping = setInterval(() => res.write(": ping\n\n"), 15000);
      req.on("close", () => {
        clearInterval(timer);
        clearInterval(ping);
      });
    } else {
      res.writeHead(404).end();
    }
  });
  // Snapshot once the run ends, so the page survives the server.
  setInterval(() => {
    if (exported || !readEvents(log).some((ev) => TERMINAL.has(ev.kind))) return;
    exported = true;
    fs.writeFileSync(`${log}.html`, page(log, { live: false }));
    process.stdout.write(`x-ray snapshot: ${log}.html\n`);
  }, 500);
  server.listen(Number(portArg) || 0, "127.0.0.1", () => {
    process.stdout.write(`x-ray page: http://127.0.0.1:${server.address().port}/\n`);
  });
} else if (cmd === "export") {
  const [log, out] = args;
  if (!log) die("usage: export <log> [out.html]");
  const target = out ?? `${log}.html`;
  fs.writeFileSync(target, page(log, { live: false }));
  process.stdout.write(`${target}\n`);
} else {
  die("usage: xray.mjs init|map|emit|ask|answer|watch|serve|export ...");
}
