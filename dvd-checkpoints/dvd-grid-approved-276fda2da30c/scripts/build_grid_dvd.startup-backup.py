import copy
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
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
BASE = ROOT / "dvd/full-build"
SOURCE = BASE / "controls-draft-v4"
OUT = BASE / "grid-draft-v5"
for directory in ("media", "frames", "audio", "cache", "logs", "masks"):
    (OUT / directory).mkdir(parents=True, exist_ok=True)

ENV = dict(os.environ, VIDEO_FORMAT="NTSC")
SR = 24000
VERSION = "grid-with-soft-click-v1"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
pipeline = None

source_xml = SOURCE / "dvdauthor.xml"
if not source_xml.is_file():
    raise RuntimeError(f"Missing previous controls build: {source_xml}")

plan = json.loads(
    (BASE / "navigation-preparation-v1/dvd-menu-plan.json").read_text()
)
locations = json.loads(
    (BASE / "controls-navigation-v1/menu-location-map.json").read_text()
)
tree = ET.parse(source_xml)
root = tree.getroot()
vmgm = root.find("vmgm")
vm = vmgm.find("menus")
old_sets = root.findall("titleset")
original_vm_pgcs = vm.findall("pgc")[:]
original_set_count = len(old_sets)

def write_xml(path, element):
    ET.indent(element, space="  ")
    ET.ElementTree(element).write(
        path, encoding="utf-8", xml_declaration=True
    )

def run(arguments, name, stdin=None, stdout=None):
    log = OUT / "logs" / f"{name}.log"
    with log.open("wb") as output:
        result = subprocess.run(
            [str(a) for a in arguments],
            cwd=OUT, env=ENV, stdin=stdin,
            stdout=stdout if stdout is not None else output,
            stderr=output,
        )
    if result.returncode:
        raise RuntimeError(
            f"{name} failed:\n{log.read_text(errors='replace')[-6000:]}"
        )

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def qualify(command, titleset):
    prefix = f"titleset {titleset} " if titleset else "vmgm "
    return re.sub(
        r"\bjump menu (\d+);",
        lambda match: f"jump {prefix}menu {match.group(1)};",
        command,
    )

def find_vm_action(filename):
    for pgc in original_vm_pgcs:
        if any(
            Path(v.get("file", "")).name == filename
            for v in pgc.findall("vob")
        ):
            return qualify(pgc.find("button").text, 0)
    raise RuntimeError(f"Missing existing menu: {filename}")

continue_action = find_vm_action("main-return.mpg")
resume_action = find_vm_action("main-resume.mpg")

scene_actions = {}
for number, ts in enumerate(old_sets, 1):
    for pgc in ts.find("menus").findall("pgc"):
        for vob in pgc.findall("vob"):
            filename = Path(vob.get("file", "")).stem
            if filename.startswith("select-"):
                scene_actions[filename[7:]] = qualify(
                    pgc.find("button").text, number
                )

dialogue = [r for r in plan["render"] if r["kind"] == "dialogue"]
assert len(dialogue) == 284, "Unexpected scene count."
assert all(r["node"] in scene_actions for r in dialogue)

entry = plan["chapters"][0]["entry"]
old_ts, old_menu = plan["node_locations"][entry]
start_ts, start_menu = locations[f"{old_ts}:{old_menu}"]
start_action = (
    " ".join(f"g{i} = 0;" for i in range(10))
    + f" jump titleset {start_ts} menu {start_menu};"
)

set_names = {
    1: "Join the Crew",
    2: "Our Place in Space",
    3: "The Wider Universe",
}
pages = {}

def option(label, slot, action=None, link=None, speech=None):
    return {
        "label": label, "slot": slot,
        "action": action, "link": link,
        "speech": speech or label,
    }

pages["home"] = {
    "title": "RIFT SIGNAL",
    "subtitle": "Choose where to begin",
    "top": True,
    "options": [
        option("Start from beginning", 0, action=start_action),
        option("Continue this session", 1, action=continue_action),
        option(
            "Resume bookmark", 2, action=resume_action,
            speech="Resume bookmark from this playback session."
        ),
        *[
            option(
                f"Set {s}: {set_names[s]}", s + 2,
                link=f"set-{s}"
            )
            for s in (1, 2, 3)
        ],
    ],
}

