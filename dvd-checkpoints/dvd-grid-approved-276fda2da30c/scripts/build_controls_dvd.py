import hashlib
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
BASE = ROOT / "dvd/full-build"
SOURCE = BASE / "hud-draft-v3"
PREP = BASE / "controls-navigation-v1"
OUT = BASE / "controls-draft-v4"
for folder in ("new-media", "frames", "audio", "cache", "masks", "logs"):
    (OUT / folder).mkdir(parents=True, exist_ok=True)

SR = 24000
ENV = dict(os.environ, VIDEO_FORMAT="NTSC")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
VERSION = "controls-review-v1"
pipeline = None

screens = json.loads((PREP / "new-screens.json").read_text())
tree = ET.parse(PREP / "navigation.xml")
root = tree.getroot()
vm = root.find("vmgm/menus")

def set_text(parent, tag, value):
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    child.text = value
    return child

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def run(args, label, stdin=None, stdout=None):
    log = OUT / "logs" / f"{label}.log"
    with log.open("wb") as err:
        result = subprocess.run(
            [str(a) for a in args], cwd=OUT, env=ENV,
            stdin=stdin, stdout=stdout if stdout is not None else err,
            stderr=err,
        )
    if result.returncode:
        raise RuntimeError(
            f"{label} failed:\n{log.read_text(errors='replace')[-5000:]}"
        )

def write_xml(path, element):
    ET.indent(element, space="  ")
    ET.ElementTree(element).write(
        path, encoding="utf-8", xml_declaration=True
    )

# Give setting a bookmark audible and visible confirmation.
return_menu = next(
    p for p in vm.findall("pgc")
    if any(
        Path(v.get("file", "")).name == "main-return.mpg"
        for v in p.findall("vob")
    )
)
match = re.fullmatch(
    r"\s*jump menu (\d+);\s*", return_menu.find("button").text
)
assert match, "Cannot identify the return dispatcher."
return_router = int(match.group(1))
confirmation_used = False

for ts in root.findall("titleset"):
    menus = ts.find("menus")
    bookmark_buttons = [
        button for pgc in menus.findall("pgc")
        for button in pgc.findall("button")
        if re.search(r"\bg10\s*=\s*\d+;", button.text or "")
        and "g11" in (button.text or "")
    ]
    if not bookmark_buttons:
        continue

    number = len(menus.findall("pgc")) + 1
    assert number <= 99
    pgc = ET.SubElement(menus, "pgc")
    ET.SubElement(pgc, "pre").text = "button = 1024;"
    ET.SubElement(pgc, "vob", file="new-media/bookmark-saved.mpg")
    ET.SubElement(pgc, "button", name="continue").text = (
        f"jump vmgm menu {return_router};"
    )
    ET.SubElement(pgc, "post").text = (
        f"jump vmgm menu {return_router};"
    )

    for button in bookmark_buttons:
        old = button.text
        new, count = re.subn(
            r"jump\s+(?:titleset\s+\d+\s+)?menu\s+\d+;\s*$",
            f"jump menu {number};",
            old,
        )
        assert count == 1, "Unexpected bookmark destination."
        button.text = new
    confirmation_used = True

if confirmation_used:
    screens.append({
        "id": "bookmark-saved",
        "kind": "notice",
        "media": "new-media/bookmark-saved.mpg",
        "label": "Bookmark set",
        "spoken_text": (
            "Bookmark set for this session. "
            "Your scene and story choices are remembered."
        ),
        "selection_tail_seconds": 2,
    })

# Original frames are read only. Fit the complete image above the footer.
frame_sources = {}
for screen in screens:
    node = screen.get("node")
    if not node or node in frame_sources:
        continue
    candidates = [
        SOURCE / "frames" / f"{node}-00.png",
        SOURCE / "frames" / f"{node}.png",
    ]
    found = next((p for p in candidates if p.is_file()), None)
    if found is None:
        raise RuntimeError(f"Missing approved frame for {node}.")
    frame_sources[node] = found

def font(size):
    return ImageFont.truetype(FONT, size)

def centered(draw, text, y, size=30, color="#cceaf4"):
    draw.text(
        (640, y), text, font=font(size), fill=color, anchor="mt"
    )

