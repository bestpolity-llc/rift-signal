import ast
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
OUT = ROOT / "outputs/production-audio-v1"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000

SETS = {
    "mission-set-one": {
        "main": {"all", "visit", "planet", "edge", "detail", "thanks"},
        "alternate": {"all", "picture", "stars", "pair", "discovery", "evening"},
    },
    "mission-set-two": {
        "main": {"all", "ocean", "mars"},
        "alternate": {"all", "land", "saturn"},
    },
    "mission-set-three": {
        "main": {"all", "strand", "spiral"},
        "alternate": {"all", "void", "elliptical"},
    },
}

# Load only the existing sound-design functions and their constants.
# Do not run its preview creation or overwrite its files.
source = (ROOT / "make_four_rooms.py").read_text()
tree = ast.parse(source)
nodes = []
for node in tree.body:
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
        nodes.append(node)
    elif isinstance(node, ast.Assign):
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if names and names <= {"ROOT", "SR", "rng", "PAN"}:
            nodes.append(node)
sound = {"__name__": "rift_sound_design"}
exec(compile(ast.Module(body=nodes, type_ignores=[]),
             "approved_sound_design", "exec"), sound)
for name in ("process_voice", "build", "quiet"):
    if not callable(sound.get(name)):
        raise RuntimeError(f"Missing sound-design function: {name}")
original_process = sound["process_voice"]

def read_audio(path):
    x, rate = sf.read(path, dtype="float32")
    if rate != SR or x.ndim != 1 or not len(x):
        raise RuntimeError(f"Unexpected source format: {path}")
    if not np.isfinite(x).all() or np.max(np.abs(x)) == 0:
        raise RuntimeError(f"Invalid source audio: {path}")
    return x

# Check every source and route before generating replacements.
manifests = {}
for name, routes in SETS.items():
    rows = json.loads((ROOT/"outputs"/name/"manifest.json").read_text())
    allowed = set.union(*routes.values())
    if name == "mission-set-one":
        allowed |= {"cloud", "group"}
    unknown = {r["tag"] for r in rows} - allowed
    if unknown:
        raise RuntimeError(f"Unrecognized dialogue tags in {name}: {unknown}")
    for r in rows:
        if r["role"] not in {"captain", "elena", "chase", "ship", "haven"}:
            raise RuntimeError(f"Unknown role: {r['role']}")
        p = Path(r["file"])
        if not p.is_absolute():
            p = ROOT/p
        if not p.is_file():
            raise RuntimeError(f"Missing source: {p}")
    for route, tags in routes.items():
        for episode in range(1, 6):
            if not any(r["episode"] == episode and r["tag"] in tags for r in rows):
                raise RuntimeError(f"Empty episode: {name}, {route}, {episode}")
    manifests[name] = rows

pipeline = None
raw_dir = OUT/"eric-source-clips"
raw_dir.mkdir(exist_ok=True)
count = sum(r["role"] == "chase" for rows in manifests.values() for r in rows)
index = 0
for name, rows in manifests.items():
    for row in rows:
        row["original_file"] = row["file"]
        if row["role"] != "chase":
            continue
        index += 1
        key = hashlib.sha256(
            ("am_eric|0.96|" + row["text"]).encode()
        ).hexdigest()[:24]
        path = raw_dir/f"eric-{key}.wav"
        if path.exists():
            read_audio(path)
            print(f"[{index}/{count}] Reusing Eric: {name}", flush=True)
        else:
            print(f"[{index}/{count}] Generating Eric: {name}", flush=True)
            if pipeline is None:
                pipeline = KPipeline(
                    lang_code="a", device="cpu", repo_id="hexgrad/Kokoro-82M"
                )
            chunks = []
            for _, _, audio in pipeline(row["text"], voice="am_eric", speed=.96):
                if audio is not None:
                    if hasattr(audio, "detach"):
                        audio = audio.detach().cpu().numpy()
                    chunks.append(np.asarray(audio, dtype=np.float32).reshape(-1))
            if not chunks:
                raise RuntimeError("Kokoro returned no audio.")
            x = np.concatenate(chunks)
            if not np.isfinite(x).all() or np.max(np.abs(x)) == 0:
                raise RuntimeError("Kokoro returned invalid audio.")
            temporary = path.with_suffix(".tmp.wav")
            sf.write(temporary, x, SR, subtype="PCM_16")
            read_audio(temporary)
            temporary.replace(path)
        row["file"] = str(path)
        row["voice"] = "am_eric"
        row["seconds"] = sf.info(path).duration

def filt(x, hz, kind):
    return sosfilt(butter(2, hz, btype=kind, fs=SR, output="sos"), x)

def eric_processed(row):
    # Same voice level and placement as the approved Eric cockpit sample.
    x = read_audio(row["file"]).astype(np.float64)
    active = x[np.abs(x) > .01]
    rms = np.sqrt(np.mean(active*active)) if len(active) else .01
    x *= min(3., 10**(-23/20)/max(float(rms), 1e-6))
    peak = np.max(np.abs(x))
    if peak > .90:
        x *= .90/peak
    x = filt(x, 65, "highpass")
    x = .97*x + .03*filt(x, 2500, "lowpass")
    pan = .10
    y = np.column_stack((
        x*np.cos((pan+1)*np.pi/4),
        x*np.sin((pan+1)*np.pi/4),
    ))
    reflected = filt(x, 2200, "lowpass")
    for channel, seconds in ((0, .017), (1, .025)):
        delay = round(SR*seconds)
        if delay < len(x):
            y[delay:, channel] += .017*reflected[:-delay]
    return y.astype(np.float32)