for set_number in (1, 2, 3):
    chapters = [
        (i, chapter)
        for i, chapter in enumerate(plan["chapters"], 1)
        if int(chapter["set"]) == set_number
    ]
    pages[f"set-{set_number}"] = {
        "title": set_names[set_number],
        "subtitle": "Choose an episode",
        "top": True,
        "options": [
            option(
                f"Episode {chapter['episode']}", index,
                link=f"episode-{number}-page-0"
            )
            for index, (number, chapter) in enumerate(chapters)
        ] + [option("Main menu", 5, link="home")],
    }

roles = {
    "ship": "Ship computer",
    "captain": "Captain",
    "elena": "Elena",
    "chase": "Chase",
    "haven": "Haven",
}
for chapter_number, chapter in enumerate(plan["chapters"], 1):
    rows = [
        r for r in dialogue
        if int(r["chapter"]) == chapter_number
    ]
    chunks = [rows[i:i + 6] for i in range(0, len(rows), 6)]
    for page_index, chunk in enumerate(chunks):
        choices = []
        for index, row in enumerate(chunk):
            scene_number = page_index * 6 + index + 1
            role = roles.get(row["role"], row["role"])
            label = f"Scene {scene_number}: {role}"
            excerpt = " ".join(row["text"].split()[:10]).rstrip(",;:")
            choices.append(option(
                label, index,
                action=scene_actions[row["node"]],
                speech=f"{label}. {excerpt}."
            ))

        if page_index:
            choices.append(option(
                "Previous page", 6,
                link=f"episode-{chapter_number}-page-{page_index - 1}"
            ))
        if page_index + 1 < len(chunks):
            choices.append(option(
                "Next page", 7,
                link=f"episode-{chapter_number}-page-{page_index + 1}"
            ))
        choices.append(option(
            "Episodes", 8, link=f"set-{chapter['set']}"
        ))

        pages[f"episode-{chapter_number}-page-{page_index}"] = {
            "title": f"Set {chapter['set']} · Episode {chapter['episode']}",
            "subtitle": f"Scenes · page {page_index + 1} of {len(chunks)}",
            "top": False,
            "options": choices,
        }

for page in pages.values():
    for item in page["options"]:
        if item["link"]:
            assert item["link"] in pages

new_group = None
new_group_number = None

def allocate(top):
    global new_group, new_group_number
    if top:
        group, domain = vm, 0
    else:
        if new_group is None or len(new_group.findall("pgc")) >= 80:
            ts = ET.SubElement(root, "titleset")
            new_group_number = len(root.findall("titleset"))
            assert new_group_number <= 99
            new_group = ET.SubElement(ts, "menus", lang="en")
            for child in old_sets[0].find("menus"):
                if child.tag != "pgc":
                    new_group.append(copy.deepcopy(child))
            ts.append(copy.deepcopy(old_sets[0].find("titles")))
        group, domain = new_group, new_group_number

    number = len(group.findall("pgc")) + 1
    assert number <= 99
    attrs = {"entry": "root"} if domain and number == 1 else {}
    pgc = ET.SubElement(group, "pgc", attrs)
    ET.SubElement(pgc, "pre").text = "button = 1024;"
    return (domain, number), pgc

def jump(address):
    domain, number = address
    if domain:
        return f"jump titleset {domain} menu {number};"
    return f"jump vmgm menu {number};"

entries = {}
screens = []
for key, page in pages.items():
    entries[key] = []
    for index, item in enumerate(page["options"]):
        address, pgc = allocate(page["top"])
        screen_id = f"grid-{key}-{index}"
        path = OUT / "media" / f"{screen_id}.mpg"
        ET.SubElement(pgc, "vob", file=str(path))
        ET.SubElement(pgc, "button", name="continue")
        ET.SubElement(pgc, "post")
        entries[key].append((address, pgc))
        screens.append({
            "id": screen_id, "page": key, "selected": index,
            "speech": item["speech"], "file": str(path),
        })

home = entries["home"][0][0]
assert home[0] == 0

