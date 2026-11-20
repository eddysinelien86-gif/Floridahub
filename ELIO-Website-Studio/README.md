# ELIO Website Studio

A toolkit for building websites for local businesses and selling them.

```
ELIO-Website-Studio/
├── build.js              # turns a client's config into a finished website
├── new-client.sh         # starts a new client from the example
├── template/index.html   # the website design (3 looks: bold, elegant, modern)
├── clients/              # one folder per client, each with site.config.json (+ assets/)
├── dist/                 # built websites, ready to upload
├── studio-site/          # ELIO's own sales page
├── dashboard/            # your business dashboard (leads, clients, income)
└── business/             # pricing, sales script, proposal and intake templates
```

## Make a site for a new client (about 15 minutes)

You need [Node.js](https://nodejs.org) 18 or newer.

```bash
cd ELIO-Website-Studio
./new-client.sh joes-pizza                  # creates clients/joes-pizza/
# edit clients/joes-pizza/site.config.json  (name, phone, services, colors...)
node build.js clients/joes-pizza            # writes dist/joes-pizza/index.html
```

Open `dist/joes-pizza/index.html` in a browser to preview it. Put photos in `clients/joes-pizza/assets/` and reference them as `assets/photo.jpg` (for example `"hero": { "image": "assets/storefront.jpg" }`).

Rebuild every client at once with `node build.js --all`.

### Config options (`site.config.json`)
`clients/lost-in-da-souse-kitchen/site.config.json` is a complete example.

| Field | What it does |
|---|---|
| `business` | name, tagline, phone, email, address, `hours` list |
| `theme.style` | `"bold"` (restaurants, barbers, gyms), `"elegant"` (salons, spas, boutiques) or `"modern"` (trades, services) |
| `theme.primary`, `theme.accent` | brand color (dark) and button color (bright) |
| `announcement` | a line in the top bar, e.g. "Now open in Sunrise" |
| `hero` | `eyebrow`, `headline`, `subheadline`, `ctaText`/`ctaLink`, `secondaryText`/`secondaryLink`, `image` |
| `highlights` | 2–3 short selling points shown as chips |
| `rating` | `{ value, count, source }`. Real numbers only. |
| `hoursSummary` | short hours line for the info strip |
| `order` | `[{ label, url }]` online ordering or booking links |
| `services` | 3, 4 or 6 items of `{ title, description, price?, tag?, image? }` |
| `servicesNav`, `servicesEyebrow`, `servicesTitle`, `servicesIntro` | section labels (use `"Menu"` for food) |
| `band` | `{ headline, text }`: the big call-to-action strip |
| `gallery` | 3 or 5 photo URLs or `assets/...` paths |
| `about`, `aboutTitle`, `aboutImage` | the story section |
| `testimonials` | `{ quote, name }`. Real reviews only, with permission. |
| `social` | `{ instagram, facebook, tiktok }` links |
| `contactTitle`, `contactFormAction` | contact section title and optional form endpoint |
| `seo` | page `title` and `description` for Google |
| `hideCredit` | `true` removes "Website by ELIO Website Studio" |

**Photos make the biggest difference.** Put the owner's photos in `clients/<name>/assets/` and use
`"assets/photo.jpg"` for `hero.image`, `aboutImage`, `gallery` or a service's `image`.

## Putting a site online
Each finished site is one folder in `dist/`. Free or cheap options:
- **Netlify Drop** (app.netlify.com/drop): drag the folder in and get a link in seconds. Great for demos.
- **Cloudflare Pages** or **GitHub Pages**: free hosting that supports the client's own domain.
- **Wix**: if a client wants to edit the site themselves.

Connect the client's domain in the host's settings, and HTTPS is set up automatically.

## Your dashboard and demo agent
**Start it:** double-click **ELIO Studio** on your desktop (or run `./start-studio.sh`). It opens at http://localhost:4321.
To add the desktop icon the first time, run `./install-desktop-icon.sh`.

**Demo agent:** type a business into the box at the top, for example
"Lost in da Souse Kitchen, 8438 W Oakland Park Blvd, Sunrise FL", and click **Create demo**.
The agent uses Claude Code on this computer to look the business up, writes `clients/<name>/site.config.json`,
builds the site into `dist/`, and adds the business to the pipeline as **Demo ready** with an **Open demo** link.
Each demo takes a few minutes and uses some of your Claude plan. Read the agent's notes (click the business)
and check the details with the owner before you show it.

The pipeline is **Lead → Demo ready → Demo sent → Proposal → Building → Live**. When you show a demo,
move the business to **Demo sent**: the dashboard records the date.

Your data is saved in `data/studio.json`. The server only accepts connections from this computer.

You can still double-click `dashboard/index.html` directly; everything except the agent works that way,
but that copy keeps its data separately inside the browser.
- Track every business from **Lead → Demo sent → Proposal → Building → Live**
- See monthly recurring income, fees won, open pipeline and follow-ups due
- **TV mode** shows it full screen with large text, for a laptop plugged into a TV
- Your data stays in that browser. Use **Save backup** now and then, and **Load backup** to move it to another computer.

Example client configs for a plumber, a restaurant and a salon are in `clients/_example-*`.

## Running the business
See `business/`:
- `pricing-and-sales.md`: packages, who to target, the "demo first" pitch, launch checklist
- `client-intake.md`: questions to ask a new client
- `proposal-template.md`: fill in and send to close the deal
