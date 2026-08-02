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
