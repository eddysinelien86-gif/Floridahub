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
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const cssUrl = (u) => `url('${String(u).replace(/['\\\n\r]/g, (c) => encodeURIComponent(c))}')`;

// Three looks. The agent (or you) picks one per client with "theme.style".
const STYLES = {
  bold: {
    fonts: "family=Anton&family=Inter:wght@400;600;700;800",
    display: "'Anton', Impact, 'Arial Narrow', sans-serif",
    body: "'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif",
    radius: "10px", headCase: "uppercase", headTrack: ".01em", headWeight: "400",
  },
  elegant: {
    fonts: "family=Playfair+Display:wght@600;700&family=Lato:wght@400;700;900",
    display: "'Playfair Display', Georgia, 'Times New Roman', serif",
    body: "'Lato', system-ui, -apple-system, 'Segoe UI', sans-serif",
    radius: "4px", headCase: "none", headTrack: "0", headWeight: "700",
  },
  modern: {
    fonts: "family=Plus+Jakarta+Sans:wght@400;600;700;800",
    display: "'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",
    body: "'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif",
    radius: "16px", headCase: "none", headTrack: "-.02em", headWeight: "800",
  },
};

const ICON = {
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>',
  phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>',
  bag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 7h12l1 14H5L6 7z"/><path d="M9 7a3 3 0 0 1 6 0"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5L2.5 9.4l6.6-.9z"/></svg>',
  mail: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4.5 4.5L19 7"/></svg>',
  instagram: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor"/></svg>',
  facebook: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M14 8h3V4h-3a4 4 0 0 0-4 4v2H8v4h2v8h4v-8h3l1-4h-4V8z"/></svg>',
  tiktok: '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M16 3c.3 2.3 1.9 4 4 4.3v3.2a7.6 7.6 0 0 1-4-1.3V15a6 6 0 1 1-6-6v3.3a2.8 2.8 0 1 0 2.8 2.7V3H16z"/></svg>',
  web: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
};

// Black or white text, whichever reads better on the given color.
function inkFor(hex) {
  const m = /^#?([\da-f]{6})$/i.exec(String(hex || "").trim());
  if (!m) return "#111111";
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? "#111111" : "#ffffff";
}

const telHref = (p) => `tel:${String(p).replace(/[^\d+]/g, "")}`;
const mapsHref = (a) => `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(a)}`;
const btn = (cls, href, label, icon) => {
  const ext = /^https?:/.test(href) ? ' target="_blank" rel="noopener"' : "";
  return `<a class="btn ${cls}" href="${esc(href)}"${ext}>${icon ? ICON[icon] : ""}${esc(label)}</a>`;
};

