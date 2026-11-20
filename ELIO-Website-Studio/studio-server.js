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
const crypto = require("crypto");

const ROOT = __dirname;
const PORT = +process.env.PORT || 4321;
const DATA_DIR = path.join(ROOT, "data");
const DATA_FILE = path.join(DATA_DIR, "studio.json");
const INCOMING = path.join(ROOT, "clients", "_incoming");
const AGENT_TIMEOUT_MS = 15 * 60 * 1000;
const SETTINGS_FILE = path.join(DATA_DIR, "settings.json");
const NETLIFY_API = process.env.NETLIFY_API || "https://api.netlify.com/api/v1";

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
  const example = fs.readFileSync(path.join(ROOT, "clients", "lost-in-da-souse-kitchen", "site.config.json"), "utf8");
  return `You are the lead designer and copywriter at ELIO Website Studio. You build demo websites that local
business owners see and immediately want to buy. They must look like a top restaurant chain or premium local
brand made them: bold, confident, specific, and built to make the phone ring or orders come in.

THE USER'S REQUEST:
"""
${request}
"""

STEP 1: RESEARCH (use WebSearch and WebFetch)
Find the exact business and location. Collect: name, address, phone, hours for each day, what they sell,
signature items, real prices if published, Google rating and review count, official website, official online
ordering links (their own site, Toast, Square, ChowNow, order.online, DoorDash, Uber Eats, Grubhub), and social
pages (Instagram, Facebook, TikTok). Details in the user's request always win over what you find.

STEP 2: WRITE ONE JSON FILE to exactly this path: ${outFile}
Use this finished, high-quality config as your model for format, tone and level of detail:
${example}

Every field you can use:
- business: name, tagline, phone, email, address, hours: [{days, time}]
- theme.style: "bold" (restaurants, food trucks, barbers, gyms, auto, anything loud),
  "elegant" (salons, spas, boutiques, fine dining, law, real estate), "modern" (trades, cleaning, clinics, tech, everything else)
- theme.primary: a deep brand color (white text must read well on it). theme.accent: a bright pop color for buttons.
  Base both on the business's own logo/signage colors when you can find them.
- announcement: one short line for the top bar (an opening, late hours, a real promotion). Optional.
- hero: eyebrow (location or short claim), headline (max 6 words, punchy, in the business's voice),
  subheadline (one sentence: what, where, why), ctaText + ctaLink (optional: the main action URL),
  secondaryText + secondaryLink (optional), image (optional photo URL, see PHOTOS)
- highlights: 2-3 short real selling points shown as chips (e.g. "Open until 2 AM", "Family owned", "Free estimates")
- rating: {value, count, source} ONLY if you found the real numbers (e.g. Google)
- hoursSummary: one short line for the info strip (e.g. "Open daily · until 2 AM")
- order: [{label, url}] official ordering/booking links only, best first (e.g. {"label":"Order pickup","url":...})
- servicesNav ("Menu" for food), servicesEyebrow, servicesTitle, servicesIntro (one sentence)
- services: 3, 4 or 6 items of {title, description, price?, tag?, image?}. Signature items first.
  tag examples: "Most popular", "Signature", "New". Descriptions make people hungry/interested: concrete, sensory, short.
- band: {headline, text}: a bold call-to-action line, e.g. "Late-night cravings? We got you."
- about, aboutTitle, aboutEyebrow, aboutImage?
- gallery: 3 or 5 photo URLs (optional, see PHOTOS)
- social: {instagram, facebook, tiktok} full URLs you verified
- contactTitle: e.g. "Pull up", "Visit us", "Book your visit"
- seo: {title, description} with the city and main service for Google
- testimonials: always []

PHOTOS AND VIDEO (they make the biggest difference, always include them):
- First choice: direct image links (.jpg, .jpeg, .png, .webp) from the business's OWN official website or official
  ordering page, found with WebFetch.
- Otherwise use free stock media as SAMPLES that match what the business sells (e.g. fried wings, catfish, burgers,
  a barber chair, a clean bathroom): photos from images.unsplash.com or images.pexels.com, and optionally one short
  looping video as a direct .mp4 link from videos.pexels.com. Both sites allow free commercial use. Only use URLs you
  confirmed exist with WebFetch. Never use Google, Yelp, Instagram, Facebook or other people's photos.
  When any stock media is used, set "sampleMedia": true (the site then shows a small "Sample photos" label).
- Fill: hero.image (wide, dramatic, appetizing), an image for every service card, "gallery" with exactly 5 photos,
  "aboutImage" (portrait). Add hero.video (an .mp4 URL) only if you found a fitting one; hero.image stays as its poster.
- Use image size parameters for speed, e.g. images.unsplash.com/...?w=1600&q=80 for the hero and ?w=800&q=75 for cards.
- In your final notes, say which photos/video are stock samples to replace with the owner's own.

RULES:
- Never invent facts: no made-up prices, reviews, ratings, awards, years in business, staff names or links.
  If unsure, leave the field out.
- "about": 2-3 sentences from real facts, ending with "(Demo text: confirm with the owner.)"
- No phone found: set hero.ctaText "Get directions" and hero.ctaLink to a Google Maps search URL for the address
  (unless there is an official order link, which then comes first).
- Don't create or change any other file.

QUALITY CHECK before you finish: Would the owner be proud to show this? Is the headline specific to THIS
business (not generic)? Are the colors right for the brand? Is every fact verified?

Finally, reply with ONLY a short plain-text list for the user: what to confirm with the owner before launch
(e.g. hours that differ between listings, prices not found, photos used, missing phone). No other commentary.`;
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