for key, page in pages.items():
    for index, item in enumerate(page["options"]):
        _, pgc = entries[key][index]
        pgc.find("button").text = (
            jump(entries[item["link"]][0][0])
            if item["link"] else item["action"]
        )
        pgc.find("post").text = jump(
            entries[key][(index + 1) % len(entries[key])][0]
        )

# Existing main-menu links now open the visible grid.
for pgc in original_vm_pgcs:
    filenames = [
        Path(v.get("file", "")).name for v in pgc.findall("vob")
    ]
    if any(
        re.fullmatch(r"main-(return|resume|episode-\d+)\.mpg", name)
        for name in filenames
    ):
        pgc.find("pre").text = jump(home)

for ts in root.findall("titleset")[original_set_count:]:
    for pgc in ts.find("titles").findall("pgc"):
        post = pgc.find("post")
        if post is None:
            post = ET.SubElement(pgc, "post")
        post.text = f"call vmgm menu {home[1]};"

intro_address, intro_pgc = allocate(True)
intro_path = OUT / "media/grid-introduction.mpg"
ET.SubElement(intro_pgc, "vob", file=str(intro_path))
ET.SubElement(intro_pgc, "button", name="continue").text = jump(home)
ET.SubElement(intro_pgc, "post").text = jump(home)
screens.insert(0, {
    "id": "grid-introduction",
    "page": "home",
    "selected": None,
    "file": str(intro_path),
    "speech": (
        "Welcome to Rift Signal. The highlight moves by itself. "
        "Press OK when it reaches what you want. "
        "Or wait. Every option comes around again."
    ),
})

fpc = vmgm.find("fpc")
updated, count = re.subn(
    r"jump vmgm menu 1;\s*$",
    jump(intro_address),
    fpc.text,
)
assert count == 1, "Unexpected first-play commands."
fpc.text = updated

# Check all new commands before generating the actual menu media.
print("Checking grid navigation before rendering...", flush=True)
test_root = copy.deepcopy(root)
test_dir = Path(tempfile.mkdtemp(prefix="navigation-check-", dir=OUT))
test_root.set("dest", str(test_dir / "disc"))
placeholder = BASE / "hud-draft-v3/media/welcome.mpg"
assert placeholder.is_file()
for menus in test_root.iter("menus"):
    for vob in menus.iter("vob"):
        vob.set("file", str(placeholder))
test_xml = test_dir / "navigation.xml"
write_xml(test_xml, test_root)
run(["dvdauthor", "-x", test_xml], "navigation-check")
print("Grid navigation compiled. Rendering screens...", flush=True)

def font(size):
    return ImageFont.truetype(FONT, size)

def centered(draw, text, x, y, size, color):
    draw.text(
        (x, y), text,
        font=font(size), fill=color, anchor="mt"
    )

def wrap(text, width, size):
    face = font(size)
    lines, line = [], ""
    for word in text.split():
        attempt = (line + " " + word).strip()
        if line and face.getlength(attempt) > width:
            lines.append(line)
            line = word
        else:
            line = attempt
    if line:
        lines.append(line)
    return lines

def picture(screen):
    page = pages[screen["page"]]
    image = Image.new("RGB", (1280, 720), "#061019")
    draw = ImageDraw.Draw(image)
    centered(draw, page["title"], 640, 38, 36, "#73dff7")
    centered(draw, page["subtitle"], 640, 94, 25, "#c8dde7")

    for index, item in enumerate(page["options"]):
        row, column = divmod(item["slot"], 3)
        x = 60 + column * 392
        y = 155 + row * 151
        active = screen["selected"] == index
        draw.rounded_rectangle(
            (x, y, x + 376, y + 130), radius=13,
            fill="#174457" if active else "#10232f",
            outline="#99eeff" if active else "#3a5e70",
            width=5 if active else 2,
        )
        lines = wrap(item["label"], 326, 28)
        top = y + (130 - len(lines) * 36) // 2
        for line_number, line in enumerate(lines):
            centered(
                draw, line, x + 188, top + line_number * 36, 28,
                "#ffffff" if active else "#c3d4df",
            )

    instruction = (
        "The highlight moves. Press OK to choose."
        if screen["selected"] is not None
        else "Listen first. The highlight will move automatically."
    )
    centered(draw, instruction, 640, 641, 27, "#dfedf5")
    return image

