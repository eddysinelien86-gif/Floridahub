# Play the Pi's games on the phone (Pi 5 → Galaxy A53)

Goal: the **Raspberry Pi 5 runs the games**, and you **play them on the phone**
over your home WiFi, using a Bluetooth controller paired to the phone.

## Honest expectations first

- The Pi 5 is great for **retro / emulated games** (NES, SNES, Genesis, Game
  Boy/GBA, PS1, N64, PSP, Dreamcast) and lighter titles. It **cannot** run
  modern Windows PC games.
- The Pi 5 has **no hardware video encoder**, so streaming its screen to the
  phone is done in software (CPU). Expect a **smooth experience for 2D/retro**
  games at 720p, and more latency on demanding 3D. Use **5GHz WiFi or wired
  Ethernet** on the Pi for the best result.
- If streaming ever feels laggy, the fallback is to plug the Pi into a TV with
  HDMI and play there — zero latency. But this guide is for playing on the phone.

---

## Part 1 — Put games on the Pi

Use **Raspberry Pi OS (64-bit, Bookworm)** as the base (so Sunshine can host the
stream). Then add RetroPie on top:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git
git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git
cd RetroPie-Setup
sudo ./retropie_setup.sh
```

In the menu: **Basic install** → let it build the core emulators and
EmulationStation frontend. This takes a while.

- Put your game files (ROMs you legally own) in `~/RetroPie/roms/<system>/`.
- Launch the frontend with `emulationstation`.
- Configure a controller in EmulationStation when prompted (you can also just
  rely on the controller paired to the phone once streaming — see Part 3).

> Prefer a simpler route? `sudo apt install retroarch` gives you RetroArch
> alone without the full RetroPie frontend.

## Part 2 — Install Sunshine (the stream host) on the Pi

Sunshine turns the Pi into a streaming host.

1. Go to the Sunshine releases page: **https://github.com/LizardByte/Sunshine/releases**
2. Download the latest **`.deb` built for `arm64` / Debian Bookworm**.
3. Install it (adjust the filename to the one you downloaded):
   ```bash
   sudo apt install -y ./sunshine-*-arm64.deb
   ```
4. Start Sunshine, then open its web interface on the Pi's browser:
   **https://localhost:47990** — set a username/password on first launch.
   (It's a self-signed cert, so accept the browser warning.)
5. In the Sunshine web UI, under **Applications**, add RetroPie:
   - Name: `RetroPie`
   - Command: `emulationstation`  (or point it at RetroArch)

   Add a "Desktop" entry too, so you can stream the whole screen if needed.

## Part 3 — Moonlight on the phone

1. On the A53, install **Moonlight Game Streaming** from the Play Store.
2. Make sure the phone and Pi are on the **same WiFi**.
3. Open Moonlight — the Pi should appear automatically. Tap it.
4. It shows a **4-digit PIN**. Enter that PIN in the Sunshine web UI on the Pi
   (**PIN** tab). They're now paired.
5. Back in Moonlight, tap the Pi, then tap **RetroPie** to start streaming.

## Part 4 — Controller

Pair a **Bluetooth controller directly to the phone** (Settings → Bluetooth).
Moonlight sends its input to the Pi, so the controller "just works" in your
games. Moonlight also has on-screen touch controls if you have no controller.

---

## Quick troubleshooting

| Problem | Fix |
|---|---|
| Pi doesn't show in Moonlight | Same WiFi? Try adding the Pi's IP manually in Moonlight. |
| Laggy / stutter | Use 5GHz WiFi or Ethernet on the Pi; lower Moonlight's resolution to 720p and bitrate to ~10 Mbps; set HEVC in Moonlight settings. |
| Black screen on stream | In Sunshine, make sure a display/resolution is set; for headless Pi you may need a dummy HDMI plug or a forced resolution in `config.txt`. |
| Controller not detected | Pair it to the **phone**, not the Pi. |

## Where this fits with the rest of Floridahub

This is separate from the trend bot — gaming runs on the Pi, the bot runs on the
phone (see `PHONE_SETUP.md`). They don't interfere. Later, if you want the bot on
the Pi too, it can share the same Raspberry Pi OS install.