function render(cfg) {
  const b = cfg.business || {};
  const t = cfg.theme || {};
  const hero = cfg.hero || {};
  const style = STYLES[t.style] || STYLES.modern;
  const services = cfg.services || [];
  const testimonials = cfg.testimonials || [];
  const hours = b.hours || [];
  const order = (cfg.order || []).filter((o) => o && o.url);
  const social = cfg.social || {};
  const rating = cfg.rating && cfg.rating.value ? cfg.rating : null;
  const directions = b.address ? mapsHref(b.address) : "";

  // The one thing we most want visitors to do.
  const isMaps = (u) => /google\.[a-z.]+\/maps|maps\.google|maps\.apple/.test(String(u));
  const primary =
    hero.ctaLink ? { href: hero.ctaLink, label: hero.ctaText || "Get started", icon: isMaps(hero.ctaLink) ? "pin" : "bag" }
    : order[0] ? { href: order[0].url, label: hero.ctaText || order[0].label || "Order online", icon: "bag" }
    : b.phone ? { href: telHref(b.phone), label: hero.ctaText || `Call ${b.phone}`, icon: "phone" }
    : { href: "#visit", label: hero.ctaText || "Get in touch", icon: "" };
  const secondary =
    hero.secondaryLink ? { href: hero.secondaryLink, label: hero.secondaryText || "Learn more", icon: "" }
    : directions && !isMaps(primary.href) ? { href: directions, label: "Get directions", icon: "pin" }
    : b.phone && !primary.href.startsWith("tel:") ? { href: telHref(b.phone), label: "Call us", icon: "phone" }
    : null;

  const servicesNav = cfg.servicesNav || "Services";
  const nav = [
    services.length && `<a href="#services">${esc(servicesNav)}</a>`,
    cfg.about && `<a href="#about">About</a>`,
    testimonials.length && `<a href="#reviews">Reviews</a>`,
    `<a href="#visit">${b.address ? "Visit" : "Contact"}</a>`,
  ].filter(Boolean).join("");

  // Hero
  const chips = [
    ...(cfg.highlights || []).map((h) => `<li>${ICON.check}${esc(h)}</li>`),
    rating && `<li>${ICON.star}${esc(rating.value)} on ${esc(rating.source || "Google")}${rating.count ? ` (${esc(rating.count)} reviews)` : ""}</li>`,
  ].filter(Boolean).slice(0, 4);
  const heroHtml = `<section class="hero${hero.image ? " has-img" : ""}"${hero.image ? ` style="background-image:${cssUrl(hero.image)}"` : ""}>
  <div class="pattern" aria-hidden="true"></div>
  <div class="wrap">
    ${hero.eyebrow || b.tagline ? `<p class="eyebrow" style="color:var(--accent)">${esc(hero.eyebrow || b.tagline)}</p>` : ""}
    <h1>${esc(hero.headline || b.name)}</h1>
    ${hero.subheadline ? `<p class="sub">${esc(hero.subheadline)}</p>` : ""}
    <div class="ctas">${btn("btn-accent", primary.href, primary.label, primary.icon)}${secondary ? btn("btn-light", secondary.href, secondary.label, secondary.icon) : ""}</div>
    ${chips.length ? `<ul class="chips">${chips.join("")}</ul>` : ""}
  </div>
</section>`;

  // Info strip
  const hoursSummary = cfg.hoursSummary || (hours[0] ? `${hours[0].days}: ${hours[0].time}` : "");
  const cells = [
    hoursSummary && `<div class="cell">${ICON.clock}<div><div class="k">Hours</div><div class="v">${esc(hoursSummary)}</div></div></div>`,
    b.address && `<div class="cell">${ICON.pin}<div><div class="k">Location</div><div class="v"><a href="${esc(directions)}" target="_blank" rel="noopener">${esc(b.address)}</a></div></div></div>`,
    b.phone ? `<div class="cell">${ICON.phone}<div><div class="k">Call</div><div class="v"><a href="${esc(telHref(b.phone))}">${esc(b.phone)}</a></div></div></div>`
      : order[0] ? `<div class="cell">${ICON.bag}<div><div class="k">Order</div><div class="v"><a href="${esc(order[0].url)}" target="_blank" rel="noopener">${esc(order[0].label || "Order online")}</a></div></div></div>`
      : b.email && `<div class="cell">${ICON.mail}<div><div class="k">Email</div><div class="v"><a href="mailto:${esc(b.email)}">${esc(b.email)}</a></div></div></div>`,
  ].filter(Boolean);
  const infoHtml = cells.length ? `<div class="info"><div class="wrap">${cells.join("")}</div></div>` : "";

  // Menu / services
  const anyImg = services.some((s) => s.image);
  const servicesHtml = services.length ? `<section class="block" id="services"><div class="wrap">
  <div class="head"><div><p class="eyebrow">${esc(cfg.servicesEyebrow || servicesNav)}</p><h2>${esc(cfg.servicesTitle || "What we do")}</h2></div>${cfg.servicesIntro ? `<p>${esc(cfg.servicesIntro)}</p>` : ""}</div>
  <div class="cards">${services.map((s) => `<article class="card">
    ${anyImg ? (s.image ? `<div class="ph" style="background-image:${cssUrl(s.image)}" role="img" aria-label="${esc(s.title)}"></div>` : `<div class="ph blank" aria-hidden="true"><span>${esc(s.title)}</span></div>`) : ""}
    <div class="body">${s.tag ? `<span class="tag">${esc(s.tag)}</span>` : ""}<div class="row"><h3>${esc(s.title)}</h3>${s.price ? `<span class="price">${esc(s.price)}</span>` : ""}</div><p>${esc(s.description)}</p></div>
  </article>`).join("")}</div>
</div></section>` : "";

  // Call-to-action band
  const bandBtns = order.length
    ? order.slice(0, 3).map((o, i) => btn(i ? "btn-light" : "btn-accent", o.url, o.label || "Order online", i ? "" : "bag")).join("")
    : btn("btn-accent", primary.href, primary.label, primary.icon);
  const band = cfg.band || {};
  const bandHtml = band.headline !== "" ? `<section class="band"><div class="wrap">
  <div><h2>${esc(band.headline || "Ready when you are.")}</h2>${band.text ? `<p>${esc(band.text)}</p>` : ""}</div>
  <div class="ctas">${bandBtns}</div>
</div></section>` : "";

  // Gallery
  const pics = (cfg.gallery || []).map((g) => (typeof g === "string" ? { src: g } : g)).filter((g) => g && g.src);
  const shown = pics.length >= 5 ? pics.slice(0, 5) : pics.length >= 3 ? pics.slice(0, 3) : [];
  const galleryHtml = shown.length ? `<section class="block tint" id="gallery"><div class="wrap">
  <div class="head"><div><p class="eyebrow">Gallery</p><h2>${esc(cfg.galleryTitle || "Take a look")}</h2></div></div>
  <div class="gallery"${shown.length === 3 ? ' style="grid-template-columns:repeat(3,1fr);grid-auto-rows:260px"' : ""}>${shown.map((g, i) =>
    `<figure role="img" aria-label="${esc(g.alt || b.name)}" style="background-image:${cssUrl(g.src)}${shown.length === 3 && i === 0 ? ";grid-column:auto;grid-row:auto" : ""}"></figure>`).join("")}</div>
</div></section>` : "";

  // About
  const ratingHtml = rating ? `<div class="rating"><span class="stars" aria-hidden="true">★★★★★</span>${esc(rating.value)} on ${esc(rating.source || "Google")}${rating.count ? ` <small>(${esc(rating.count)} reviews)</small>` : ""}</div>` : "";
  const aboutHtml = cfg.about ? `<section class="block" id="about"><div class="wrap"><div class="about${cfg.aboutImage ? "" : " solo"}">
  <div><p class="eyebrow">${esc(cfg.aboutEyebrow || "Our story")}</p><h2>${esc(cfg.aboutTitle || `About ${b.name}`)}</h2><p>${esc(cfg.about)}</p>${ratingHtml}</div>
  ${cfg.aboutImage ? `<div class="pic" role="img" aria-label="${esc(b.name)}" style="background-image:${cssUrl(cfg.aboutImage)}"></div>` : ""}
</div></div></section>` : "";

  // Reviews (real ones only)
  const reviewsHtml = testimonials.length ? `<section class="block" id="reviews"><div class="wrap">
  <div class="head"><div><p class="eyebrow">Reviews</p><h2>What customers say</h2></div></div>
  <div class="reviews">${testimonials.map((r) => `<blockquote class="review"><p>“${esc(r.quote)}”</p><cite>${esc(r.name)}</cite></blockquote>`).join("")}</div>
</div></section>` : "";

  // Visit / contact
  const form = cfg.contactFormAction ? `<form class="form" action="${esc(cfg.contactFormAction)}" method="POST">
    <label>Name<input name="name" required></label>
    <label>Email<input name="email" type="email" required></label>
    <label>Phone<input name="phone" type="tel"></label>
    <label>How can we help?<textarea name="message" rows="4" required></textarea></label>
    <button class="btn btn-primary" type="submit">Send message</button>
  </form>` : "";
  const visitHtml = `<section class="block tint" id="visit"><div class="wrap"><div class="visit">
  <div>
    <p class="eyebrow">${b.address ? "Visit us" : "Contact"}</p>
    <h2>${esc(cfg.contactTitle || (b.address ? "Come see us" : "Get in touch"))}</h2>
    ${b.address ? `<div class="line">${ICON.pin}<a href="${esc(directions)}" target="_blank" rel="noopener">${esc(b.address)}</a></div>` : ""}
    ${b.phone ? `<div class="line">${ICON.phone}<a href="${esc(telHref(b.phone))}">${esc(b.phone)}</a></div>` : ""}
    ${b.email ? `<div class="line">${ICON.mail}<a href="mailto:${esc(b.email)}">${esc(b.email)}</a></div>` : ""}
    <div class="ctas">${directions ? btn("btn-primary", directions, "Get directions", "pin") : ""}${b.phone ? btn("btn-outline", telHref(b.phone), "Call now", "phone") : ""}</div>
    ${form}
  </div>
  ${hours.length ? `<div class="hours"><h3>Hours</h3><ul>${hours.map((h) => `<li><span>${esc(h.days)}</span><span>${esc(h.time)}</span></li>`).join("")}</ul></div>` : ""}
</div></div></section>`;

  const socialHtml = Object.entries(social).filter(([, u]) => u).length
    ? `<div class="social">${Object.entries(social).filter(([, u]) => u).map(([k, u]) =>
        `<a href="${esc(u)}" target="_blank" rel="noopener" aria-label="${esc(k)}">${ICON[k] || ICON.web}</a>`).join("")}</div>`
    : "";

  const barItems = [primary, secondary || (b.phone && !primary.href.startsWith("tel:") ? { href: telHref(b.phone), label: "Call", icon: "phone" } : null)].filter(Boolean);
  const actionbar = `<nav class="actionbar" aria-label="Quick actions">${barItems.map((x, i) => btn(i ? "btn-primary" : "btn-accent", x.href, x.label.replace(/^Call \(.*/, "Call"), x.icon)).join("")}</nav>`;

  const vars = {
    TITLE: esc(cfg.seo?.title || `${b.name}${b.tagline ? " | " + b.tagline : ""}`),
    DESCRIPTION: esc(cfg.seo?.description || hero.subheadline || b.tagline || ""),
    OG_IMAGE: hero.image && /^https?:/.test(hero.image) ? `<meta property="og:image" content="${esc(hero.image)}">` : "",
    FONTS_URL: `https://fonts.googleapis.com/css2?${style.fonts}&display=swap`,
    PRIMARY: esc(t.primary || "#1f3a5f"),
    ACCENT: esc(t.accent || "#ffb703"),
    ACCENT_INK: inkFor(t.accent || "#ffb703"),
    DISPLAY_FONT: style.display, BODY_FONT: style.body, RADIUS: style.radius,
    HEAD_CASE: style.headCase, HEAD_TRACK: style.headTrack, HEAD_WEIGHT: style.headWeight,
    ANNOUNCE: cfg.announcement ? `<div class="announce">${esc(cfg.announcement)}</div>` : "",
    NAME: esc(b.name || "Business Name"),
    NAV: nav,
    HEADER_CTA: btn("btn-accent", primary.href, primary.label.replace(/^Call \(.*/, "Call now"), ""),
    HERO: heroHtml, INFO: infoHtml, SERVICES: servicesHtml, BAND: bandHtml, GALLERY: galleryHtml,
    ABOUT: aboutHtml, REVIEWS: reviewsHtml, VISIT: visitHtml, SOCIAL: socialHtml, ACTIONBAR: actionbar,
    YEAR: String(new Date().getFullYear()),
    CREDIT: cfg.hideCredit ? "" : " · Website by ELIO Website Studio",
  };
  return TEMPLATE.replace(/\{\{(\w+)\}\}/g, (_, k) => (k in vars ? vars[k] : ""));
}

function build(clientDir, { quiet = false } = {}) {
  const dir = path.resolve(ROOT, clientDir);
  const cfgPath = path.join(dir, "site.config.json");
  if (!fs.existsSync(cfgPath)) {
    if (!quiet) { console.error(`No site.config.json in ${dir}`); process.exitCode = 1; }
    return;
  }
  const cfg = JSON.parse(fs.readFileSync(cfgPath, "utf8"));
  const out = path.join(ROOT, "dist", path.basename(dir));
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "index.html"), render(cfg));
  const assets = path.join(dir, "assets");
  if (fs.existsSync(assets)) fs.cpSync(assets, path.join(out, "assets"), { recursive: true });
  console.log(`Built ${path.relative(ROOT, out)}/index.html`);
}

module.exports = { render, STYLES };

if (require.main === module) {
  const arg = process.argv[2];
  if (!arg) {
    console.log("Usage: node build.js <clients/name> | --all");
    process.exit(1);
  }
  if (arg === "--all") {
    const clients = path.join(ROOT, "clients");
    for (const name of fs.readdirSync(clients)) {
      if (fs.statSync(path.join(clients, name)).isDirectory()) build(path.join("clients", name), { quiet: true });
    }
  } else {
    build(arg);
  }
}