def speech(screen):
    global pipeline
    text = screen["speech"]
    has_click = screen["selected"] is not None
    key = hashlib.sha256(
        json.dumps([VERSION, text, has_click]).encode()
    ).hexdigest()[:24]
    path = OUT / "audio" / f"{key}.wav"

    if path.is_file():
        info = sf.info(path)
        assert info.samplerate == SR
        return path, info.frames / SR

    if pipeline is None:
        from kokoro import KPipeline
        pipeline = KPipeline(
            lang_code="a", repo_id="hexgrad/Kokoro-82M"
        )

    chunks = []
    for _, _, audio in pipeline(text, voice="af_sarah", speed=.92):
        if audio is not None:
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise RuntimeError("Speech generation returned no audio.")

    x = np.concatenate(chunks)
    assert np.isfinite(x).all() and np.any(x)
    x = sosfilt(
        butter(2, 65, btype="highpass", fs=SR, output="sos"), x
    )
    t = np.arange(len(x)) / SR
    x = .9 * x + .1 * x * np.cos(2 * np.pi * 72 * t)
    rms = np.sqrt(np.mean(x * x))
    x *= np.clip(10**(-23 / 20) / max(rms, 1e-9), .5, 2.)
    x *= min(1., .89 / max(float(np.max(np.abs(x))), 1e-9))

    # Keep four seconds after each spoken option.
    x = np.concatenate((
        np.zeros(round(.2 * SR)), x, np.zeros(4 * SR)
    )).astype(np.float32)

    # Soft tick when the highlight changes, before the spoken label.
    if has_click:
        count = round(.055 * SR)
        t = np.arange(count) / SR
        envelope = np.exp(-85 * t)
        envelope *= np.minimum(t / .004, 1)
        envelope *= np.minimum((t[-1] - t) / .008, 1)
        tick = (
            np.sin(2 * np.pi * 460 * t)
            + .22 * np.sin(2 * np.pi * 690 * t)
        ) * envelope
        tick *= .018 / max(float(np.max(np.abs(tick))), 1e-9)
        offset = round(.04 * SR)
        x[offset:offset + count] += tick.astype(np.float32)

    temp = path.with_suffix(".tmp.wav")
    sf.write(temp, x, SR, subtype="PCM_16")
    temp.replace(path)
    return path, len(x) / SR

# Invisible OK button. The visible outline is rendered into each frame.
for mode in ("widescreen", "letterbox"):
    for state in ("highlight", "select"):
        Image.new("RGBA", (720, 480), (0, 0, 0, 0)).save(
            OUT / "masks" / f"{mode}-{state}.png"
        )
    xml = ET.Element("subpictures", format="NTSC")
    stream = ET.SubElement(xml, "stream")
    spu = ET.SubElement(
        stream, "spu", start="00:00:01.00", force="yes",
        highlight=str(OUT / "masks" / f"{mode}-highlight.png"),
        select=str(OUT / "masks" / f"{mode}-select.png"),
    )
    y0, y1 = (388, 432) if mode == "widescreen" else (352, 384)
    ET.SubElement(
        spu, "button", name="continue",
        x0="45", y0=str(y0), x1="675", y1=str(y1),
        up="continue", down="continue",
        left="continue", right="continue",
    )
    write_xml(OUT / "masks" / f"{mode}.xml", xml)

