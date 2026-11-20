#!/usr/bin/env node
// ELIO Studio server: runs the dashboard at http://localhost:4321 and the demo-building agent.
// Start it with ./start-studio.sh (or: node studio-server.js). No dependencies.
//
// The agent uses the Claude Code CLI installed on this computer (`claude`), signed in with your
// Claude account. Set CLAUDE_BIN to use a different path.

const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { spawn, execFileSync } = require("child_process");

const ROOT = __dirname;
const PORT = +process.env.PORT || 4321;
const DATA_DIR = path.join(ROOT, "data");
const DATA_FILE = path.join(DATA_DIR, "studio.json");
const INCOMING = path.join(ROOT, "clients", "_incoming");
const AGENT_TIMEOUT_MS = 15 * 60 * 1000;

const CLAUDE_BIN =
  process.env.CLAUDE_BIN ||
  [path.join(os.homedir(), ".local", "bin", "claude")].find((p) => fs.existsSync(p)) ||
  "claude";

// ---------- storage ----------
function load() {
  try {
    const d = JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
    return { items: d.items || [], jobs: d.jobs || [], imported: !!d.imported };
  } catch {
    return { items: [], jobs: [], imported: false };
  }
}
let state = load();
// A job that was running when the server stopped will never finish.
for (const j of state.jobs) if (j.status === "working" || j.status === "queued") {
  j.status = "failed";
  j.error = "The studio was closed before this finished. Try again.";
}
function save() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  const tmp = DATA_FILE + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(state, null, 2));
  fs.renameSync(tmp, DATA_FILE);
}

// ---------- helpers ----------
const slugify = (s) =>
  String(s).toLowerCase().normalize("NFKD").replace(/[^\w\s-]/g, "").trim().replace(/[\s_]+/g, "-").replace(/-+/g, "-").slice(0, 60) || "client";
const today = () => new Date().toISOString().slice(0, 10);
const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

function uniqueSlug(base) {
  let slug = base, n = 2;
  while (fs.existsSync(path.join(ROOT, "clients", slug))) slug = `${base}-${n++}`;
  return slug;
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let b = "";
    req.on("data", (c) => { b += c; if (b.length > 2e6) req.destroy(); });
    req.on("end", () => { try { resolve(b ? JSON.parse(b) : {}); } catch (e) { reject(e); } });
    req.on("error", reject);
  });
}

function send(res, code, body, type = "application/json") {
  res.writeHead(code, { "Content-Type": type, "Cache-Control": "no-store" });
  res.end(type === "application/json" ? JSON.stringify(body) : body);
}

const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif" };

function serveFile(res, file) {
  fs.readFile(file, (err, buf) => {
    if (err) return send(res, 404, "Not found", "text/plain");
    res.writeHead(200, { "Content-Type": MIME[path.extname(file).toLowerCase()] || "application/octet-stream" });
    res.end(buf);
  });
}

// ---------- the agent ----------
function agentPrompt(request, outFile) {
  const example = fs.readFileSync(path.join(ROOT, "clients", "_example-plumbing", "site.config.json"), "utf8");
  return `You are the website builder for ELIO Website Studio, which makes demo websites for local businesses.

THE USER'S REQUEST:
"""
${request}
"""

YOUR JOB:
1. Identify the exact business (and the exact location, if it has several). Search the web for its public details:
   address, phone, opening hours, what it sells or does, menu items or services, prices if published, and its
   Instagram or other social pages. Prefer details the user gave you over anything you find online.
2. Write ONE JSON file to this exact path: ${outFile}
   It must follow the same format as this example config:
${example}
   Extra optional fields: "servicesNav" (menu link text, e.g. "Menu" for restaurants), "hero.ctaLink" (a URL),
   "hero.image" (leave out), "contactFormAction" (leave empty).

RULES:
- Use only details you actually found or the user gave you. Never invent prices, reviews, awards, years in business,
  or staff names. If you can't confirm a detail, leave it out (omit "price"; omit "phone" or "email" if unknown).
- "testimonials" must be an empty list.
- "about": 2-3 friendly sentences built only from facts you found, ending with "(Demo text: confirm with the owner.)"
- Pick "theme.primary" and "theme.accent" colors that suit the business (primary must be dark enough for white text).
- Use 3, 4 or 6 "services" so the cards fill their rows.
- Write a short, punchy hero headline in the business's own voice.
- If the phone is unknown, set "hero.ctaText" to "Get directions" and "hero.ctaLink" to a Google Maps search URL for the address.
- Do not create or change any other file.

When the file is written, reply with ONLY a short plain-text list of what the owner should confirm before launch
(for example hours that differ between listings, missing prices, missing photos). No other commentary.`;
}

let running = false;
function pump() {
  if (running) return;
  const job = state.jobs.find((j) => j.status === "queued");
  if (!job) return;
  running = true;
  runJob(job).finally(() => { running = false; save(); pump(); });
}

