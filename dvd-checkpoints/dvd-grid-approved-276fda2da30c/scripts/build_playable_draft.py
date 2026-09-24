import hashlib
import json
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageOps
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
BASE = ROOT / "dvd/full-build"
PREP = BASE / "navigation-preparation-v1"
OUT = BASE / "playable-draft-v1"
ART = ROOT / "dvd/source-template-v1/rift-signal-remaster/assets"
SCI = ROOT / "visuals/science-originals"
for folder in ("media", "frames", "audio", "logs", "masks", "cache"):
    (OUT / folder).mkdir(parents=True, exist_ok=True)
PLAN = json.loads((PREP / "dvd-menu-plan.json").read_text())
GRAPH = json.loads((BASE / "branch-map.json").read_text())
PROMPTS = json.loads((BASE / "choice-audio-v1/manifest.json").read_text())
PROMPTS = {r["media"]: r for r in PROMPTS}
ENV = dict(os.environ, VIDEO_FORMAT="NTSC")
SR = 24000
R = Image.Resampling.LANCZOS
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
if not FONT.is_file():
    raise RuntimeError("DejaVu Sans font is missing.")
SCRIPT_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
missing_art = set()

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def run(args, name, inp=None, out=None):
    log = OUT / "logs" / (name + ".log")
    with log.open("wb") as errors:
        p = subprocess.run(
            args, cwd=OUT, env=ENV, stdin=inp,
            stdout=out if out is not None else errors, stderr=errors,
        )
    if p.returncode:
        raise RuntimeError(
            f"{name} failed.\n"
            + log.read_text(errors="replace")[-6500:]
            + f"\nFull log: {log}"
        )

@lru_cache(maxsize=12)
def font(size):
    return ImageFont.truetype(str(FONT), size)

@lru_cache(maxsize=12)
def picture(path, width, height):
    with Image.open(path) as source:
        return ImageOps.contain(
            source.convert("RGB"), (width, height), method=R
        )

def place(canvas, path, box):
    if not path.is_file():
        raise RuntimeError(f"Missing existing artwork: {path}")
    x0, y0, x1, y1 = box
    image = picture(str(path), x1-x0, y1-y0)
    canvas.paste(image, (
        x0 + (x1-x0-image.width)//2,
        y0 + (y1-y0-image.height)//2,
    ))

def wrapped(text, width, size):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if current and draw.textlength(trial, font=font(size)) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]

def center(draw, text, y, size, fill="#eaf5ff"):
    draw.text((640, y), text, font=font(size), fill=fill, anchor="mt")

TOPICS = {
    (2,1): "Earth: our home",
    (2,2): "Earth and the Moon",
    (2,3): "The Sun and its planets",
    (2,4): "The heliosphere",
    (2,5): "The Milky Way",
    (3,1): "Different kinds of galaxies",
    (3,2): "The Local Group",
    (3,3): "A galaxy cluster",
    (3,4): "The cosmic web",
    (3,5): "The observable universe",
}
NAMES = {
    "captain": "CAPTAIN MARCUS",
    "elena": "ELENA / SIGNAL OPERATIONS",
    "chase": "CHASE / PILOT",
    "haven": "HAVEN / GROUND STATION",
    "ship": "ASTERION / SHIP COMPUTER",
}
PORTRAITS = {
    "captain": ("captain-marcus-value.png", "crew-quarters.png", 435),
    "elena": ("mentor-elena-torres.png", "signal-operations.png", 520),
    "chase": ("pilot-chase-mercer.png", "bridge-view.png", 585),
}

