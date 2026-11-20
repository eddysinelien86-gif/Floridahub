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
const TWILIO_API = process.env.TWILIO_API || "https://api.twilio.com/2010-04-01";

const CLAUDE_BIN =
  process.env.CLAUDE_BIN ||
  [path.join(os.homedir(), ".local", "bin", "claude")].find((p) => fs.existsSync(p)) ||
  "claude";

// ---------- storage ----------
function load() {
  try {
    const d = JSON.parse(fs.readFileSync(DATA_FILE, "utf8"));
    return { items: d.items || [], jobs: d.jobs || [], imported: !!d.imported, pausedUntil: d.pausedUntil || 0 };
  } catch {
    return { items: [], jobs: [], imported: false, pausedUntil: 0 };
  }
}
let state = load();
// A job that was cut off when the studio closed goes back in line. Waiting jobs keep waiting.
for (const j of state.jobs) if (j.status === "working") {
  j.status = "queued";
  j.step = "Waiting to start (the studio was restarted)";
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
const RETRY_FALLBACK_MS = 30 * 60 * 1000;   // when the reset time is unknown, try again in 30 minutes
const MAX_LIMIT_WAITS = 12;
const TICK_MS = +process.env.STUDIO_TICK_MS || 60 * 1000;
const RESET_BUFFER_MS = process.env.STUDIO_RESET_BUFFER_MS !== undefined ? +process.env.STUDIO_RESET_BUFFER_MS : 60 * 1000;

// Claude Code reports the reset as "...usage limit reached|<unix seconds>". Other wordings fall back to 30 minutes.
function resetTimeFrom(text) {
  const m = /\|(\d{10})\b/.exec(text || "");
  const t = m ? +m[1] * 1000 : 0;
  return t > Date.now() ? t + RESET_BUFFER_MS : Date.now() + RETRY_FALLBACK_MS;
}

function resumeIfReady() {
  if (state.pausedUntil && Date.now() >= state.pausedUntil) {
    state.pausedUntil = 0;
    for (const j of state.jobs) if (j.status === "waiting") { j.status = "queued"; j.step = "Usage is back. Starting soon"; }
    save();
  }
}

function pump() {
  if (running) return;
  resumeIfReady();
  if (state.pausedUntil) return;
  const job = [...state.jobs].reverse().find((j) => j.status === "queued");   // oldest request first
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
      // stdin "ignore": Claude Code must not wait for piped input.
      child = spawn(CLAUDE_BIN, args, { cwd: ROOT, env: process.env, stdio: ["ignore", "pipe", "pipe"] });
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
      let notes = "", isError = false;
      try { const r = JSON.parse(out); notes = String(r.result || "").trim(); isError = !!r.is_error; } catch { notes = out.trim(); }
      const why = (notes || err.split("\n").filter((l) => l.trim() && !/no stdin data received|redirect stdin/i.test(l)).join(" ")).trim();
      if (!fs.existsSync(outFile)) {
        if (code === null) return fail("It took too long and was stopped. Try again with more details (town, phone).");
        if (/limit|usage|quota|rate/i.test(why)) return waitForReset(why);
        if (/log ?in|auth|credential|unauthori/i.test(why)) return fail("Claude Code isn't signed in. Open a terminal, run `claude`, sign in, then try again.");
        return fail(`The agent didn't produce a website.${why ? " " + why.slice(-400) : (isError ? " Claude Code reported an error." : "")}`);
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

    function waitForReset(why) {
      job.limitWaits = (job.limitWaits || 0) + 1;
      if (job.limitWaits > MAX_LIMIT_WAITS) return fail(`Your Claude usage limit kept blocking this demo. Try again later. (${why.slice(0, 160)})`);
      state.pausedUntil = resetTimeFrom(why);
      Object.assign(job, { status: "waiting", step: "Waiting for your usage to reset", retryAt: new Date(state.pausedUntil).toISOString() });
      // Everything else in line waits too, instead of failing one by one.
      for (const j of state.jobs) if (j.status === "queued") { j.status = "waiting"; j.step = "Waiting for your usage to reset"; j.retryAt = job.retryAt; }
      resolve();
    }

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
  let site = await netlify("GET", `/sites/${siteId}`);
  // With your own domain (bought through Netlify, so Netlify runs its DNS), each demo gets
  // https://<business>.<your-domain>. Netlify creates the address and its security certificate.
  const domain = loadSettings().demoDomain;
  item.domainNote = "";
  if (domain) {
    const host = `${slugify(item.name).slice(0, 50)}.${domain}`;
    if (site.custom_domain !== host) {
      try { site = await netlify("PATCH", `/sites/${siteId}`, { custom_domain: host }); }
      catch (e) { item.domainNote = `Couldn't set up ${host}: ${e.message}. Using the Netlify address for now.`; }
    }
    if (site.custom_domain === host) {
      item.publicUrl = `https://${host}`;
      item.netlifyUrl = site.ssl_url || site.url;
      item.publishedAt = new Date().toISOString();
      return item;
    }
  }
  item.publicUrl = site.ssl_url || site.url || d.ssl_url || d.url;
  item.publishedAt = new Date().toISOString();
  return item;
}

// ---------- texting (Twilio) ----------
const normalizePhone = (p) => {
  const d = String(p || "").replace(/[^\d+]/g, "");
  if (/^\+\d{10,15}$/.test(d)) return d;
  const digits = d.replace(/\D/g, "");
  if (digits.length === 10) return "+1" + digits;
  if (digits.length === 11 && digits.startsWith("1")) return "+" + digits;
  return "";
};

async function sendText(to, body) {
  const t = loadSettings().twilio || {};
  if (!t.sid || !t.token || !t.from) throw new Error("Set up texting first (Texting settings).");
  const num = normalizePhone(to);
  if (!num) throw new Error("That phone number doesn't look right. Use 10 digits, like (954) 555-1234.");
  const r = await fetch(`${TWILIO_API}/Accounts/${encodeURIComponent(t.sid)}/Messages.json`, {
    method: "POST",
    headers: { Authorization: "Basic " + Buffer.from(`${t.sid}:${t.token}`).toString("base64"), "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ To: num, From: t.from, Body: body }),
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401) throw new Error("Twilio didn't accept your Account SID or Auth Token. Check Texting settings.");
  if (!r.ok) throw new Error(`Text not sent: ${data.message || "Twilio error " + r.status}`);
  return { sid: data.sid, status: data.status, to: num };
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
    if (p === "/api/state" && req.method === "GET") {
      const st = loadSettings();
      return send(res, 200, { ...state, agent: true, running, netlify: !!st.netlifyToken, demoDomain: st.demoDomain || "",
        texting: !!(st.twilio && st.twilio.sid && st.twilio.token && st.twilio.from), textFrom: (st.twilio && st.twilio.from) || "" });
    }
    if (p === "/api/settings/domain" && req.method === "POST") {
      const body = await readBody(req);
      const domain = String(body.domain || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/.*$/, "");
      if (domain && !/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(domain)) return send(res, 400, { error: "Type just the domain, like eliostudio.com" });
      const st = loadSettings(); st.demoDomain = domain; saveSettings(st);
      return send(res, 200, { ok: true, demoDomain: domain });
    }
    if (p === "/api/settings/twilio" && req.method === "POST") {
      const body = await readBody(req);
      const st = loadSettings();
      if (body.clear) { delete st.twilio; saveSettings(st); return send(res, 200, { ok: true, texting: false }); }
      const from = normalizePhone(body.from);
      const sid = String(body.sid || "").trim(), token = String(body.token || "").trim();
      if (!/^AC[0-9a-f]{32}$/i.test(sid)) return send(res, 400, { error: "The Account SID starts with AC followed by 32 letters and numbers." });
      if (!token) return send(res, 400, { error: "Paste your Auth Token." });
      if (!from) return send(res, 400, { error: "Type your Twilio phone number, like (954) 555-1234." });
      // Check the keys work before saving them.
      const r = await fetch(`${TWILIO_API}/Accounts/${encodeURIComponent(sid)}.json`, { headers: { Authorization: "Basic " + Buffer.from(`${sid}:${token}`).toString("base64") } }).catch(() => null);
      if (!r) return send(res, 400, { error: "Couldn't reach Twilio. Check your internet connection." });
      if (r.status === 401 || r.status === 404) return send(res, 400, { error: "Twilio didn't accept that Account SID and Auth Token." });
      st.twilio = { sid, token, from }; saveSettings(st);
      return send(res, 200, { ok: true, texting: true, textFrom: from });
    }
    const tx = /^\/api\/items\/(\d+)\/text$/.exec(p);
    if (tx && req.method === "POST") {
      const item = state.items.find((i) => String(i.id) === tx[1]);
      if (!item) return send(res, 404, { error: "That business isn't on the dashboard any more." });
      const body = await readBody(req);
      const msg = String(body.message || "").trim();
      if (!item.publicUrl) return send(res, 400, { error: "Put the demo online first." });
      if (!msg.includes(item.publicUrl)) return send(res, 400, { error: "The message must include the demo link." });
      try {
        const r = await sendText(body.to, /reply stop/i.test(msg) ? msg : msg + "\n\nReply STOP to opt out.");
        item.messages = [...(item.messages || []), { at: new Date().toISOString(), via: "text", to: r.to, status: r.status, sid: r.sid }];
        item.sentAt = new Date().toISOString().slice(0, 10); item.sentVia = "text";
        if (["Lead", "Demo ready"].includes(item.stage)) item.stage = "Demo sent";
        item.next = "Follow up on demo"; item.due = addDays(2);
        save();
        return send(res, 200, { item, to: r.to });
      } catch (e) { return send(res, 400, { error: e.message }); }
    }
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
        for (const k of ["netlifySiteId", "publicUrl", "publishedAt", "slug", "demo", "netlifyUrl", "domainNote", "messages"]) if (i[k] === undefined && o[k] !== undefined) i[k] = o[k];
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
      const paused = state.pausedUntil > Date.now();
      const job = { id: "job-" + Date.now(), request, createdAt: new Date().toISOString(),
        ...(paused ? { status: "waiting", step: "Waiting for your usage to reset", retryAt: new Date(state.pausedUntil).toISOString() } : { status: "queued", step: "Waiting to start" }) };
      state.jobs.unshift(job);
      state.jobs = state.jobs.slice(0, 50);
      save();
      pump();
      return send(res, 200, job);
    }
    if (p.startsWith("/api/jobs/") && req.method === "DELETE") {
      state.jobs = state.jobs.filter((j) => j.id !== p.slice(10) || j.status === "working");
      if (!state.jobs.some((j) => j.status === "waiting")) state.pausedUntil = 0;
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
  setInterval(pump, TICK_MS);   // checks every minute whether usage is back
});
