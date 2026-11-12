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
python markethub_server.py
```

The server will listen on port 8000 by default.

## Run the tests

```bash
python -m unittest discover -s backend/tests -v
```

## Firmware notes

The ESP32-S3 sketch is designed for an LVGL-based display and expects the Raspberry Pi backend to be reachable at `http://pi.local:8000/api/dashboard`.

## Florida Water 2.0 video hub

A public video site for the Florida Water 2.0 promotion business: a video feed with categories, search and a featured row, a watch page, a "Submit a video" form, a "Promote" page with packages and a quote form, and a staff desk for approving posts.

Videos are not downloaded or re-uploaded. Creators submit a link to their own YouTube, TikTok, Instagram or Vimeo post, staff approve it, and it plays through that platform's official embed player.

```bash
cd backend
HUB_ADMIN_TOKEN=choose-a-long-secret python hub_server.py
```

Open http://localhost:8080. The staff desk is at `/#/admin` and asks for the token above (if the variable is unset, a one-time token is printed at startup).

- `backend/hub_config.json` holds the brand name, categories and promo packages (set your prices here)
- `backend/hub_server.py` and `backend/hub_db.py` are the API and SQLite storage (`backend/hub.db`, created on first run)
- `site/` is the front end
- Settings: `HUB_PORT`, `HUB_HOST`, `HUB_DB`, `HUB_ADMIN_TOKEN`

Before going public, put it behind HTTPS (for example a reverse proxy such as Caddy or nginx).
