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

## Outreach agent (AC restoration, roofing, contractors)

Open `http://localhost:8000/outreach` after starting the backend. The workflow:

1. **Find companies.** Pick a trade and city. The Google Places API returns operating businesses with their phone numbers and websites.
2. **Draft.** Claude (`claude-opus-5-5`) writes a personalized text and email for each lead from your pitch. If no Anthropic key is set, a template is used instead.
3. **Review and send.** You edit if needed, then click **Send text** or **Send email** for one message at a time. There is deliberately no bulk send.

Guards built in:
- Every text ends with "Reply STOP to opt out." and every email has your address and an unsubscribe line.
- STOP/UNSUBSCRIBE replies to your Telnyx number opt the contact out automatically. Opted-out contacts are never sent to.
- Sends are allowed only 9am–8pm Mon–Sat. There are daily caps, and no lead is re-contacted on the same channel within 30 days.
- **Dry-run mode is on by default.** Nothing is delivered until `OUTREACH_DRY_RUN=false`.

### Configuration (environment variables)

| Variable | Purpose |
| --- | --- |
| `GOOGLE_PLACES_API_KEY` | Lead search (Places API "New") |
| `ANTHROPIC_API_KEY` | Claude drafting |
| `TELNYX_API_KEY`, `TELNYX_FROM_NUMBER` | Sending texts (`TELNYX_MESSAGING_PROFILE_ID` optional) |
| `TELNYX_PUBLIC_KEY` | Verifies inbound webhooks (strongly recommended) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Sending email |
| `OUTREACH_SENDER_NAME`, `OUTREACH_COMPANY`, `OUTREACH_COMPANY_ADDRESS`, `OUTREACH_PITCH` | Who you are and what you offer (address is required for email) |
| `OUTREACH_TZ`, `OUTREACH_SEND_START_HOUR`, `OUTREACH_SEND_END_HOUR` | Sending window (default 9–20, America/New_York) |
| `OUTREACH_DAILY_SMS_CAP`, `OUTREACH_DAILY_EMAIL_CAP`, `OUTREACH_RECONTACT_DAYS` | Limits (50 / 100 / 30) |
| `OUTREACH_ADMIN_TOKEN` | If set, the outreach API requires it (the page prompts for it) |
| `OUTREACH_DRY_RUN` | `true` (default) logs instead of sending |

In the Telnyx portal, point your messaging profile's inbound webhook at `https://<your-host>/api/outreach/webhooks/telnyx`.

**Before turning off dry run:** register your Telnyx number for A2P 10DLC (brand plus campaign). Carriers block unregistered business texting. The campaign must accurately describe the messages you send.
