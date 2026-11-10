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

## AI Assistant (Claude)

The `/api/ai/generate` endpoint writes captions, hashtags, review replies, and
marketing ideas using Claude. It works with or without a key:

- **With a key** it returns real, generated content (`"source": "claude"`).
- **Without a key** it returns built-in sample text so the dashboard still runs
  (`"source": "sample"`).

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
