"use strict";
// Florida Water 2.0 front end. Hash routes: #/, #/v/<id>, #/submit, #/promote, #/how, #/admin
// All user-supplied text is inserted with textContent, never as HTML.

const view = document.getElementById("view");
const state = { meta: null, category: "", sort: "new", q: "", page: 1 };
const PROVIDERS = { youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram", vimeo: "Vimeo" };

function el(tag, props, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v === true) node.setAttribute(k, "");
    else if (v !== false && v != null) node.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) node.append(kid);
  return node;
}

async function api(path, options = {}) {
  const init = { headers: { ...(options.headers || {}) } };
  if (options.body) {
    init.method = "POST";
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  } else if (options.method) init.method = options.method;
  const res = await fetch(path, init);
  let data = {};
  try { data = await res.json(); } catch { /* non-JSON error */ }
  if (!res.ok) throw Object.assign(new Error(data.error || "Something went wrong. Try again."), { status: res.status });
  return data;
}

const fmtViews = (n) => (n === 1 ? "1 view" : `${new Intl.NumberFormat("en", { notation: "compact" }).format(n)} views`);
function ago(ts) {
  const s = Math.max(0, Date.now() / 1000 - ts);
  const units = [[31536000, "year"], [2592000, "month"], [86400, "day"], [3600, "hour"], [60, "minute"]];
  for (const [secs, name] of units) {
    const n = Math.floor(s / secs);
    if (n >= 1) return `${n} ${name}${n > 1 ? "s" : ""} ago`;
  }
  return "just now";
}

function card(v) {
  const thumb = el("div", { class: "thumb" });
  if (v.thumbnail) {
    const img = el("img", { src: v.thumbnail, alt: "", loading: "lazy" });
    img.addEventListener("error", () => img.remove());
    thumb.append(img);
  }
  thumb.append(el("span", { class: "play" }));
  if (v.sponsored) thumb.append(el("span", { class: "tag" }, "Sponsored"));
  thumb.append(el("span", { class: "tag src" }, PROVIDERS[v.provider] || v.provider));
  return el("a", { class: "card", href: `#/v/${v.id}` },
    thumb,
    el("div", { class: "card-body" },
      el("div", { class: "card-title" }, v.title),
      el("div", { class: "meta" }, `${v.category} · ${fmtViews(v.views)} · ${ago(v.published_at)}`)));
}

// ---- feed ---------------------------------------------------------------
async function feed() {
  const params = new URLSearchParams({ sort: state.sort, page: state.page });
  if (state.category) params.set("category", state.category);
  if (state.q) params.set("q", state.q);
  const data = await api(`/api/videos?${params}`);
  const filtered = state.category || state.q;
  const out = [];

  if (!filtered && state.page === 1) {
    out.push(el("section", { class: "hero" },
      el("h1", {}, "Florida's feed, straight from the people who filmed it."),
      el("p", {}, "Music, comedy, sports and local moments from across the state. Send us your video and we will put it in front of Florida."),
      el("div", { class: "hero-cta" },
        el("a", { class: "btn", href: "#/submit" }, "Submit a video"),
        el("a", { class: "btn btn-ghost", href: "#/promote" }, "Promote your brand"))));
    if (data.featured.length) {
      out.push(el("h2", { class: "sec-title" }, "Featured"), el("div", { class: "grid" }, data.featured.map(card)));
    }
  }

  const chip = (label, value) => el("button", {
    class: `chip${state.category === value ? " on" : ""}`, type: "button",
    onclick: () => { state.category = value; state.page = 1; render(); },
  }, label);
  const sortBtn = (label, value) => el("button", {
    class: `chip${state.sort === value ? " on" : ""}`, type: "button",
    onclick: () => { state.sort = value; state.page = 1; render(); },
  }, label);
  out.push(el("div", { class: "bar" },
    el("div", { class: "chips" }, chip("All", ""), state.meta.categories.map((c) => chip(c, c))),
    el("div", { class: "sort" }, sortBtn("Newest", "new"), sortBtn("Most viewed", "top"))));

  if (state.q) out.push(el("p", { class: "meta" }, `${data.total} result${data.total === 1 ? "" : "s"} for “${state.q}”`));

  if (!data.videos.length) {
    out.push(el("div", { class: "empty" },
      el("h2", {}, filtered ? "No videos match that yet" : "No videos posted yet"),
      el("p", {}, filtered ? "Try another category or search, or be the first to send one in." : "Be the first on the feed. Approved videos show up here."),
      el("a", { class: "btn", href: "#/submit" }, "Submit a video")));
  } else {
    out.push(el("div", { class: "grid" }, data.videos.map(card)));
    if (data.pages > 1) {
      const go = (d) => () => { state.page += d; render(); window.scrollTo(0, 0); };
      out.push(el("div", { class: "pager" },
        el("button", { class: "btn btn-ghost btn-sm", type: "button", disabled: state.page <= 1, onclick: go(-1) }, "Previous"),
        `Page ${data.page} of ${data.pages}`,
        el("button", { class: "btn btn-ghost btn-sm", type: "button", disabled: state.page >= data.pages, onclick: go(1) }, "Next")));
    }
  }
  return out;
}