cache = {}
def process(row):
    key = (row["role"], row["file"])
    if key not in cache:
        y = eric_processed(row) if row["role"] == "chase" else original_process(row)
        if not len(y) or not np.isfinite(y).all():
            raise RuntimeError(f"Invalid processed clip: {row['file']}")
        peak = float(np.max(np.abs(y)))
        if peak > .89:
            y = y*(.89/peak)
        cache[key] = y
    return cache[key]
sound["process_voice"] = process

def room(row):
    return {
        "captain": "quarters",
        "chase": "cockpit",
        "elena": "operations",
        "ship": "operations",
        "haven": "operations",
    }[row["role"]]

def assemble(rows):
    # Follow the speaker's location; Elena, the console, and received
    # Haven transmissions share the Signal Operations listening space.
    pieces = [sound["quiet"](1)]
    effects_used = False
    for location, group in itertools.groupby(rows, key=room):
        dialogue = list(group)
        effects = location == "operations" and len(dialogue) >= 3 and not effects_used
        y = sound["build"](dialogue, location, effects=effects)
        # Keep the existing between-line gaps without inserting extra
        # one-second pauses every time a speaker's room changes.
        pieces.append(y[SR:-SR])
        effects_used |= effects
    pieces.append(sound["quiet"](1))
    y = np.concatenate(pieces)
    if not np.isfinite(y).all():
        raise RuntimeError("Non-finite samples in assembled track.")
    peak = float(np.max(np.abs(y)))
    if peak > .95:
        y *= .95/peak
    return y

def duration(seconds):
    seconds = round(seconds)
    return f"{seconds//60}m {seconds%60:02d}s"

report = ["SUCCESS: UPDATED THREE-SET AUDIO", "Chase: Eric"]
totals = {"main": 0., "alternate": 0.}
for name, routes in SETS.items():
    folder = OUT/name
    clips = folder/"processed-clips"
    clips.mkdir(parents=True, exist_ok=True)
    rows = manifests[name]
    cache.clear()

    # Preserve every dialogue clip, including choices outside the two routes.
    for number, row in enumerate(rows, 1):
        path = clips/f"{number:03d}-{row['role']}.wav"
        sf.write(path, process(row), SR, subtype="PCM_16")
        row["processed_file"] = str(path)
    (folder/"manifest.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    for route, tags in routes.items():
        print(f"Assembling {name}: {route}", flush=True)
        total = 0.
        with sf.SoundFile(
            folder/f"full-listening-draft-{route}-stereo.wav",
            mode="w", samplerate=SR, channels=2, subtype="PCM_16"
        ) as full, sf.SoundFile(
            folder/f"full-listening-draft-{route}-mono.wav",
            mode="w", samplerate=SR, channels=1, subtype="PCM_16"
        ) as mono:
            for episode in range(1, 6):
                selected = [
                    r for r in rows if r["episode"] == episode and r["tag"] in tags
                ]
                # Stable ambience across repeated builds.
                sound["rng"] = np.random.default_rng(2044 + episode)
                y = assemble(selected)
                sf.write(folder/f"episode-{episode:02d}-{route}-stereo.wav",
                         y, SR, subtype="PCM_16")
                sf.write(folder/f"episode-{episode:02d}-{route}-mono.wav",
                         y.mean(axis=1), SR, subtype="PCM_16")
                full.write(y)
                mono.write(y.mean(axis=1))
                total += len(y)/SR
                report.append(f"{name}, {route}, episode {episode}: {duration(len(y)/SR)}")
        totals[route] += total
        report.append(f"{name}, {route}: TOTAL {duration(total)}")

    if name == "mission-set-one":
        extra = [r for tag in ("cloud", "group") for r in rows if r["tag"] == tag]
        if extra:
            y = assemble(extra)
            sf.write(folder/"additional-detail-branches-stereo.wav",
                     y, SR, subtype="PCM_16")
            sf.write(folder/"additional-detail-branches-mono.wav",
                     y.mean(axis=1), SR, subtype="PCM_16")

settings = {
    "chase_voice": "am_eric",
    "chase_speed": .96,
    "rooms": {role: room({"role": role}) for role in
              ("captain", "chase", "elena", "ship", "haven")},
    "routes": {name: {route: sorted(tags) for route, tags in routes.items()}
               for name, routes in SETS.items()},
    "sound_design_source": source,
    "notes": "Listening masters; player response delays excluded. Original files preserved.",
}
(OUT/"build-settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
report.extend([
    f"ALL THREE SETS, main: {duration(totals['main'])}",
    f"ALL THREE SETS, alternate: {duration(totals['alternate'])}",
    "Stereo and mono listening masters created.",
    "All dialogue branches retained as processed clips.",
    "Original recordings unchanged.",
    "Timings include listening-draft pauses, not player response delays.",
    f"Output folder: {OUT}",
])
(OUT/"report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n" + "\n".join(report), flush=True)
