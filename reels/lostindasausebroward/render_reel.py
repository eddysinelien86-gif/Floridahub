#!/usr/bin/env python3
"""Render the 60-second Lost in Da Sause Instagram Reel with FFmpeg.

Built for a Raspberry Pi 5 (Raspberry Pi OS Bookworm, FFmpeg 5.1+), works on any Linux/macOS box.

    sudo apt install ffmpeg fonts-dejavu-core
    python3 render_reel.py --clips ./clips --preview          # 540x960 timing check
    python3 render_reel.py --clips ./clips --music beat.mp3 --voice vo.wav --logo logo.png

Put these clips (any common video extension) in --clips, filmed vertical, 5-8 s each:
    lid.*       lid coming off the chicken souse (the pop)
    spoon.*     spoon lifting souse close-up
    wings.*     Lost Wings in the box
    fries.*     toppings going onto the Steakhouse Detour fries
    smokebox.*  overhead of the full Colossal Smoke Box

Outputs (in --out): reel.mp4 (or reel_preview.mp4), cover.jpg, captions.srt, edit_list.txt
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HANDLE = "@lostindasausebroward"
BRAND = "LOST IN DA SAUSE"
FPS = 30
CREAM = "0xFFF1D6"
AMBER = "0xFFB000"
INK = "0x1A1208"
CLIP_NAMES = ["lid", "spoon", "wings", "fries", "smokebox"]
VIDEO_EXTS = [".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"]
FONT_CANDIDATES = [
    "fonts/Anton-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

# ---------------------------------------------------------------------------
# The edit. Times are seconds inside each segment. Segments play back to back.
# ---------------------------------------------------------------------------
def T(text, t0, t1, style, y=0.5, x=None):
    return dict(text=text, t0=t0, t1=t1, style=style, y=y, x=x)


def build_plan(pop_time, address):
    end_lines = [
        T(HANDLE, 0.9, 7.2, "sticker", y=0.60),
        T("SUNRISE, FL", 1.3, 7.2, "big", y=0.68),
        T("FOLLOW FOR THE NEXT CLOSE-UP", 2.0, 7.2, "small", y=0.80),
    ]
    if address:
        end_lines.append(T(address, 1.6, 7.2, "small", y=0.745))
    return [
        dict(name="hook", kind="single", clip="lid", ss=0.0, dur=4.0, speed=1.0,
             zoom=(1.0, 1.18, 0.35, pop_time), flash_at=[pop_time], cut_flash=False,
             texts=[T("BROWARD,", pop_time + 0.1, 3.9, "hook", y=0.30),
                    T("LOOK AT THIS", pop_time + 0.35, 3.9, "hook", y=0.37)]),
        dict(name="souse_spoon", kind="single", clip="spoon", ss=0.0, dur=7.0,
             ramp=(0.8, 2.0, 0.75), zoom=(1.0, 1.12, 6.5, 0.0),
             texts=[T("CHICKEN SOUSE", 0.6, 6.8, "label", y=0.62),
                    T(BRAND, 2.5, 6.8, "small", y=0.69, x="left")]),
        dict(name="souse_hold", kind="single", clip="lid", ss=2.0, dur=6.0, speed=0.6,
             zoom=(1.25, 1.10, 5.5, 0.0),
             texts=[T("LOOK AT THAT SPOON", 0.3, 5.8, "big", y=0.30)]),
        dict(name="wings", kind="single", clip="wings", ss=0.0, dur=6.0, speed=0.85,
             zoom=(1.15, 1.0, 0.5, 0.0),
             texts=[T("LOST WINGS", 0.2, 5.8, "label", y=0.62)]),
        dict(name="fries", kind="single", clip="fries", ss=0.0, dur=7.0, speed=0.8,
             zoom=(1.0, 1.10, 6.8, 0.0),
             texts=[T("STEAKHOUSE DETOUR", 0.1, 6.9, "label", y=0.24),
                    T("CHOPPED STEAK", 0.8, 6.9, "chip", y=0.55),
                    T("PEPPERS + ONIONS", 1.9, 6.9, "chip", y=0.605),
                    T("MUSHROOMS", 3.0, 6.9, "chip", y=0.66),
                    T("CHEESE", 4.0, 6.9, "chip", y=0.715),
                    T("LOST SAUCE", 5.0, 6.9, "sticker", y=0.78, x="left")]),
        dict(name="smokebox_reveal", kind="single", clip="smokebox", ss=0.0, dur=4.0, speed=1.0,
             zoom=(1.3, 1.0, 0.45, 0.0), flash_at=[0.0],
             texts=[T("COLOSSAL", 0.4, 3.9, "hook", y=0.30),
                    T("SMOKE BOX", 0.6, 3.9, "hook", y=0.37)]),
        dict(name="smokebox_split", kind="split3", dur=6.0,
             panels=[("wings", 1.0), ("smokebox", 1.5), ("fries", 2.0)],
             texts=[T("20\nWINGS", 0.5, 5.9, "panel", y=0.72, x=0),
                    T("6\nSLIDERS", 1.4, 5.9, "panel", y=0.72, x=1),
                    T("LOADED\nFRIES", 2.3, 5.9, "panel", y=0.72, x=2)]),
        dict(name="last_slider", kind="single", clip="smokebox", ss=1.0, dur=5.0, speed=0.7,
             zoom=(1.0, 1.35, 4.8, 0.0),
             texts=[T("WHO TOOK THE", 1.6, 4.9, "big", y=0.30),
                    T("LAST SLIDER?", 1.8, 4.9, "hook", y=0.36)]),
        dict(name="versus", kind="split2", dur=7.0,
             panels=[("spoon", 1.0), ("smokebox", 0.5)],
             texts=[T("TEAM\nSOUSE", 0.6, 6.9, "panel2", y=0.70, x=0),
                    T("TEAM\nSMOKE BOX", 0.9, 6.9, "panel2", y=0.70, x=1),
                    T("VS", 0.4, 6.9, "sticker", y=0.47),
                    T("WHICH ONE SHOULD WE", 1.8, 6.9, "big", y=0.20),
                    T("FEATURE NEXT?", 2.0, 6.9, "hook", y=0.255)]),
        dict(name="endcard", kind="endcard", clip="lid", ss=1.5, dur=7.2, texts=end_lines),
        # Last 0.8 s matches the very first frame so the Reel loops cleanly.
        dict(name="loop", kind="single", clip="lid", ss=0.0, dur=0.8, speed=1.0,
             zoom=(1.0, 1.0, 1.0, 0.0), cut_flash=False, texts=[]),
    ]


# Voiceover lines with the reel time they should land on (used for captions.srt).
VO = [
    (0.3, 3.9, "Broward. You know that friend who swears they're not hungry..."),
    (4.0, 7.4, "...then starts reaching for your plate? Send them this."),
    (7.5, 10.9, "This is Lost in Da Sause, in Sunrise."),
    (11.0, 16.8, "First up, the chicken souse. Take a second... look at what's in that spoon."),
    (17.0, 22.8, "Then you got the Lost Wings."),
    (23.0, 29.8, "And the Steakhouse Detour fries. Chopped steak, peppers, onions, mushrooms, cheese, and Lost Sauce on top."),
    (30.0, 33.8, "When the whole crew pulls up? Colossal Smoke Box."),
    (34.0, 39.8, "Twenty wings. Six burger sliders. Loaded fries."),
    (40.0, 44.8, "Good luck finding out who took that last slider."),
    (45.2, 51.8, "Now I gotta know... you taking the chicken souse, or splitting the Smoke Box? Drop your pick below."),
    (52.0, 58.5, "Follow @lostindasausebroward, and let's see which one gets the next close-up."),
]


# ---------------------------------------------------------------------------
# Filter helpers
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, W, H, font, tmp):
        self.W, self.H, self.font, self.tmp = W, H, font, tmp
        self.n = 0

    def textfile(self, text):
        self.n += 1
        p = self.tmp / f"t{self.n}.txt"
        p.write_text(text, encoding="utf-8")
        return str(p)


def q(s):
    """Quote a value for the filtergraph (paths/expressions)."""
    return "'" + str(s).replace("\\", "/").replace("'", r"\'") + "'"


def fade_alpha(t0, t1, f=0.18):
    return (f"if(lt(t,{t0}),0,if(lt(t,{t0 + f}),(t-{t0})/{f},"
            f"if(lt(t,{t1 - f}),1,max(({t1}-t)/{f},0))))")


def ease_out(t0, d):
    """1 -> 0 cubic ease-out starting at t0 over d seconds."""
    return f"pow(max(0,min(1,1-(t-{t0})/{d})),3)"


def drawtext(c, item, panels=1):
    lines = item["text"].split("\n")
    if len(lines) > 1:  # one drawtext per line so each line centers on its own (FFmpeg 5.1 safe)
        size = dict(hook=0.115, big=0.068, panel=0.075, panel2=0.060).get(item["style"], 0.06)
        step = size * c.W * 1.15
        mid = (len(lines) - 1) / 2
        return ",".join(drawtext(c, dict(item, text=ln, y=item["y"] + (i - mid) * step / c.H), panels)
                        for i, ln in enumerate(lines))
    W, H = c.W, c.H
    t0, t1, style = item["t0"], item["t1"], item["style"]
    base = dict(hook=0.115, big=0.068, label=0.078, chip=0.052, sticker=0.058,
                small=0.040, panel=0.075, panel2=0.060)[style] * W
    # Auto-fit: shrink long lines so they stay inside the safe area / their panel.
    max_w = (W / panels) * 0.86 if style in ("panel", "panel2") else W * 0.80
    base = min(base, max_w / (max(len(item["text"]), 1) * 0.66))
    border = max(2, int(W * 0.006))
    opts = dict(fontfile=q(c.font), textfile=q(c.textfile(item["text"])), expansion="none",
                alpha=q(fade_alpha(t0, t1)),
                enable=q(f"between(t,{t0},{t1})"))
    y = f"{H * item['y']:.0f}-text_h/2"
    if style in ("hook", "big", "panel", "panel2"):
        # Pop: overshoot the size then settle.
        fs = f"{base:.1f}*(1+0.35*{ease_out(t0, 0.2)})"
        opts.update(fontcolor=CREAM if style != "big" else AMBER, borderw=str(border),
                    bordercolor=INK, shadowx=str(border), shadowy=str(border),
                    shadowcolor=INK + "@0.6")
        if style in ("panel", "panel2"):
            pw = W / panels
            x = f"{pw * item['x'] + pw / 2:.0f}-text_w/2"
        else:
            x = "(w-text_w)/2"
    elif style in ("label", "sticker"):
        fs = f"{base:.1f}"
        opts.update(fontcolor=INK, box="1", boxcolor=AMBER + "@0.95", boxborderw=str(int(W * 0.018)))
        if item.get("x") == "left" or style == "label":
            x = f"{W * 0.08:.0f}-{W * 0.9:.0f}*{ease_out(t0, 0.28)}"   # slide in from the left
        else:
            fs = f"{base:.1f}*(1+0.4*{ease_out(t0, 0.2)})"
            x = "(w-text_w)/2"
    elif style == "chip":
        fs = f"{base:.1f}"
        opts.update(fontcolor=CREAM, box="1", boxcolor=INK + "@0.72", boxborderw=str(int(W * 0.014)))
        x = f"{W * 0.08:.0f}-{W * 0.9:.0f}*{ease_out(t0, 0.25)}"
    else:  # small
        fs = f"{base:.1f}"
        opts.update(fontcolor=CREAM, borderw=str(max(1, border // 2)), bordercolor=INK)
        x = f"{W * 0.08:.0f}" if item.get("x") == "left" else "(w-text_w)/2"
    opts.update(fontsize=q(fs), x=q(x), y=q(y))
    return "drawtext=" + ":".join(f"{k}={v}" for k, v in opts.items())


GRADE = ("eq=contrast=1.07:saturation=1.10:gamma=0.98,"
         "colorbalance=rs=0.035:gs=0.01:bs=-0.045:rh=0.05:gh=0.015:bh=-0.04,"
         "vignette=angle=PI/5")
GRAIN = "noise=alls=4:allf=t"


def flash(t, strength=0.6, d=0.08):
    return f"drawbox=x=0:y=0:w=iw:h=ih:color=white@{strength}:t=fill:enable={q(f'between(t,{t},{t + d})')}"


def retime(seg):
    if "ramp" in seg:  # fast for the first `a` source seconds, then slow-mo
        a, fast, slow = seg["ramp"]
        return f"setpts=PTS-STARTPTS,setpts={q(f'(if(lt(T,{a}),T/{fast},{a}/{fast}+(T-{a})/{slow}))/TB')}"
    return f"setpts=(PTS-STARTPTS)/{seg.get('speed', 1.0)}"


def fit(w, h):
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"


def src_needed(seg):
    if "ramp" in seg:
        a, fast, slow = seg["ramp"]
        return a + (seg["dur"] - a / fast) * slow + 1
    return seg["dur"] * seg.get("speed", 1.0) + 1


def single_graph(c, seg):
    W, H = c.W, c.H
    W2, H2 = int(W * 1.2) // 2 * 2, int(H * 1.2) // 2 * 2
    z0, z1, zd, zs = seg["zoom"]
    p = f"max(0,min(1,(on/{FPS}-{zs})/{zd}))"
    z = f"{z0}+({z1}-{z0})*({p}*{p}*(3-2*{p}))"
    parts = [retime(seg), f"fps={FPS}", fit(W2, H2),
             f"zoompan=z={q(z)}:x={q('iw/2-(iw/zoom/2)')}:y={q('ih/2-(ih/zoom/2)')}:d=1:s={W}x{H}:fps={FPS}",
             GRADE, GRAIN]
    if seg.get("cut_flash", True):
        parts.append(flash(0, 0.45, 0.07))
    parts += [flash(t) for t in seg.get("flash_at", [])]
    parts += [drawtext(c, it) for it in seg["texts"]]
    parts.append("format=yuv420p")
    return "[0:v]" + ",".join(parts) + "[v]"


def split_graph(c, seg, n):
    W, H, d = c.W, c.H, seg["dur"]
    pw = W // n
    g = [f"color=c=black:s={W}x{H}:r={FPS}:d={d}[base]"]
    last = "base"
    for i, _ in enumerate(seg["panels"]):
        g.append(f"[{i}:v]setpts=(PTS-STARTPTS)/0.8,fps={FPS},{fit(pw, H)},{GRADE}[p{i}]")
        t = 0.12 + 0.18 * i
        if n == 3:  # panels slide up one after another, on the beat
            pos = f"x={pw * i}:y={q(f'if(lt(t,{t}),H,H*{ease_out(t, 0.3)})')}"
        else:       # left panel from the left, right from the right
            sign = -1 if i == 0 else 1
            pos = f"x={q(f'{pw * i}+{sign}*{pw}*{ease_out(t, 0.35)}')}:y=0"
        g.append(f"[{last}][p{i}]overlay={pos}:eval=frame:shortest=1[o{i}]")
        last = f"o{i}"
    lw = max(4, W // 180)
    divs = ",".join(f"drawbox=x={pw * k - lw // 2}:y=0:w={lw}:h=ih:color={AMBER}:t=fill:enable={q('gte(t,0.6)')}"
                    for k in range(1, n))
    texts = ",".join(drawtext(c, it, panels=n) for it in seg["texts"])
    g.append(f"[{last}]{divs},{GRAIN},{flash(0, 0.45, 0.07)},{texts},format=yuv420p[v]")
    return ";".join(g)


def endcard_graph(c, seg, has_logo):
    W, H = c.W, c.H
    bg = (f"[0:v]setpts=(PTS-STARTPTS)/0.5,fps={FPS},{fit(W, H)},boxblur=20:2,"
          f"eq=brightness=-0.22:saturation=1.2,vignette=angle=PI/4")
    texts = ",".join(drawtext(c, it) for it in seg["texts"])
    if has_logo:
        lw = int(W * 0.56)
        y = f"{H * 0.33:.0f}-h/2+{H * 0.04:.0f}*{ease_out(0.15, 0.5)}"
        return (f"{bg}[bg];[1:v]scale={lw}:-1,format=rgba,fade=in:st=0.15:d=0.45:alpha=1[logo];"
                f"[bg][logo]overlay=x=(W-w)/2:y={q(y)}:eval=frame:shortest=1,{flash(0, 0.45, 0.07)},"
                f"{texts},format=yuv420p[v]")
    title = T(BRAND, 0.2, seg["dur"], "hook", y=0.36)
    return f"{bg},{flash(0, 0.45, 0.07)},{drawtext(c, title)},{texts},format=yuv420p[v]"


# ---------------------------------------------------------------------------
def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        sys.exit(f"ffmpeg failed: {' '.join(cmd[:6])} ...")


def find_clip(clips_dir, name):
    for ext in VIDEO_EXTS:
        for p in (clips_dir / f"{name}{ext}", clips_dir / f"{name}{ext.upper()}"):
            if p.exists():
                return p
    return None


def looped_input(path, ss, need):
    return ["-stream_loop", "-1", "-ss", f"{ss}", "-t", f"{need:.2f}", "-i", str(path)]


def render_segment(c, seg, clips, logo, out, preset):
    inputs = []
    if seg["kind"] == "single":
        inputs = looped_input(clips[seg["clip"]], seg["ss"], src_needed(seg))
        graph = single_graph(c, seg)
    elif seg["kind"] in ("split3", "split2"):
        for name, ss in seg["panels"]:
            inputs += looped_input(clips[name], ss, seg["dur"] * 0.8 + 1)
        graph = split_graph(c, seg, 3 if seg["kind"] == "split3" else 2)
    else:
        inputs = looped_input(clips[seg["clip"]], seg["ss"], seg["dur"] * 0.5 + 1)
        if logo:
            inputs += ["-loop", "1", "-i", str(logo)]
        graph = endcard_graph(c, seg, bool(logo))
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
         "-filter_complex", graph, "-map", "[v]", "-t", f"{seg['dur']}", "-an",
         "-c:v", "libx264", "-preset", preset, "-crf", "18", "-r", str(FPS),
         "-pix_fmt", "yuv420p", "-video_track_timescale", "15360", str(out)])


def audio_args(music, voice, total, vo_start, pop_time):
    ins, g = [], []
    idx = 1
    if music:
        ins += ["-stream_loop", "-1", "-i", str(music)]
        # Music drops almost silent until the lid pop, then the beat hits.
        g.append(f"[{idx}:a]atrim=0:{total},asetpts=PTS-STARTPTS,"
                 f"volume={q(f'if(lt(t,{pop_time}),0.12,0.9)')}:eval=frame,"
                 f"afade=t=out:st={total - 2}:d=2[m]")
        idx += 1
    if voice:
        ms = int(vo_start * 1000)
        ins += ["-i", str(voice)]
        g.append(f"[{idx}:a]adelay={ms}|{ms},apad,atrim=0:{total},loudnorm=I=-16:TP=-1.5,asplit=2[vo][sc]")
    if music and voice:
        g.append("[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[duck]")
        g.append("[duck][vo]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    elif music:
        g.append("[m]anull[a]")
    elif voice:
        g.append("[sc]anullsink;[vo]anull[a]")
    else:
        ins += ["-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=48000:cl=stereo"]
        g.append(f"[{idx}:a]anull[a]")
    return ins, ";".join(g)


def srt_time(s):
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--music", type=Path, help="licensed/original instrumental")
    ap.add_argument("--voice", type=Path, help="recorded or TTS voiceover (wav/mp3)")
    ap.add_argument("--vo-start", type=float, default=0.3, help="seconds before the voice starts")
    ap.add_argument("--logo", type=Path, help="PNG logo, ideally transparent")
    ap.add_argument("--font", type=Path, help="bold display font (.ttf/.otf), e.g. Anton")
    ap.add_argument("--pop-time", type=float, default=1.0, help="when the lid pops in lid clip (s)")
    ap.add_argument("--address", default="8438 W OAKLAND PARK BLVD",
                    help="end-card address line; pass '' to hide")
    ap.add_argument("--preview", action="store_true", help="fast 540x960 draft")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. On the Pi: sudo apt install ffmpeg")
    font = a.font or next((Path(f) for f in FONT_CANDIDATES if Path(f).exists()), None)
    if not font or not font.exists():
        sys.exit("No bold font found. Pass --font /path/to/Font.ttf")
    clips = {n: find_clip(a.clips, n) for n in CLIP_NAMES}
    missing = [n for n, p in clips.items() if p is None]
    if missing:
        sys.exit(f"Missing clips in {a.clips}: {', '.join(missing)} (see the shot list in README.md)")

    W, H = (540, 960) if a.preview else (1080, 1920)
    preset = "ultrafast" if a.preview else "medium"
    plan = build_plan(a.pop_time, a.address.upper())
    a.out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        c = Ctx(W, H, font.resolve(), tmp)
        listing, t, edit = [], 0.0, []
        for i, seg in enumerate(plan):
            seg_out = tmp / f"seg{i:02}.mp4"
            print(f"[{i + 1}/{len(plan)}] {seg['name']:<16} {t:5.1f}-{t + seg['dur']:5.1f}s", flush=True)
            render_segment(c, seg, clips, a.logo, seg_out, preset)
            listing.append(f"file '{seg_out}'")
            src = seg.get("clip") or " | ".join(p for p, _ in seg.get("panels", []))
            words = " / ".join(x["text"].replace("\n", " ") for x in seg["texts"])
            edit.append(f"{t:05.1f}-{t + seg['dur']:05.1f}s  {seg['name']:<16} clips: {src:<26} text: {words}")
            t += seg["dur"]
        (tmp / "list.txt").write_text("\n".join(listing))
        silent = tmp / "video.mp4"
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(tmp / "list.txt"), "-c", "copy", str(silent)])

        name = "reel_preview.mp4" if a.preview else "reel.mp4"
        ains, agraph = audio_args(a.music, a.voice, round(t, 2), a.vo_start, a.pop_time)
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(silent), *ains,
             "-filter_complex", agraph, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{t:.2f}",
             "-movflags", "+faststart", str(a.out / name)])

        cover = dict(text="BROWARD,\nWHAT YOU\nORDERING?", t0=-1, t1=99, style="hook", y=0.42, x=None)
        tag = dict(text=HANDLE, t0=-1, t1=99, style="sticker", y=0.64, x=None)
        # Frame from the Smoke Box reveal, after the flash and before its titles come in.
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", "30.3", "-i", str(silent),
             "-vf", f"{drawtext(c, cover)},{drawtext(c, tag)}",
             "-frames:v", "1", "-q:v", "2", str(a.out / "cover.jpg")])

    with open(a.out / "captions.srt", "w", encoding="utf-8") as f:
        for i, (s, e, line) in enumerate(VO, 1):
            f.write(f"{i}\n{srt_time(s)} --> {srt_time(e)}\n{line}\n\n")
    (a.out / "edit_list.txt").write_text("\n".join(edit) + "\n")
    print(f"Done: {a.out / name}  ({t:.1f}s)  + cover.jpg, captions.srt, edit_list.txt")


if __name__ == "__main__":
    main()
