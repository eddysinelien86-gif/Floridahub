# ELIO Website Studio

A toolkit for building websites for local businesses and selling them.

```
ELIO-Website-Studio/
├── build.js              # turns a client's config into a finished website
├── new-client.sh         # starts a new client from the example
├── template/index.html   # the website design every client site uses
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
| Field | What it does |
|---|---|
| `business` | name, tagline, phone, email, address, `hours` list |
| `theme` | `primary` and `accent` colors, optional `font` |
| `hero` | headline, subheadline, button text (`ctaText`), optional `ctaLink` and `image` |
| `services` | list of `{ title, description, price? }` |
| `about` | paragraph about the business |
| `testimonials` | list of `{ quote, name }`. Use **real** reviews only. Leave empty to hide the section. |
| `contactFormAction` | a form endpoint URL (e.g. from Formspree or Netlify Forms). Leave empty to hide the form. |
| `seo` | page `title` and `description` for Google |
| `hideCredit` | `true` removes "Website by ELIO Website Studio" from the footer |

## Putting a site online
Each finished site is one folder in `dist/`. Free or cheap options:
- **Netlify Drop** (app.netlify.com/drop): drag the folder in and get a link in seconds. Great for demos.
- **Cloudflare Pages** or **GitHub Pages**: free hosting that supports the client's own domain.
- **Wix**: if a client wants to edit the site themselves.

Connect the client's domain in the host's settings, and HTTPS is set up automatically.

## Your dashboard
Double-click `dashboard/index.html` to open it in your browser. Nothing to install.
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