for index, screen in enumerate(screens, 1):
    name = screen["id"]
    print(f"[{index}/{len(screens)}] {name}", flush=True)
    frame = OUT / "frames" / f"{name}.png"
    picture(screen).save(frame)
    audio, seconds = speech(screen)
    target = Path(screen["file"])
    stamp = hashlib.sha256(
        (VERSION + digest(frame) + digest(audio)).encode()
    ).hexdigest()
    marker = OUT / "cache" / f"{name}.json"
    saved = json.loads(marker.read_text()) if marker.is_file() else {}

    if (
        target.is_file() and target.stat().st_size
        and saved.get("stamp") == stamp
    ):
        continue

    raw = OUT / "cache" / f"{name}.raw.mpg"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", "30000/1001", "-i", frame,
        "-i", audio, "-t", f"{seconds:.6f}",
        "-vf", "scale=720:480:flags=lanczos,setsar=32/27",
        "-r", "30000/1001", "-target", "ntsc-dvd",
        "-aspect", "16:9", "-ac", "2", "-ar", "48000",
        "-b:a", "192k", raw,
    ], f"encode-{name}")

    wide = OUT / "cache" / f"{name}.wide.mpg"
    final = OUT / "cache" / f"{name}.final.mpg"
    for stream, mode, src, dst in (
        (0, "widescreen", raw, wide),
        (1, "letterbox", wide, final),
    ):
        with src.open("rb") as inp, dst.open("wb") as output:
            run(
                [
                    "spumux", "-m", "dvd", "-s", stream,
                    OUT / "masks" / f"{mode}.xml"
                ],
                f"{name}-{mode}", stdin=inp, stdout=output,
            )

    final.replace(target)
    raw.unlink(missing_ok=True)
    wide.unlink(missing_ok=True)
    marker.write_text(json.dumps({
        "stamp": stamp, "seconds": seconds
    }))

disc = Path(tempfile.mkdtemp(prefix="disc-", dir=OUT))
(disc / "AUDIO_TS").mkdir()
root.set("dest", str(disc))
for vob in root.iter("vob"):
    path = Path(vob.get("file"))
    assert path.is_absolute() and path.is_file(), f"Missing media: {path}"

xml = OUT / "dvdauthor.xml"
write_xml(xml, root)
print("Authoring complete grid-menu DVD...", flush=True)
run(["dvdauthor", "-x", xml], "dvdauthor")

group_count = len(root.findall("titleset"))
required = ["VIDEO_TS.IFO", "VIDEO_TS.BUP"]
for i in range(1, group_count + 1):
    required += [f"VTS_{i:02d}_0.IFO", f"VTS_{i:02d}_0.BUP"]
for name in required:
    path = disc / "VIDEO_TS" / name
    assert path.is_file() and path.stat().st_size, f"Missing {name}"

iso = OUT / "rift-signal-grid-review.iso"
temp_iso = OUT / "rift-signal-grid-review.tmp.iso"
print("Creating grid review ISO...", flush=True)
run([
    "genisoimage", "-dvd-video", "-udf", "-V", "RIFT_SIGNAL",
    "-o", temp_iso, disc,
], "genisoimage")
assert temp_iso.stat().st_size <= 4_700_000_000, "ISO exceeds DVD capacity."
temp_iso.replace(iso)
iso.with_suffix(".iso.sha256").write_text(
    digest(iso) + "  " + iso.name + "\n"
)
(OUT / "grid-plan.json").write_text(json.dumps(pages, indent=2))
(OUT / "render-manifest.json").write_text(json.dumps(screens, indent=2))

preview = [
    '<!doctype html><meta charset="utf-8"><title>Rift Signal grids</title>',
    '<style>body{background:#061019;color:white;font-family:sans-serif}'
    'img{display:block;width:min(100%,1100px);margin:25px auto}</style>',
    '<h1>Rift Signal — scanning grids</h1>',
]
for name in (
    "grid-home-0", "grid-home-3",
    "grid-set-1-0", "grid-episode-1-page-0-0"
):
    preview.append(f'<img src="frames/{name}.png">')
(OUT / "index.html").write_text("\n".join(preview))

report = [
    "SUCCESS: grid-menu review DVD created.",
    "Opening menu: six visible tiles with a moving highlight.",
    "Spoken scanning instructions play when the disc loads.",
    "Soft click included when the grid highlight changes.",
    "Three sets, fifteen episodes, and paged individual-scene grids.",
    "Options speak, then allow four seconds before advancing.",
    "Existing story videos, footer controls and session bookmark retained.",
    "Bookmark remains current-session only.",
    f"New grid screens: {len(screens)}",
    f"ISO size: {iso.stat().st_size / 1_000_000:.1f} MB",
    f"ISO: {iso}",
    f"Preview: {OUT / 'index.html'}",
    "Physical-player testing remains. No disc burned.",
]
(OUT / "report.txt").write_text("\n".join(report))
print("\n" + "\n".join(report), flush=True)