// ---------- publishing (Netlify) ----------
// Your Netlify token stays in data/settings.json on this computer and is never sent to the browser.
function loadSettings() { try { return JSON.parse(fs.readFileSync(SETTINGS_FILE, "utf8")); } catch { return {}; } }
function saveSettings(x) { fs.mkdirSync(DATA_DIR, { recursive: true }); fs.writeFileSync(SETTINGS_FILE, JSON.stringify(x, null, 2), { mode: 0o600 }); }

async function netlify(method, url, body, headers = {}) {
  const token = loadSettings().netlifyToken;
  if (!token) throw new Error("Connect your Netlify account first.");
  const r = await fetch(NETLIFY_API + url, {
    method,
    headers: { Authorization: `Bearer ${token}`, ...(body && !Buffer.isBuffer(body) ? { "Content-Type": "application/json" } : {}), ...headers },
    body: body ? (Buffer.isBuffer(body) ? body : JSON.stringify(body)) : undefined,
  });
  const text = await r.text();
  let data; try { data = text ? JSON.parse(text) : {}; } catch { data = { message: text }; }
  if (r.status === 401) throw new Error("Netlify didn't accept your token. Paste a new one in Publishing settings.");
  if (!r.ok) throw new Error(`Netlify error ${r.status}: ${String(data.message || data.error || text).slice(0, 200)}`);
  return data;
}

function listFiles(dir, base = dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    return e.isDirectory() ? listFiles(full, base) : [{ full, rel: "/" + path.relative(base, full).split(path.sep).join("/") }];
  });
}

async function publishItem(item) {
  const dir = path.join(ROOT, "dist", item.slug || "");
  if (!item.slug || !fs.existsSync(path.join(dir, "index.html"))) throw new Error("This business has no demo website to publish yet.");
  let siteId = item.netlifySiteId;
  if (siteId) {
    try { await netlify("GET", `/sites/${siteId}`); } catch { siteId = null; }
  }
  if (!siteId) {
    const name = `${slugify(item.name).slice(0, 40)}-demo-${crypto.randomBytes(3).toString("hex")}`;
    const site = await netlify("POST", "/sites", { name });
    siteId = site.id;
    item.netlifySiteId = site.id;
  }
  const files = listFiles(dir);
  const digests = {}, byHash = {};
  for (const f of files) {
    const h = crypto.createHash("sha1").update(fs.readFileSync(f.full)).digest("hex");
    digests[f.rel] = h; byHash[h] = f;
  }
  const deploy = await netlify("POST", `/sites/${siteId}/deploys`, { files: digests });
  for (const h of deploy.required || []) {
    const f = byHash[h];
    if (f) await netlify("PUT", `/deploys/${deploy.id}/files${f.rel.split("/").map(encodeURIComponent).join("/")}`, fs.readFileSync(f.full), { "Content-Type": "application/octet-stream" });
  }
  let d = deploy;
  for (let i = 0; i < 30 && d.state !== "ready"; i++) {
    if (d.state === "error") throw new Error("Netlify couldn't finish publishing. Try again.");
    await new Promise((r) => setTimeout(r, 1000));
    d = await netlify("GET", `/deploys/${deploy.id}`);
  }
  const site = await netlify("GET", `/sites/${siteId}`);
  item.publicUrl = site.ssl_url || site.url || d.ssl_url || d.url;
  item.publishedAt = new Date().toISOString();
  return item;
}

async function unpublishItem(item) {
  if (item.netlifySiteId) {
    try { await netlify("DELETE", `/sites/${item.netlifySiteId}`); } catch (e) { if (!/404/.test(e.message)) throw e; }
  }
  delete item.netlifySiteId; delete item.publicUrl; delete item.publishedAt;
  return item;
}

// ---------- routes ----------
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const p = decodeURIComponent(url.pathname);
  try {
    if (p === "/" || p === "/index.html") return serveFile(res, path.join(ROOT, "dashboard", "index.html"));
    if (p === "/api/state" && req.method === "GET") return send(res, 200, { ...state, agent: true, running, netlify: !!loadSettings().netlifyToken });
    if (p === "/api/settings/netlify" && req.method === "POST") {
      const body = await readBody(req);
      const token = String(body.token || "").trim();
      const settings = loadSettings();
      if (!token) { delete settings.netlifyToken; saveSettings(settings); return send(res, 200, { ok: true, netlify: false }); }
      settings.netlifyToken = token; saveSettings(settings);
      try { await netlify("GET", "/user"); } catch (e) { delete settings.netlifyToken; saveSettings(settings); return send(res, 400, { error: e.message }); }
      return send(res, 200, { ok: true, netlify: true });
    }
    const pub = /^\/api\/items\/(\d+)\/(publish|unpublish)$/.exec(p);
    if (pub && req.method === "POST") {
      const item = state.items.find((i) => String(i.id) === pub[1]);
      if (!item) return send(res, 404, { error: "That business isn't on the dashboard any more." });
      try {
        await (pub[2] === "publish" ? publishItem(item) : unpublishItem(item));
        save();
        return send(res, 200, { item });
      } catch (e) {
        save();
        return send(res, 400, { error: e.message });
      }
    }
    if (p === "/api/items" && req.method === "PUT") {
      const body = await readBody(req);
      if (!Array.isArray(body.items)) return send(res, 400, { error: "items must be a list" });
      // Keep publishing details the browser may not have yet.
      const prev = new Map(state.items.map((i) => [String(i.id), i]));
      state.items = body.items.map((i) => {
        const o = prev.get(String(i.id)) || {};
        for (const k of ["netlifySiteId", "publicUrl", "publishedAt", "slug", "demo"]) if (i[k] === undefined && o[k] !== undefined) i[k] = o[k];
        return i;
      });
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
