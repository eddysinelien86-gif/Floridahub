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
