#!/usr/bin/env node
// ELIO Website Studio — client site generator.
// Usage:
//   node build.js <client-folder>      e.g. node build.js clients/sunshine-plumbing
//   node build.js --all                builds every folder in clients/
// Output goes to dist/<client-folder-name>/index.html (no dependencies needed).

const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const TEMPLATE = fs.readFileSync(path.join(ROOT, "template", "index.html"), "utf8");

const esc = (s = "") =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

function section(id, title, inner) {
  return `<section id="${id}" class="section"><div class="wrap"><h2>${esc(title)}</h2>${inner}</div></section>`;
}

function render(cfg) {
  const b = cfg.business || {};
  const t = cfg.theme || {};
  const hero = cfg.hero || {};
  const services = cfg.services || [];
  const testimonials = cfg.testimonials || [];
  const hours = b.hours || [];

  const nav = [
    services.length && `<a href="#services">Services</a>`,
    cfg.about && `<a href="#about">About</a>`,
    testimonials.length && `<a href="#reviews">Reviews</a>`,
    `<a href="#contact">Contact</a>`,
  ]
    .filter(Boolean)
    .join("");

  const servicesHtml = services.length
    ? section(
        "services",
        cfg.servicesTitle || "What we do",
        `<div class="grid">${services
          .map(
            (s) => `<article class="card">
  <h3>${esc(s.title)}</h3>
  <p>${esc(s.description)}</p>
  ${s.price ? `<p class="price">${esc(s.price)}</p>` : ""}
</article>`
          )
          .join("")}</div>`
      )
    : "";

  const aboutHtml = cfg.about
    ? section("about", cfg.aboutTitle || `About ${b.name}`, `<p class="lead">${esc(cfg.about)}</p>`)
    : "";

  const reviewsHtml = testimonials.length
    ? section(
        "reviews",
        "What customers say",
        `<div class="grid">${testimonials
          .map((r) => `<blockquote class="card"><p>“${esc(r.quote)}”</p><cite>— ${esc(r.name)}</cite></blockquote>`)
          .join("")}</div>`
      )
    : "";

  const contactLines = [
    b.phone && `<p><strong>Phone:</strong> <a href="tel:${esc(b.phone.replace(/[^\d+]/g, ""))}">${esc(b.phone)}</a></p>`,
    b.email && `<p><strong>Email:</strong> <a href="mailto:${esc(b.email)}">${esc(b.email)}</a></p>`,
    b.address &&
      `<p><strong>Address:</strong> <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
        b.address
      )}" target="_blank" rel="noopener">${esc(b.address)}</a></p>`,
  ]
    .filter(Boolean)
    .join("");

  const hoursHtml = hours.length
    ? `<h3>Hours</h3><ul class="hours">${hours
        .map((h) => `<li><span>${esc(h.days)}</span><span>${esc(h.time)}</span></li>`)
        .join("")}</ul>`
    : "";

  const form = cfg.contactFormAction
    ? `<form class="card form" action="${esc(cfg.contactFormAction)}" method="POST">
  <label>Name<input name="name" required></label>
  <label>Email<input name="email" type="email" required></label>
  <label>Phone<input name="phone" type="tel"></label>
  <label>How can we help?<textarea name="message" rows="4" required></textarea></label>
  <button class="btn" type="submit">Send message</button>
</form>`
    : "";

  const contactHtml = section(
    "contact",
    cfg.contactTitle || "Get in touch",
    `<div class="contact ${form ? "two" : ""}"><div>${contactLines}${hoursHtml}</div>${form}</div>`
  );

  const ctaHref = hero.ctaLink || (b.phone ? `tel:${b.phone.replace(/[^\d+]/g, "")}` : "#contact");

  const vars = {
    TITLE: esc(cfg.seo?.title || `${b.name} | ${b.tagline || ""}`),
    DESCRIPTION: esc(cfg.seo?.description || hero.subheadline || b.tagline || ""),
    PRIMARY: esc(t.primary || "#0f4c81"),
    ACCENT: esc(t.accent || "#f4a261"),
    FONT: esc(t.font || "system-ui, -apple-system, Segoe UI, Roboto, sans-serif"),
    NAME: esc(b.name || "Business Name"),
    NAV: nav,
    HEADLINE: esc(hero.headline || b.name),
    SUBHEADLINE: esc(hero.subheadline || b.tagline || ""),
    CTA_TEXT: esc(hero.ctaText || "Contact us"),
    CTA_HREF: esc(ctaHref),
    HERO_IMAGE: hero.image ? `background-image:linear-gradient(rgba(0,0,0,.55),rgba(0,0,0,.55)),url('${esc(hero.image)}');` : "",
    SERVICES: servicesHtml,
    ABOUT: aboutHtml,
    REVIEWS: reviewsHtml,
    CONTACT: contactHtml,
    YEAR: String(new Date().getFullYear()),
    CREDIT: cfg.hideCredit ? "" : ` · Website by ELIO Website Studio`,
  };

  return TEMPLATE.replace(/\{\{(\w+)\}\}/g, (_, k) => (k in vars ? vars[k] : ""));
}

function build(clientDir) {
  const dir = path.resolve(ROOT, clientDir);
  const cfgPath = path.join(dir, "site.config.json");
  if (!fs.existsSync(cfgPath)) {
    console.error(`No site.config.json in ${dir}`);
    process.exitCode = 1;
    return;
  }
  const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  const out = path.join(ROOT, "dist", path.basename(dir));
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "index.html"), render(cfg));
  // Copy any client assets (images, logo) alongside the page.
  const assets = path.join(dir, "assets");
  if (fs.existsSync(assets)) fs.cpSync(assets, path.join(out, "assets"), { recursive: true });
  console.log(`Built ${path.relative(ROOT, out)}/index.html`);
}

const arg = process.argv[2];
if (!arg) {
  console.log("Usage: node build.js <clients/name> | --all");
  process.exit(1);
}
if (arg === "--all") {
  const clients = path.join(ROOT, "clients");
  for (const name of fs.readdirSync(clients)) {
    if (fs.statSync(path.join(clients, name)).isDirectory()) build(path.join("clients", name));
  }
} else {
  build(arg);
}