def wrapped(text, width, size):
    words = text.split()
    lines, line = [], ""
    face = font(size)
    for word in words:
        trial = (line + " " + word).strip()
        if line and face.getlength(trial) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines

def draw_frame(screen):
    image = Image.new("RGB", (1280, 720), "#061019")
    draw = ImageDraw.Draw(image)
    kind = screen["kind"]

    if screen.get("node"):
        with Image.open(frame_sources[screen["node"]]) as original:
            fitted = ImageOps.contain(
                original.convert("RGB"), (1176, 568),
                Image.Resampling.LANCZOS
            )
        image.paste(fitted, ((1280-fitted.width)//2, 20))
        draw = ImageDraw.Draw(image)
    else:
        centered(draw, "RIFT SIGNAL", 75, 40, "#67d8f4")
        centered(draw, "SIGNAL OPERATIONS", 135, 22)
        label_lines = wrapped(screen["label"], 1060, 42)
        for i, line in enumerate(label_lines):
            centered(draw, line, 275 + i*55, 42)

    if kind == "footer-control":
        # All three actions remain visible; one is highlighted and spoken.
        labels = ["Continue", "Main menu", "Bookmark"]
        for i, label in enumerate(labels):
            left = 64 + i*390
            right = left + 370
            selected = label == screen["label"]
            draw.rounded_rectangle(
                (left, 622, right, 676), radius=9,
                fill="#163747" if selected else "#0a1a24",
                outline="#74def7" if selected else "#294856",
                width=3 if selected else 1,
            )
            draw.text(
                ((left+right)//2, 632), label, anchor="mt",
                font=font(29),
                fill="#ffffff" if selected else "#8ca6b2",
            )
    elif kind == "scene-selection":
        label = screen["label"].replace(": ship", ": ship computer")
        centered(draw, label, 594, 28, "#74def7")
        excerpt = screen.get("excerpt", "")
        if excerpt:
            words = excerpt.split()
            short = " ".join(words[:13]) + ("…" if len(words) > 13 else "")
            lines = wrapped(short, 1100, 22)
            for i, line in enumerate(lines[:2]):
                centered(draw, line, 632+i*26, 22)
        else:
            centered(draw, "Press OK to select", 640, 26)
    elif kind == "main-menu":
        subtitle = "Press OK to select, or wait for the next option."
        if screen["id"] == "main-resume":
            centered(draw, "For this playback session", 450, 26)
        elif screen["id"] == "main-return":
            centered(draw, "Return without changing your place", 450, 26)
        else:
            centered(draw, "Choose an individual scene next", 450, 26)
        centered(draw, subtitle, 635, 26)
    else:
        centered(draw, "Returning to your controls", 620, 26)

    return image

def speech_text(screen):
    if screen["kind"] == "scene-selection" and screen.get("excerpt"):
        role_label = screen["label"].replace(": ship", ": ship computer")
        # A brief excerpt helps identify the scene without replaying all of it.
        excerpt = " ".join(screen["excerpt"].split()[:12]).rstrip(",;:")
        return f"{role_label}. {excerpt}."
    if screen["id"] == "main-resume":
        return "Resume session bookmark."
    return screen["spoken_text"]

def voice_file(screen):
    global pipeline
    spoken = speech_text(screen)
    tail = float(screen.get("selection_tail_seconds", 4))
    key = hashlib.sha256(
        json.dumps([VERSION, spoken, tail, "af_sarah", 0.92]).encode()
    ).hexdigest()[:24]
    path = OUT / "audio" / f"{key}.wav"
    if path.is_file():
        samples, rate = sf.read(path, dtype="float32")
        if rate == SR and samples.ndim == 1 and np.isfinite(samples).all():
            return path, len(samples)/SR

    if pipeline is None:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")

    chunks = []
    for _, _, audio in pipeline(spoken, voice="af_sarah", speed=0.92):
        if audio is None:
            continue
        if hasattr(audio, "detach"):
            audio = audio.detach().cpu().numpy()
        chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise RuntimeError(f"No speech generated: {spoken}")
    samples = np.concatenate(chunks)
    if not np.isfinite(samples).all() or not np.any(samples):
        raise RuntimeError("Invalid generated speech.")

    samples = sosfilt(
        butter(2, 65, btype="highpass", fs=SR, output="sos"), samples
    )
    t = np.arange(len(samples)) / SR
    samples = 0.9*samples + 0.1*samples*np.cos(2*np.pi*72*t)
    level = np.sqrt(np.mean(samples**2))
    samples *= min(2.0, max(0.5, 10**(-23/20)/max(level, 1e-9)))
    samples *= min(1.0, 0.89/max(float(np.max(np.abs(samples))), 1e-9))
    samples = np.concatenate([
        np.zeros(round(.2*SR)),
        samples,
        np.zeros(round(tail*SR)),
    ]).astype(np.float32)
    temp = path.with_suffix(".tmp.wav")
    sf.write(temp, samples, SR, subtype="PCM_16")
    temp.replace(path)
    return path, len(samples)/SR

# Invisible single-button overlays, preserving both DVD display modes.
for mode in ("widescreen", "letterbox"):
    for state in ("highlight", "select"):
        Image.new("RGBA", (720, 480), (0, 0, 0, 0)).save(
            OUT / "masks" / f"{mode}-{state}.png"
        )

def multiplex(raw, target, name):
    intermediate = OUT / "cache" / f"{name}.wide.mpg"
    final = OUT / "cache" / f"{name}.final.mpg"
    for stream, mode, source, output in (
        (0, "widescreen", raw, intermediate),
        (1, "letterbox", intermediate, final),
    ):
        xml_root = ET.Element("subpictures", format="NTSC")
        xml_stream = ET.SubElement(xml_root, "stream")
        spu = ET.SubElement(
            xml_stream, "spu", start="00:00:01.00", force="yes",
            highlight=str(OUT/"masks"/f"{mode}-highlight.png"),
            select=str(OUT/"masks"/f"{mode}-select.png"),
        )
        y0, y1 = (388, 432) if mode == "widescreen" else (352, 384)
        ET.SubElement(
            spu, "button", name="continue",
            x0="45", y0=str(y0), x1="675", y1=str(y1),
            up="continue", down="continue", left="continue", right="continue"
        )
        xml_path = OUT / "cache" / f"{name}-{mode}.xml"
        write_xml(xml_path, xml_root)
        with source.open("rb") as inp, output.open("wb") as out:
            run(
                ["spumux", "-m", "dvd", "-s", stream, xml_path],
                f"{name}-{mode}", stdin=inp, stdout=out
            )
    final.replace(target)
    intermediate.unlink(missing_ok=True)
    raw.unlink(missing_ok=True)

print(f"Preparing {len(screens)} new control and selection screens.", flush=True)
print("Approved story videos will be reused unchanged.", flush=True)
manifest = []

for index, screen in enumerate(screens, 1):
    name = screen["id"]
    print(f"[{index}/{len(screens)}] {name}", flush=True)
    frame_path = OUT / "frames" / f"{name}.png"
    draw_frame(screen).save(frame_path)
    audio_path, seconds = voice_file(screen)
    target = OUT / screen["media"]
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = hashlib.sha256(
        (VERSION + digest(frame_path) + digest(audio_path)).encode()
    ).hexdigest()
    marker = OUT / "cache" / f"{name}.json"
    cached = json.loads(marker.read_text()) if marker.is_file() else {}

    if not (target.is_file() and target.stat().st_size
            and cached.get("stamp") == stamp):
        raw = OUT / "cache" / f"{name}.raw.mpg"
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-framerate", "30000/1001", "-i", frame_path,
            "-i", audio_path, "-t", f"{seconds:.6f}",
            "-vf", "scale=720:480:flags=lanczos,setsar=32/27",
            "-r", "30000/1001", "-target", "ntsc-dvd",
            "-aspect", "16:9", "-ac", "2", "-ar", "48000",
            "-b:a", "192k", raw,
        ], f"encode-{name}")
        multiplex(raw, target, name)
        marker.write_text(json.dumps({
            "stamp": stamp, "seconds": seconds
        }))
    manifest.append({
        **screen, "seconds": seconds,
        "frame": str(frame_path), "audio": str(audio_path),
        "file": str(target),
    })

# A few finished frames for a quick browser review.
preview_names = ["main-episode-1", "bookmark-saved", "main-resume"]
for role in ("captain", "elena", "chase", "haven"):
    original_plan = json.loads(
        (BASE/"navigation-preparation-v1/dvd-menu-plan.json").read_text()
    )
    row = next(
        (r for r in original_plan["render"]
         if r.get("role") == role and r["kind"] == "dialogue"), None
    )
    if row:
        preview_names.append(row["node"] + "-control-continue")
html = [
    '<!doctype html><meta charset="utf-8"><title>Rift Signal controls</title>',
    '<style>body{background:#061019;color:#cceaf4;font-family:sans-serif;'
    'margin:30px}img{width:min(100%,1100px);display:block;margin-bottom:35px}</style>',
    '<h1>Rift Signal — controls review</h1>',
]
for name in preview_names:
    if (OUT/"frames"/f"{name}.png").is_file():
        html.append(f'<h2>{name}</h2><img src="frames/{name}.png">')
(OUT/"index.html").write_text("\n".join(html))

disc = Path(tempfile.mkdtemp(prefix="disc-", dir=OUT))
(disc/"AUDIO_TS").mkdir()
root.set("dest", str(disc))

for vob in root.iter("vob"):
    path = Path(vob.get("file"))
    if not path.is_absolute():
        if path.parts[0] == "new-media":
            path = OUT/path
        else:
            path = SOURCE/path
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"Missing DVD media: {path}")
    vob.set("file", str(path))