// ---- watch --------------------------------------------------------------
async function watch(id) {
  let v;
  try { v = await api(`/api/videos/${id}`); } catch {
    return [el("div", { class: "empty" }, el("h2", {}, "That video is not available"),
      el("a", { class: "btn", href: "#/" }, "Back to videos"))];
  }
  api(`/api/videos/${id}/view`, { method: "POST" }).catch(() => {});
  document.title = `${v.title} · ${state.meta.brand}`;
  const more = (await api(`/api/videos?category=${encodeURIComponent(v.category)}`)).videos.filter((x) => x.id !== v.id).slice(0, 5);
  const tall = v.provider === "tiktok" || v.provider === "instagram";
  const copy = el("button", { class: "btn btn-ghost btn-sm", type: "button" }, "Copy link");
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); copy.textContent = "Link copied"; }
    catch { copy.textContent = "Copy the address bar link"; }
  });
  return [el("div", { class: "watch" },
    el("article", {},
      el("div", { class: `player${tall ? " tall" : ""}` },
        el("iframe", { src: v.embed_url, title: v.title, allowfullscreen: true, loading: "lazy",
          allow: "accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen",
          referrerpolicy: "strict-origin-when-cross-origin" })),
      el("h1", {}, v.title),
      el("p", { class: "meta" }, `${v.category} · ${fmtViews(v.views + 1)} · ${ago(v.published_at)}${v.submitter_name ? ` · sent in by ${v.submitter_name}` : ""}${v.sponsored ? " · Sponsored" : ""}`),
      el("div", { class: "actions" }, copy,
        el("a", { class: "btn btn-ghost btn-sm", href: v.source_url, target: "_blank", rel: "noopener noreferrer" }, `Watch on ${PROVIDERS[v.provider] || "the original site"}`)),
      v.description ? el("p", { class: "desc" }, v.description) : null),
    el("aside", { class: "side" },
      el("h2", { class: "sec-title" }, `More ${v.category}`),
      more.length ? el("div", { class: "grid" }, more.map(card)) : el("p", { class: "meta" }, "Nothing else in this category yet.")))];
}

// ---- forms --------------------------------------------------------------
function bindForm(form, path, toBody, successText) {
  const msg = el("p", { class: "msg", role: "status", hidden: true });
  const btn = form.querySelector("button[type=submit]");
  form.append(msg);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    btn.disabled = true;
    msg.hidden = true;
    try {
      await api(path, { body: toBody(new FormData(form)) });
      form.reset();
      msg.className = "msg ok";
      msg.textContent = successText;
    } catch (err) {
      msg.className = "msg err";
      msg.textContent = err.message;
    }
    msg.hidden = false;
    btn.disabled = false;
  });
  return form;
}

const field = (label, control, hint) => el("label", {}, label, control, hint ? el("span", { class: "hint" }, hint) : null);

