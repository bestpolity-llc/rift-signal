import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
BASE = ROOT / "dvd/full-build"
PLAN = BASE / "navigation-preparation-v1/dvd-menu-plan.json"
OUT = BASE / "choice-audio-v1"
OUT.mkdir(parents=True, exist_ok=True)
plan = json.loads(PLAN.read_text())
SR = 24000
pipeline = None

def silence(seconds):
    return np.zeros((round(seconds * SR), 2), dtype=np.float32)

def read_audio(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    x, rate = sf.read(path, dtype="float32", always_2d=True)
    if rate != SR or x.shape[1] not in (1, 2):
        raise RuntimeError(f"Unexpected audio format: {path}")
    if not len(x) or not np.isfinite(x).all():
        raise RuntimeError(f"Invalid audio: {path}")
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x

def filt(x, hz, kind):
    return sosfilt(
        butter(2, hz, btype=kind, fs=SR, output="sos"), x
    ).astype(np.float32)

def synthesize(text):
    global pipeline
    key = hashlib.sha256(
        ("ship-v1|af_sarah|0.92|" + text).encode()
    ).hexdigest()[:20]
    path = OUT / f"computer-{key}.wav"
    if path.exists():
        return path, read_audio(path)
    if pipeline is None:
        from kokoro import KPipeline
        pipeline = KPipeline(
            lang_code="a", repo_id="hexgrad/Kokoro-82M", device="cpu"
        )
    chunks = []
    for _, _, audio in pipeline(text, voice="af_sarah", speed=.92):
        if audio is not None:
            if hasattr(audio, "detach"):
                audio = audio.detach().cpu().numpy()
            chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise RuntimeError("Kokoro returned no audio.")
    x = np.concatenate(chunks)
    if not np.isfinite(x).all() or np.max(np.abs(x)) == 0:
        raise RuntimeError("Kokoro returned invalid audio.")
    x = filt(x, 65, "highpass")
    t = np.arange(len(x)) / SR
    x = .90 * x + .10 * x * np.cos(2 * np.pi * 72 * t)
    x += .025 * (x - filt(x, 1600, "lowpass"))
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    x *= np.clip(10 ** (-23 / 20) / max(rms, 1e-9), .5, 2.)
    stereo = np.column_stack((x * .985, x * 1.015))
    peak = float(np.max(np.abs(stereo)))
    stereo *= min(1., .89 / max(peak, 1e-9))
    temporary = path.with_suffix(".tmp.wav")
    sf.write(temporary, stereo, SR, subtype="PCM_16")
    temporary.replace(path)
    return path, read_audio(path)

choices = [r for r in plan["render"] if r["kind"] == "choice"]
records = []
preview = []
reused = 0
generated = 0

for i, row in enumerate(choices, 1):
    label = row["label"].strip().rstrip(".!?")
    existing = row.get("choice_audio", [])
    print(f"[{i}/{len(choices)}] {label}", flush=True)
    if existing:
        pieces = []
        texts = []
        for item in existing:
            pieces.append(read_audio(item["audio"]))
            pieces.append(silence(.35))
            texts.append(item["text"])
        audio = np.concatenate(pieces)
        text = " ".join(texts)
        reused += 1
        source = "existing approved prompt"
    else:
        text = (
            f"{label}. Press once to choose this option, then release. "
            "Or wait to hear the other option. Both options keep returning."
        )
        _, audio = synthesize(text)
        generated += 1
        source = "new ship computer prompt"

    # This is a selection window, not a deadline:
    # the DVD cycles back to the option until the player chooses.
    tail_seconds = 4.0
    audio = np.concatenate((silence(.2), audio, silence(tail_seconds)))
    path = OUT / f"{row['node']}-{row['option']}.wav"
    sf.write(path, audio, SR, subtype="PCM_16")
    records.append({
        "node": row["node"], "option": row["option"],
        "media": row["media"], "label": row["label"],
        "text": text, "audio": str(path),
        "seconds": len(audio) / SR,
        "selection_tail_seconds": tail_seconds,
        "source": source,
        "listening_review_required": source.startswith("new"),
    })
    preview.extend((audio, silence(1.0)))

for row in plan["render"]:
    if row["kind"] not in ("welcome", "end"):
        continue
    if row["kind"] == "welcome":
        text = (
            "Welcome to Rift Signal. Your station is ready. "
            "Press once to join your crew, then release the button. "
            "You can take your time."
        )
    else:
        text = (
            "Your mission is complete. Thank you for exploring with us. "
            "Press once if you would like to start again."
        )
    _, audio = synthesize(text)
    audio = np.concatenate((silence(.2), audio, silence(.8)))
    path = OUT / f"{row['kind']}.wav"
    sf.write(path, audio, SR, subtype="PCM_16")
    records.append({
        "kind": row["kind"], "media": row["media"],
        "text": text, "audio": str(path),
        "seconds": len(audio) / SR,
        "hold_after_playback": True,
        "listening_review_required": True,
    })
    preview.extend((audio, silence(1.0)))

sf.write(
    OUT / "choice-prompts-preview.wav",
    np.concatenate(preview), SR, subtype="PCM_16"
)
(OUT / "manifest.json").write_text(
    json.dumps(records, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
report = "\n".join([
    "SUCCESS: DVD choice audio prepared.",
    f"Choice screens covered: {len(choices)}",
    f"Existing prompts preserved: {reused}",
    f"Missing prompts generated or reused from cache: {generated}",
    "Welcome and ending prompts included.",
    "Each choice finishes speaking, then allows four seconds before cycling.",
    "Options repeat; there is no one-time selection deadline.",
    "New prompts need listening review.",
    "Original episode recordings unchanged. No DVD rebuilt or burned.",
    f"Output folder: {OUT}",
]) + "\n"
(OUT / "report.txt").write_text(report, encoding="utf-8")
print(report, flush=True)
