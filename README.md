# MarketHub

MarketHub is a touchscreen-first marketing dashboard concept for an ESP32-S3 device with a Raspberry Pi backend. The project includes:

- A REST API backend written in Python with SQLite storage
- An Arduino/ESP32-S3 firmware sketch for LVGL-based touchscreen rendering
- A browser preview for rapid visual iteration

## Project structure

- `backend/` contains the Python API and SQLite-backed data layer
- `firmware/` contains the ESP32-S3 sketch and PlatformIO configuration
- `web/` contains a desktop preview of the dashboard experience

## Run the backend

```bash
cd backend
pip install -r requirements.txt
python markethub_server.py
```

The server will listen on port 8000 by default.

## Update the Pi from GitHub

After new code is pushed to GitHub, run this on the Pi to pull it and restart
the dashboard (settings in `backend/secrets.env` and saved data are kept):

```bash
cd ~/Floridahub && ./update.sh
```

## Start at boot

```bash
./install-autostart.sh          # backend + public tunnel only (keeps the lead form online)
./install-autostart.sh screen   # also open the dashboard full-screen on the Pi
./install-autostart.sh off      # stop starting anything at boot
```

## Saved data

Leads, reviews and drafts are kept across restarts. The tiles are counted from
what is really saved; sources that are not connected yet show "—".

## AI Assistant (Claude)

The `/api/ai/generate` endpoint writes captions, hashtags, review replies, and
marketing ideas. It picks the first option that is available:

- **With a key** it uses Claude (`"source": "claude"`).
- **Without a key**, or if the Claude call fails, it uses a local
  [Ollama](https://ollama.com) model running on the Pi (`"source": "ollama"`).
  This is free and works offline, but takes several seconds per answer.
- **With neither** it returns built-in sample text so the dashboard still runs
  (`"source": "sample"`).

Local model setup on the Pi:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b
# optional:
export MARKETHUB_OLLAMA_MODEL="llama3.2:3b"        # or "off" to disable
export OLLAMA_HOST="http://127.0.0.1:11434"       # another machine's address also works
```

Enable real AI by setting your key from [console.anthropic.com](https://console.anthropic.com):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# optional:
export MARKETHUB_MODEL="claude-haiku-5-5"   # cheaper for an always-on Pi (default: claude-opus-5-5)
export MARKETHUB_BRAND="Your Business Name"  # flavors the generated content
python markethub_server.py
```

Try it:

```bash
curl -X POST http://localhost:8000/api/ai/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"write a caption for my phone repair launch"}'
```

## Run the tests

```bash
python -m unittest discover -s backend/tests -v
```

## Firmware notes

The ESP32-S3 sketch is designed for an LVGL-based display and expects the Raspberry Pi backend to be reachable at `http://pi.local:8000/api/dashboard`.