function submitPage() {
  const form = el("form", { class: "form panel" },
    field("Video link", el("input", { name: "url", type: "url", required: true, maxlength: 300, placeholder: "https://www.youtube.com/watch?v=..." }),
      "YouTube, TikTok, Instagram or Vimeo. Post it on your own account first, then paste the link."),
    field("Title", el("input", { name: "title", required: true, minlength: 3, maxlength: 120 })),
    field("Category", el("select", { name: "category", required: true }, state.meta.categories.map((c) => el("option", {}, c)))),
    field("Description (optional)", el("textarea", { name: "description", maxlength: 1000 })),
    field("Your name or handle (shown with the video, optional)", el("input", { name: "submitter_name", maxlength: 60 })),
    field("Email or social handle", el("input", { name: "contact", required: true, maxlength: 120 }), "Only our team sees this."),
    el("label", { class: "check" }, el("input", { type: "checkbox", name: "rights", required: true }),
      el("span", {}, "This is my video, or I have the owner's permission to share it here.")),
    el("button", { class: "btn", type: "submit" }, "Send for review"));
  bindForm(form, "/api/submissions", (f) => ({
    url: f.get("url"), title: f.get("title"), category: f.get("category"), description: f.get("description"),
    submitter_name: f.get("submitter_name"), contact: f.get("contact"), rights_confirmed: f.get("rights") === "on",
  }), "Got it. Our team reviews every video before it goes live.");
  return [el("div", { class: "page" },
    el("h1", {}, "Submit a video"),
    el("p", { class: "lead" }, "Filmed something Florida needs to see? Send the link. If it is approved it goes on the feed, with credit and views going back to your post."),
    form)];
}

function promotePage() {
  const plans = state.meta.packages.map((p) => el("div", { class: "panel plan" },
    el("h3", {}, p.name), el("div", { class: "price" }, p.price), el("p", {}, p.summary),
    el("ul", {}, p.features.map((f) => el("li", {}, f)))));
  const form = el("form", { class: "form panel" },
    field("Your name", el("input", { name: "name", required: true, maxlength: 80 })),
    field("Business, artist or brand", el("input", { name: "business", maxlength: 120 })),
    field("Email or phone", el("input", { name: "contact", required: true, maxlength: 120 })),
    field("Package", el("select", { name: "package" }, el("option", { value: "" }, "Not sure yet"),
      state.meta.packages.map((p) => el("option", { value: p.id }, p.name)))),
    field("What do you want to promote?", el("textarea", { name: "message", maxlength: 2000 })),
    el("button", { class: "btn", type: "submit" }, "Request a quote"));
  bindForm(form, "/api/inquiries", (f) => Object.fromEntries(f), "Thanks. We will reach out with a quote.");
  return [el("div", { class: "page wide" },
    el("h1", {}, "Promote with Florida Water 2.0"),
    el("p", { class: "lead" }, "Put your music, business or event in front of our audience. Sponsored posts are always labeled."),
    el("div", { class: "plans" }, plans),
    el("div", { class: "page" }, el("h2", { class: "sec-title" }, "Request a quote"), form))];
}

function howPage() {
  const step = (title, text) => el("li", {}, el("div", {}, el("b", {}, title), el("span", {}, text)));
  return [el("div", { class: "page prose" },
    el("h1", {}, "How it works"),
    el("p", { class: "lead" }, "Every video here was sent in by its creator or shared with permission, and plays from the original post."),
    el("ol", { class: "steps" },
      step("You post it", "Upload the video to your own YouTube, TikTok, Instagram or Vimeo account."),
      step("You send the link", "Paste the link in the submit form and confirm you have the right to share it."),
      step("We review it", "Our team checks every submission before it goes live."),
      step("It hits the feed", "The video plays through the original platform's player, so the views and followers stay with you.")),
    el("h2", {}, "Content policy"),
    el("p", {}, "We do not download, re-upload or edit other people's videos. We do not post content showing minors in harm, sexual content, or anything shared without the consent of the people who own it."),
    el("h2", {}, "Takedowns and copyright"),
    el("p", {}, "If a video on this site is yours and you want it removed, or you believe it infringes your copyright, send us the video link through the ",
      el("a", { href: "#/promote" }, "contact form"), ". We remove reported videos promptly while we review."))];
}