def base_frame(row):
    im = Image.new("RGB", (1280,720), "#061019")
    d = ImageDraw.Draw(im)
    d.text((80,38), "RIFT SIGNAL", font=font(30), fill="#75d8ff")
    d.text((1200,46), "PLAYABLE DRAFT", font=font(18),
           fill="#a9bdca", anchor="ra")
    box = (80,110,1200,438)
    d.rectangle(box, fill="#020609", outline="#365269", width=2)
    role = row.get("role", "ship")
    set_no = int(row.get("set", 0))
    episode = int(row.get("episode", 0))
    tag = row.get("option", row.get("tag", "all"))
    credit = "Best Polity LLC / Rift Signal"
    topic = TOPICS.get((set_no,episode))

    if topic:
        if (set_no,episode) == (3,1) and tag == "spiral":
            place(im, SCI/"whirlpool-galaxy.tif", (84,114,1196,434))
            credit = "NASA / ESA / S. Beckwith / Hubble Heritage Team"
        elif (set_no,episode) == (3,3):
            place(im, SCI/"webb-first-deep-field.png", (84,114,1196,434))
            credit = "NASA / ESA / CSA / STScI — infrared composite"
        else:
            label = row.get("label", topic)
            missing_art.add(f"Set {set_no}, episode {episode}: {label}")
            for i, line in enumerate(wrapped(label, 980, 40)[:3]):
                center(d, line, 175+i*50, 40)
            center(d, "ILLUSTRATION PENDING", 345, 22, "#a9bdca")
    elif tag in ("planet","edge","cloud","stars","pair","group"):
        file = "planet.jpg" if tag in ("planet","edge","cloud") else "stars.jpg"
        place(im, ART/"signals"/file, (84,114,1196,434))
    elif role in PORTRAITS:
        portrait, room, x = PORTRAITS[role]
        place(im, ART/"ship"/room, (84,114,1196,434))
        d.rectangle((x-4,114,x+204,434), fill="#0c1823",
                    outline="#75d8ff", width=2)
        place(im, ART/"crew"/portrait, (x,118,x+200,430))
    elif role == "haven":
        center(d, "HAVEN", 180, 54, "#75d8ff")
        center(d, "GROUND RESEARCH STATION", 255, 25)
        center(d, "COMMUNICATIONS CHANNEL OPEN", 320, 22, "#8ae0d6")
    else:
        center(d, "ASTERION", 180, 54, "#75d8ff")
        center(d, "SHIP COMPUTER", 255, 27)
        center(d, "SIGNAL OPERATIONS", 320, 22, "#a9bdca")

    d.rectangle((80,452,1200,574), fill="#0c1823")
    speaker = NAMES.get(role, "SIGNAL OPERATIONS")
    if row["kind"] == "choice":
        speaker = "YOUR CHOICE / OPTIONS KEEP RETURNING"
    d.text((98,459), speaker, font=font(19), fill="#75d8ff")
    d.rectangle((80,582,1200,648), fill="#12313e",
                outline="#68ddda", width=2)
    action = "PRESS OK TO CHOOSE" if row["kind"] == "choice" else "PRESS OK TO CONTINUE"
    if row["kind"] == "welcome":
        action = "PRESS OK TO JOIN YOUR CREW"
    if row["kind"] == "end":
        action = "PRESS OK TO START AGAIN"
    center(d, action, 599, 27)
    center(d, credit, 673, 17, "#a9bdca")
    return im

def filt(x, hz, kind):
    return sosfilt(
        butter(2, hz, btype=kind, fs=SR, output="sos"), x
    ).astype(np.float32)

def level(x, db):
    rms = np.sqrt(np.mean(np.asarray(x, dtype=np.float64)**2))
    return x * (10**(db/20) / max(float(rms), 1e-9))

