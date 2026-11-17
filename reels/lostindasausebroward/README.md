# Lost in Da Sause Broward: 60-second Reel kit

| File | What it is |
|---|---|
| `voiceover.md` | Voiceover script with timing and delivery marks, plus a ready-to-post caption and hashtags |
| `bot_prompt.txt` | Full prompt to paste into your Raspberry Pi 5 AI video bot |
| `render_reel.py` | Renders the whole Reel with FFmpeg (effects, text animation, split screens, music ducking, cover, captions) |

## 1. Shoot these 5 clips (vertical, 5-8 s each, steady, good light)

| File name | Shot | Tip |
|---|---|---|
| `lid.mp4` | Lid coming off the chicken souse | **Most important shot.** Start tight on the lid; capture the pop sound |
| `spoon.mp4` | Spoon lifting the souse | Shoot at 60 fps if your phone allows, for smoother slow-mo |
| `wings.mp4` | Lost Wings in the box | Slow push toward the wings |
| `fries.mp4` | Toppings and Lost Sauce going onto the Steakhouse Detour fries | Keep the toppings in frame |
| `smokebox.mp4` | Overhead of the full Colossal Smoke Box | **Second most important shot.** Hold still overhead, sliders visible |

Put them in a `clips/` folder next to the script. A `logo.png` (transparent background) is optional.

## 2. Set up the Pi 5 (once)

```bash
sudo apt update && sudo apt install -y ffmpeg fonts-dejavu-core
# Optional, better-looking font: put Anton-Regular.ttf (free from Google Fonts) in ./fonts/
```

## 3. Voice and music

- **Voice:** record `voiceover.md` on your phone, or use free offline TTS on the Pi with [Piper](https://github.com/rhasspy/piper):
  `echo "<plain script>" | piper --model en_US-ryan-high.onnx --output_file vo.wav`
- **Music:** use an original or royalty-free/licensed instrumental only (copyrighted songs can get the Reel muted). Instagram's in-app music library is another option: export without `--music` and add the track in the app.

## 4. Render

```bash
python3 render_reel.py --clips clips --preview                         # quick 540x960 check
python3 render_reel.py --clips clips --music beat.mp3 --voice vo.wav --logo logo.png --pop-time 1.2
```

Outputs go to `out/`: `reel.mp4`, `cover.jpg`, `captions.srt`, `edit_list.txt`.

| Option | Use |
|---|---|
| `--pop-time` | The second the lid pops in `lid.mp4`. Lines up the flash and music drop |
| `--vo-start` | Delay before the voice starts (default 0.3 s) |
| `--address ''` | Hides the address on the end card |
| `--font` | Use a different bold font |

The Pi 5 has no hardware H.264 encoder, so the full render uses the CPU. Expect a few minutes for the final render and well under a minute for a preview.