// ---- admin --------------------------------------------------------------
let adminTab = "pending";
async function adminPage() {
  const token = sessionStorage.getItem("hubAdmin") || "";
  const headers = { "X-Admin-Token": token };
  const login = (error) => {
    const form = el("form", { class: "form panel" },
      field("Staff token", el("input", { name: "token", type: "password", required: true, autocomplete: "current-password" })),
      el("button", { class: "btn", type: "submit" }, "Sign in"),
      error ? el("p", { class: "msg err" }, error) : null);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      sessionStorage.setItem("hubAdmin", new FormData(form).get("token"));
      render();
    });
    return [el("div", { class: "page" }, el("h1", {}, "Staff sign in"), form)];
  };
  if (!token) return login();

  let rows;
  try {
    rows = adminTab === "inquiries"
      ? (await api("/api/admin/inquiries", { headers })).inquiries
      : (await api(`/api/admin/videos?status=${adminTab}`, { headers })).videos;
  } catch (err) {
    if (err.status === 401) { sessionStorage.removeItem("hubAdmin"); return login("That token was not accepted."); }
    throw err;
  }

  const act = (id, action) => async () => {
    if (action === "delete" && !confirm("Delete this video permanently?")) return;
    await api(`/api/admin/videos/${id}`, { headers, body: { action } });
    render();
  };
  const b = (label, id, action, primary) => el("button", { class: `btn btn-sm${primary ? "" : " btn-ghost"}`, type: "button", onclick: act(id, action) }, label);
  const tab = (label, value) => el("button", { class: `chip${adminTab === value ? " on" : ""}`, type: "button", onclick: () => { adminTab = value; render(); } }, label);

  const list = rows.map((r) => adminTab === "inquiries"
    ? el("div", { class: "panel row" },
        el("h3", {}, `${r.name}${r.business ? ` · ${r.business}` : ""}`),
        el("p", { class: "meta" }, `${r.contact} · ${r.package || "no package chosen"} · ${ago(r.created_at)}`),
        r.message ? el("p", { class: "desc" }, r.message) : null)
    : el("div", { class: "panel row" },
        el("h3", {}, r.title),
        el("p", { class: "meta" }, `${r.category} · ${PROVIDERS[r.provider]} · from ${r.submitter_name || "anonymous"} (${r.contact}) · ${ago(r.created_at)}`),
        el("p", { class: "meta" }, el("a", { href: r.source_url, target: "_blank", rel: "noopener noreferrer" }, r.source_url)),
        r.description ? el("p", { class: "desc" }, r.description) : null,
        el("div", { class: "actions" },
          r.status !== "published" ? b("Approve and post", r.id, "approve", true) : null,
          r.status === "published" ? b(r.featured ? "Remove from featured" : "Feature", r.id, r.featured ? "unfeature" : "feature", !r.featured) : null,
          b(r.sponsored ? "Remove sponsored label" : "Mark sponsored", r.id, r.sponsored ? "unsponsor" : "sponsor"),
          r.status !== "rejected" ? b(r.status === "published" ? "Take down" : "Reject", r.id, "reject") : null,
          b("Delete", r.id, "delete"))));

  return [el("div", { class: "page wide" },
    el("h1", {}, "Staff desk"),
    el("div", { class: "tabs" }, tab("Review queue", "pending"), tab("Live", "published"), tab("Rejected", "rejected"), tab("Promo requests", "inquiries"),
      el("button", { class: "chip", type: "button", onclick: () => { sessionStorage.removeItem("hubAdmin"); render(); } }, "Sign out")),
    list.length ? el("div", { class: "rows" }, list) : el("div", { class: "empty" }, el("h2", {}, "Nothing here right now")))];
}

// ---- router -------------------------------------------------------------
let renderSeq = 0;
async function render() {
  const seq = ++renderSeq;
  const route = location.hash.replace(/^#\/?/, "");
  const [name, arg] = route.split("/");
  const key = name === "v" ? "feed" : name || "feed";
  document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("on", a.dataset.nav === key));
  let nodes;
  try {
    if (!state.meta) {
      state.meta = await api("/api/meta");
    }
    document.title = state.meta.brand;
    if (name === "v" && /^\d+$/.test(arg || "")) nodes = await watch(arg);
    else if (name === "submit") nodes = submitPage();
    else if (name === "promote") nodes = promotePage();
    else if (name === "how") nodes = howPage();
    else if (name === "admin") nodes = await adminPage();
    else nodes = await feed();
  } catch (err) {
    nodes = [el("div", { class: "empty" }, el("h2", {}, "We could not load this page"), el("p", {}, err.message),
      el("button", { class: "btn", type: "button", onclick: render }, "Try again"))];
  }
  if (seq === renderSeq) view.replaceChildren(...nodes);
}

document.getElementById("search").addEventListener("submit", (e) => {
  e.preventDefault();
  state.q = document.getElementById("q").value.trim();
  state.page = 1;
  if (location.hash.replace(/^#\/?/, "")) location.hash = "#/"; else render();
});
window.addEventListener("hashchange", () => { window.scrollTo(0, 0); render(); });
render();
