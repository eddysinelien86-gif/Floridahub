# Running the Floridahub bot on the Galaxy A53

This runs the trend bot **on the phone itself** using Termux (a free Android
terminal). Once it's running, you open the phone's browser to see trending
hip-hop/entertainment stories with ready-to-post captions — tap to copy, paste
straight into TikTok / Instagram / Facebook.

## 1. Install Termux

Install **Termux** from **F-Droid** (https://f-droid.org) — *not* the Play
Store version, which is outdated and broken. Also install **Termux:Boot** later
if you want it to auto-start.

## 2. Install Python and git

Open Termux and run:

```bash
pkg update -y && pkg upgrade -y
pkg install python git -y
```

## 3. Get the code

The repo is private, so clone it with a **GitHub personal access token**
(create one at github.com → Settings → Developer settings → Personal access
tokens → "Tokens (classic)", with `repo` scope):

```bash
git clone https://YOUR_TOKEN@github.com/eddysinelien86-gif/Floridahub.git
cd Floridahub
```

(Replace `YOUR_TOKEN` with the token you created.)

## 4. Start the bot

```bash
bash start.sh
```

You'll see:

```
Open this on the phone's browser:
    http://localhost:8000
```

## 5. Use it

1. Leave Termux running (it can stay in the background).
2. Open **Chrome** (or any browser) on the phone and go to **http://localhost:8000**
3. Tap **🔄 Find new trends** — the bot pulls the latest headlines and writes a caption for each.
4. Tap **📋 Copy caption** on a story, then paste it into your post.
5. Tap **Mark posted** to keep track of what you've used.

## Tips

- To keep Termux awake while streaming/posting: run `termux-wake-lock` once.
- To stop the bot: tap in Termux and press `Ctrl + C`.
- To pull code updates later: `cd Floridahub && git pull && bash start.sh`
- Trends are saved on the phone in `backend/markethub.db`, so your "posted"
  history survives restarts.

## Add your own news sources

Open `backend/trends.py` and edit the `SOURCES` list near the top — add any RSS
feed URL (artist blogs, local Florida outlets, your favorite sites). The bot
will fold them into the ranking automatically.