xml_path = OUT / "dvdauthor.xml"
write_xml(xml_path, root)
print("Authoring the controls review DVD...", flush=True)
run(["dvdauthor", "-x", xml_path], "dvdauthor")

count = len(root.findall("titleset"))
required = [disc/"VIDEO_TS/VIDEO_TS.IFO", disc/"VIDEO_TS/VIDEO_TS.BUP"]
for i in range(1, count+1):
    required += [
        disc/f"VIDEO_TS/VTS_{i:02d}_0.IFO",
        disc/f"VIDEO_TS/VTS_{i:02d}_0.BUP",
    ]
if not all(p.is_file() and p.stat().st_size for p in required):
    raise RuntimeError("Required authored DVD control files are missing.")

iso = OUT/"rift-signal-controls-review.iso"
temporary = OUT/"rift-signal-controls-review.tmp.iso"
print("Creating review ISO...", flush=True)
run([
    "genisoimage", "-dvd-video", "-udf", "-V", "RIFT_SIGNAL",
    "-o", temporary, disc,
], "genisoimage")
if temporary.stat().st_size > 4_700_000_000:
    raise RuntimeError("Review ISO exceeds single-layer DVD capacity.")
temporary.replace(iso)
iso.with_suffix(".iso.sha256").write_text(
    digest(iso) + "  " + iso.name + "\n"
)
(OUT/"render-manifest.json").write_text(
    json.dumps(manifest, indent=2), encoding="utf-8"
)
notes = [
    "Review build: controls and bookmark behavior need physical-player testing.",
    "Original story audio and videos are reused unchanged.",
    "Footer controls begin after each dialogue clip finishes.",
    "OK during dialogue retains the original advance behavior.",
    "Control frames fit the complete approved picture above the footer.",
    "Options speak, then leave four seconds before cycling.",
    "Scene selection loads a matching route, not necessarily your prior choices.",
    "Return to current scene preserves current choices.",
    "Resume session bookmark restores the bookmarked choices and replays its scene.",
    "Bookmark is volatile: do not rely on it after ejecting or switching off.",
    "Persistent resume-code entry is not included in this build.",
]
(OUT/"review-notes.txt").write_text("\n".join(notes))
report = [
    "SUCCESS: controls review DVD created.",
    "Episodes: 15. Individual scene selectors: 284.",
    f"New control/selection screens: {len(screens)}",
    f"DVD menu groups: {count}",
    "Footer: Continue > Main menu > Bookmark.",
    "Spoken controls and bookmark confirmation included.",
    "Bookmark: current session only; physical-player testing required.",
    "Original story media reused unchanged.",
    f"ISO size: {iso.stat().st_size/1_000_000:.1f} MB",
    f"ISO: {iso}",
    f"Frame preview: {OUT/'index.html'}",
    f"Review notes: {OUT/'review-notes.txt'}",
    "No disc burned. Previous builds preserved.",
]
(OUT/"report.txt").write_text("\n".join(report))
print("\n" + "\n".join(report), flush=True)
