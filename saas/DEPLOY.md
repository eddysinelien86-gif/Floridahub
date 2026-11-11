# Deploy the MarketHub SaaS to the cloud (free, on Render)

This puts the multi-tenant app online at a real URL so companies can sign up
24/7 — no Pi required.

## Steps
1. Go to **https://render.com** → sign up (free; "Sign in with GitHub" is easiest).
2. Click **New +** → **Web Service**.
3. Connect your GitHub and pick the repo **`eddysinelien86-gif/Floridahub`**.
4. Fill in the settings:
   - **Branch:** `claude/phone-unlock-code-82dee1`
   - **Root Directory:** `saas`
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance Type:** Free
5. Under **Environment**, add:
   - `SAAS_SECRET` = any long random string (used to sign logins)
   - *(optional)* `ANTHROPIC_API_KEY` = your Claude key, for real AI content
   - *(recommended)* `DATABASE_URL` = your Neon Postgres connection string (so
     data survives redeploys — see **Persistent database** below)
   - *(for paid plans)* `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID` — see **Billing**
6. Click **Create Web Service**. Render builds and deploys — in ~2 minutes you
   get a live URL like `https://markethub-saas.onrender.com`.

Open that URL → **Sign up** → you're running your product in the cloud. 🎉
Each company that signs up gets `https://your-app.onrender.com/t/their-name`.

## Good to know
- **Free tier sleeps** after ~15 min idle and wakes on the next visit (first
  load takes ~30s). Fine for early users.
- **⚠️ Data persistence:** the free plan uses an ephemeral disk, so the SQLite
  database **resets when Render redeploys or restarts**. That's fine for
  testing, but **before real customers, switch to a database** (free Postgres on
  Neon or Render). That's the recommended next step.
- You can later point a custom domain (e.g. `app.yourbrand.com`) at the Render
  service in its Settings.

## Persistent database (free Neon Postgres)
Without this, the free SQLite file resets on every redeploy. Fix it once:
1. Go to **https://neon.tech** → sign up (free) → **Create project**.
2. Copy the **connection string** (starts with `postgresql://...`). Use the
   **pooled** one if offered.
3. In Render → your service → **Environment** → add `DATABASE_URL` = that string.
4. **Save** → Render redeploys. The app auto-creates its tables in Postgres on
   startup. From now on, signups and leads persist across restarts. ✅

## Billing — charge contractors monthly (Stripe)
LeadPilot has Stripe subscriptions built in. Turn them on when you're ready:
1. Go to **https://stripe.com** → create a free account. Stay in **Test mode**
   (toggle, top right) until you're ready to take real money.
2. **Product catalog → Add product**: name it e.g. "LeadPilot Pro", set a
   **recurring** price (e.g. $49 / month). Save, then copy the **Price ID**
   (looks like `price_1A2b...`).
3. **Developers → API keys**: copy your **Secret key** (`sk_test_...`).
4. In Render → **Environment**, add:
   - `STRIPE_SECRET_KEY` = `sk_test_...`
   - `STRIPE_PRICE_ID` = `price_...`
   - *(optional)* `PLAN_PRICE_LABEL` = `$49/mo` (what the button shows)
   - *(optional)* `APP_URL` = your live URL, e.g. `https://your-app.onrender.com`
5. Save → redeploy. The **Upgrade to Pro** button on each company's dashboard now
   opens Stripe Checkout; after they pay, they come back marked **Pro**.
6. *(optional, for reliability)* **Developers → Webhooks → Add endpoint**:
   URL `https://your-app.onrender.com/webhook`, events
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`. Copy the **Signing secret** (`whsec_...`)
   into Render as `STRIPE_WEBHOOK_SECRET`. This keeps plans in sync if someone
   cancels.

## Instant lead alerts (email)
When a lead comes in, the company owner gets an email right away. One Gmail
account sends all alerts; each one goes to that company's signup email.
1. Use a Gmail account for sending (your business Gmail is fine).
2. Turn on **2-Step Verification** on that Google account, then create an
   **App Password**: Google Account → Security → 2-Step Verification → App
   passwords → generate one for "Mail". You get a 16-character code.
3. In Render → **Environment**, add:
   - `SMTP_USER` = that Gmail address (e.g. `yourbiz@gmail.com`)
   - `SMTP_PASS` = the 16-character App Password (NOT your normal password)
4. Save → redeploy. New leads now email the company owner automatically.

If these aren't set, leads still save to the dashboard — they just don't email.

**Test card** (Test mode only): `4242 4242 4242 4242`, any future date, any CVC.
When you're ready for real payments, switch Stripe out of Test mode and swap in
your live `sk_live_...` key and live Price ID.

> 🔒 Never put these keys in the code or commit them — they only go in Render's
> Environment settings (or a local `secrets.env`, which is gitignored).