def fade(x, seconds):
    n = min(round(seconds*SR), len(x)//2)
    if n:
        shape = (n,) + (1,)*(x.ndim-1)
        x[:n] *= np.linspace(0,1,n).reshape(shape)
        x[-n:] *= np.linspace(1,0,n).reshape(shape)
    return x

def sound(row, source, seed):
    x, rate = sf.read(source, dtype="float32", always_2d=True)
    if rate != SR or x.shape[1] not in (1,2) or not len(x):
        raise RuntimeError(f"Unexpected audio format: {source}")
    if not np.isfinite(x).all():
        raise RuntimeError(f"Invalid audio: {source}")
    if x.shape[1] == 1:
        x = np.repeat(x,2,axis=1)
    if row["kind"] == "dialogue":
        x = np.concatenate((x, np.zeros((round(.8*SR),2),np.float32)))
    n = len(x)
    rng = np.random.default_rng(seed)
    def noise(low,high):
        return filt(filt(rng.standard_normal(n).astype(np.float32),
                         low,"highpass"),high,"lowpass")
    t = np.arange(n)/SR
    role = row.get("role","ship")
    if role == "captain":
        common = level(noise(65,210),-61)
        detail = level(noise(100,260),-70)
        bed = np.column_stack((common+detail, common))
    elif role == "chase":
        common = level(noise(55,170),-59)
        engine = level(np.sin(2*np.pi*82*t)+.22*np.sin(2*np.pi*164*t),-64)
        bed = np.column_stack((common+.9*engine,common+engine))
    else:
        common = level(noise(110,420),-59)
        equipment = level(np.sin(2*np.pi*180*t)+.2*np.sin(2*np.pi*270*t),-66)
        bed = np.column_stack((common+equipment,common+.9*equipment))
    x = x + fade(bed.astype(np.float32),1.3)

    if role == "haven" and row["kind"] == "dialogue":
        node = GRAPH["nodes"][row["node"]]
        following = GRAPH["nodes"].get(node.get("next"), {})
        if following.get("role") != "haven":
            length = round(.09*SR)
            beep = fade(np.sin(2*np.pi*820*np.arange(length)/SR).astype(np.float32),.025)
            beep = level(beep,-38)
            offset = len(x)-round(.8*SR)+round(.12*SR)
            x[offset:offset+length] += np.column_stack((beep*1.025,beep*.975))
    peak = float(np.max(np.abs(x)))
    x *= min(1., .89/max(peak,1e-9))
    return x.astype(np.float32)

# The same verified button geometry is used for every visual menu.
spu_files = []
for stream_id, mode, box in [
    (0,"widescreen",(45,388,675,432)),
    (1,"letterbox",(45,352,675,384)),
]:
    for label,color in [
        ("highlight",(104,221,218,255)), ("select",(255,242,174,255))
    ]:
        mask = Image.new("RGBA",(720,480),(0,0,0,0))
        x0,y0,x1,y1=box
        ImageDraw.Draw(mask).rectangle(
            (x0+2,y0+2,x1-2,y1-2),outline=color,width=2)
        mask.save(OUT/"masks"/f"{mode}-{label}.png")
    root = ET.Element("subpictures",format="NTSC")
    stream = ET.SubElement(root,"stream")
    spu = ET.SubElement(
        stream,"spu",start="00:00:01.00",force="yes",
        highlight=str(OUT/"masks"/f"{mode}-highlight.png"),
        select=str(OUT/"masks"/f"{mode}-select.png"))
    ET.SubElement(
        spu,"button",name="continue",
        x0=str(box[0]),y0=str(box[1]),x1=str(box[2]),y1=str(box[3]),
        up="continue",down="continue",left="continue",right="continue")
    path=OUT/"masks"/f"{mode}.xml"
    ET.ElementTree(root).write(path,encoding="utf-8")
    spu_files.append(path)

art_state = [
    (str(p),p.stat().st_size,p.stat().st_mtime_ns)
    for base in (ART,SCI) for p in sorted(base.rglob("*")) if p.is_file()
]
build_key = hashlib.sha256(json.dumps({
    "script":SCRIPT_HASH, "art":art_state
},sort_keys=True).encode()).hexdigest()
rendered = []
for i,row in enumerate(PLAN["render"],1):
    name = Path(row["media"]).stem
    target = OUT / row["media"]
    prompt = PROMPTS.get(row["media"])
    if row["kind"] == "dialogue":
        source = Path(row["audio"])
        text = row["text"]
    elif prompt:
        source = Path(prompt["audio"])
        text = prompt["text"]
    else:
        raise RuntimeError(f"Missing narration for {name}")
    if not source.is_file():
        raise RuntimeError(f"Missing audio: {source}")

    stamp = hashlib.sha256(json.dumps({
        "build":build_key,"row":row,"text":text,
        "audio":digest(source)
    },sort_keys=True).encode()).hexdigest()
    marker = OUT/"cache"/f"{name}.json"
    # Build the base even on a resumed run to collect missing-art notes.
    base = base_frame(row)
    if marker.is_file() and target.is_file():
        prior = json.loads(marker.read_text())
        if prior.get("stamp") == stamp and target.stat().st_size:
            print(f"[{i}/{len(PLAN['render'])}] Reusing {name}",flush=True)
            rendered.append(prior)
            continue

    print(f"[{i}/{len(PLAN['render'])}] Rendering {name}",flush=True)
    audio = sound(row,source,2044+i)
    wav = OUT/"audio"/f"{name}.wav"
    sf.write(wav,audio,SR,subtype="PCM_16")
    seconds = len(audio)/SR
    lines = wrapped(text,1084,25)
    pages = [lines[j:j+3] for j in range(0,len(lines),3)]
    weights = [max(1,len(" ".join(page))) for page in pages]
    # Approximate caption timing; reserve the final selection gap.
    tail = 4.0 if row["kind"] == "choice" else .8
    speaking = max(.1,seconds-tail)
    durations = [speaking*w/sum(weights) for w in weights]
    durations[-1] += seconds-sum(durations)
    listing = []
    for j,(page,duration) in enumerate(zip(pages,durations)):
        screen = base.copy()
        draw = ImageDraw.Draw(screen)
        for k,line in enumerate(page):
            draw.text((98,486+28*k),line,font=font(25),fill="#edf6ff")
        path=OUT/"frames"/f"{name}-{j:02d}.png"
        screen.save(path)
        quoted = str(path).replace("'", "'\\''")
        listing.extend([f"file '{quoted}'",f"duration {duration:.6f}"])
    listing.append(f"file '{quoted}'")
    concat = OUT/"frames"/f"{name}.ffconcat"
    concat.write_text("\n".join(listing)+"\n")
    raw=OUT/"media"/f"{name}.raw.mpg"
    run([
        "ffmpeg","-hide_banner","-y",
        "-f","concat","-safe","0","-i",str(concat),
        "-i",str(wav),"-map","0:v:0","-map","1:a:0",
        "-t",str(seconds),
        "-vf","scale=720:480:flags=lanczos,setsar=32/27",
        "-r","30000/1001","-target","ntsc-dvd",
        "-aspect","16:9","-ac","2","-ar","48000","-b:a","192k",
        str(raw),
    ],name+"-encode")
    previous=raw
    intermediates=[raw]
    for sid,xml in enumerate(spu_files):
        dest=OUT/"media"/f"{name}.stream{sid}.mpg"
        with previous.open("rb") as inp,dest.open("wb") as out:
            run(["spumux","-m","dvd","-s",str(sid),str(xml)],
                name+f"-spumux-{sid}",inp,out)
        previous=dest
        intermediates.append(dest)
    previous.replace(target)
    for p in intermediates:
        p.unlink(missing_ok=True)
    data={"stamp":stamp,"media":row["media"],"seconds":seconds}
    marker.write_text(json.dumps(data))
    rendered.append(data)

dummy=OUT/"media/title-return.mpg"
run([
    "ffmpeg","-hide_banner","-y",
    "-f","lavfi","-i","color=c=black:s=720x480:r=30000/1001",
    "-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-t","1",
    "-vf","setsar=32/27","-target","ntsc-dvd","-aspect","16:9",
    "-ac","2","-ar","48000","-b:a","192k",str(dummy)
],"dummy-title")

# A fresh authored folder keeps any previous draft intact.
import tempfile
disc=Path(tempfile.mkdtemp(prefix="disc-",dir=OUT))
(disc/"AUDIO_TS").mkdir()
tree=ET.parse(PREP/"dvdauthor.xml")
tree.getroot().set("dest",str(disc))
for vob in tree.findall(".//vob"):
    path=OUT/vob.get("file")
    if not path.is_file():
        raise RuntimeError(f"Missing rendered video: {path}")
    vob.set("file",str(path))
xml=OUT/"dvdauthor.xml"
tree.write(xml,encoding="utf-8",xml_declaration=True)
print("Authoring all fifteen sections...",flush=True)
run(["dvdauthor","-x",str(xml)],"full-dvdauthor")

for name in ["VIDEO_TS.IFO","VIDEO_TS.BUP"] + [
    f"VTS_{i:02d}_0.IFO" for i in range(1,16)
]:
    p=disc/"VIDEO_TS"/name
    if not p.is_file() or not p.stat().st_size:
        raise RuntimeError(f"Missing authored control file: {name}")

notes = [
    "RIFT SIGNAL — PLAYABLE DRAFT",
    "All fifteen episodes; branching and processed voices included.",
    "Science illustrations listed below are still pending.",
    "Captions are paged using approximate timing.",
    "Room sound is mixed per clip; it stops during indefinite holds.",
    "Original portraits retain their existing poses.",
    "Pilot uses original bridge artwork pending a cockpit illustration.",
    "Physical-player branching and content review remain necessary.",
    "",
    "PENDING ILLUSTRATIONS:",
    *sorted(missing_art),
]
(OUT/"draft-notes.txt").write_text("\n".join(notes)+"\n")
iso=OUT/"rift-signal-playable-draft.iso"
temporary=OUT/"rift-signal-playable-draft.tmp.iso"
print("Creating the draft ISO...",flush=True)
run([
    "genisoimage","-dvd-video","-udf","-V","RIFT_SIGNAL_DRAFT",
    "-o",str(temporary),str(disc)
],"full-genisoimage")
if temporary.stat().st_size > 4_700_000_000:
    raise RuntimeError("Draft exceeds single-layer DVD capacity; keep files for adjustment.")
temporary.replace(iso)
iso.with_suffix(".iso.sha256").write_text(
    digest(iso)+"  "+iso.name+"\n")
(OUT/"render-manifest.json").write_text(json.dumps(rendered,indent=2))
print("\nSUCCESS: fifteen-episode playable DVD draft created.")
print(f"Visual menus rendered or reused: {len(rendered)}")
print(f"ISO size: {iso.stat().st_size/1_000_000:.1f} MB")
print(f"ISO: {iso}")
print(f"Draft limitations and missing artwork: {OUT/'draft-notes.txt'}")
print("Processed voices, quiet room beds, and Haven end cues included.")
print("Captions use approximate timing; science topic cards are temporary.")
print("No disc burned. Original recordings unchanged.")