function runJob(job) {
  return new Promise((resolve) => {
    job.status = "working";
    job.startedAt = new Date().toISOString();
    job.step = "Researching the business";
    save();

    fs.mkdirSync(INCOMING, { recursive: true });
    const outFile = path.join(INCOMING, job.id + ".json");
    try { fs.unlinkSync(outFile); } catch {}

    const args = ["-p", agentPrompt(job.request, outFile),
      "--allowedTools", "WebSearch,WebFetch,Read,Write",
      "--permission-mode", "acceptEdits",
      "--output-format", "json"];
    let out = "", err = "";
    let child;
    try {
      child = spawn(CLAUDE_BIN, args, { cwd: ROOT, env: process.env });
    } catch (e) {
      return fail(`Couldn't start Claude Code (${e.message}).`);
    }
    const timer = setTimeout(() => { child.kill("SIGTERM"); }, AGENT_TIMEOUT_MS);
    child.stdout.on("data", (c) => (out += c));
    child.stderr.on("data", (c) => (err += c));
    child.on("error", (e) => {
      clearTimeout(timer);
      fail(e.code === "ENOENT"
        ? "Claude Code wasn't found on this computer. Open a terminal and run `claude` once to check it's installed and signed in."
        : `Couldn't start Claude Code (${e.message}).`);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (job.status !== "working") return; // already failed via 'error'
      let notes = "";
      try { notes = String(JSON.parse(out).result || "").trim(); } catch { notes = out.trim(); }
      if (!fs.existsSync(outFile)) {
        return fail(code === null
          ? "It took too long and was stopped. Try again with more details (town, phone)."
          : `The agent didn't produce a website. ${(err || notes).trim().slice(-400)}`);
      }
      let cfg;
      try { cfg = JSON.parse(fs.readFileSync(outFile, "utf8")); } catch { return fail("The agent wrote an invalid settings file. Try again."); }
      const name = cfg.business && cfg.business.name;
      if (!name) return fail("The agent couldn't identify the business. Add the town or a phone number and try again.");

      job.step = "Building the website";
      save();
      const slug = uniqueSlug(slugify(name));
      const dir = path.join(ROOT, "clients", slug);
      fs.mkdirSync(path.join(dir, "assets"), { recursive: true });
      fs.writeFileSync(path.join(dir, "site.config.json"), JSON.stringify(cfg, null, 2));
      fs.unlinkSync(outFile);
      try {
        execFileSync(process.execPath, [path.join(ROOT, "build.js"), path.join("clients", slug)], { cwd: ROOT });
      } catch (e) {
        return fail("The website settings were saved but the build failed: " + String(e.stderr || e.message).slice(0, 300));
      }

      const b = cfg.business || {};
      const item = {
        id: Date.now(),
        name,
        contact: "",
        reach: [b.phone, b.email].filter(Boolean).join(" · "),
        address: b.address || "",
        stage: "Demo ready",
        package: "Starter",
        fee: 499,
        monthly: 49,
        next: "Show demo to owner",
        due: addDays(1),
        notes,
        demo: `dist/${slug}/index.html`,
        slug,
        createdBy: "agent",
        createdAt: today(),
      };
      state.items.push(item);
      Object.assign(job, { status: "done", step: "Demo ready", finishedAt: new Date().toISOString(), itemId: item.id, demo: item.demo, name, notes });
      resolve();
    });

    function fail(msg) {
      Object.assign(job, { status: "failed", step: "Failed", error: msg, finishedAt: new Date().toISOString() });
      resolve();
    }
  });
}

// ---------- routes ----------
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const p = decodeURIComponent(url.pathname);
  try {
    if (p === "/" || p === "/index.html") return serveFile(res, path.join(ROOT, "dashboard", "index.html"));
    if (p === "/api/state" && req.method === "GET") return send(res, 200, { ...state, agent: true, running });
    if (p === "/api/items" && req.method === "PUT") {
      const body = await readBody(req);
      if (!Array.isArray(body.items)) return send(res, 400, { error: "items must be a list" });
      state.items = body.items;
      if (body.imported) state.imported = true;
      save();
      return send(res, 200, { ok: true });
    }
    if (p === "/api/agent" && req.method === "POST") {
      const body = await readBody(req);
      const request = String(body.request || "").trim();
      if (request.length < 3) return send(res, 400, { error: "Tell the agent which business to build a demo for." });
      const job = { id: "job-" + Date.now(), request, status: "queued", step: "Waiting to start", createdAt: new Date().toISOString() };
      state.jobs.unshift(job);
      state.jobs = state.jobs.slice(0, 50);
      save();
      pump();
      return send(res, 200, job);
    }
    if (p.startsWith("/api/jobs/") && req.method === "DELETE") {
      state.jobs = state.jobs.filter((j) => j.id !== p.slice(10) || j.status === "working");
      save();
      return send(res, 200, { ok: true });
    }
    if (p.startsWith("/dist/")) {
      const file = path.normalize(path.join(ROOT, p));
      if (!file.startsWith(path.join(ROOT, "dist") + path.sep)) return send(res, 403, "Forbidden", "text/plain");
      return serveFile(res, fs.existsSync(file) && fs.statSync(file).isDirectory() ? path.join(file, "index.html") : file);
    }
    send(res, 404, "Not found", "text/plain");
  } catch (e) {
    send(res, 500, { error: e.message });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`ELIO Studio is running at http://localhost:${PORT}`);
  console.log(`Agent uses: ${CLAUDE_BIN}`);
  pump();
});
