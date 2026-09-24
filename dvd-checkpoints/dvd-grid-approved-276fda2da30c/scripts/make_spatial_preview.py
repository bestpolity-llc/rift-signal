import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
SOURCE = ROOT / "outputs/mission-set-one/manifest.json"
OUT = ROOT / "outputs/spatial-preview"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000
GAP = round(.55 * SR)

# Positive pan = right. Both channels retain every speaker.
PAN = {
    "captain": -.12,
    "chase": .12,
    "elena": -.025,
    "ship": 0.,
    "haven": .055,
}
ROOM = {
    "captain": .030,
    "chase": .035,
    "elena": .015,
    "ship": .010,
    "haven": .020,
}

def filt(x, cutoff, kind):
    return sosfilt(
        butter(2, cutoff, btype=kind, fs=SR, output="sos"), x
    ).astype(np.float32)

def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))

def db(x):
    return 20 * np.log10(max(float(x), 1e-12))

def voice_mix(x, role):
    # Small tonal changes. Most of each voice remains unprocessed.
    clean = filt(x, 65, "highpass")
    if role == "captain":
        shaped = clean + .07 * filt(clean, 450, "lowpass")
    elif role == "chase":
        shaped = clean + .035 * (clean - filt(clean, 1800, "lowpass"))
    elif role == "haven":
        comms = filt(filt(clean, 170, "highpass"), 6200, "lowpass")
        shaped = .75 * clean + .25 * comms
    elif role == "ship":
        shaped = .97 * clean + .03 * filt(clean, 4200, "lowpass")
    else:
        shaped = clean

    # Modest loudness matching, capped to avoid large gain changes.
    level = rms(shaped)
    gain = np.clip(10**(-23/20) / max(level, 1e-9), .5, 2.)
    shaped = shaped * gain
    pan = PAN[role]
    stereo = np.column_stack((
        shaped * (1-pan),
        shaped * (1+pan),
    )).astype(np.float32)

    # Very low-level, positive-polarity reflections.
    # No phase inversion or delayed main voice.
    room_source = filt(shaped, 3000, "lowpass")
    for channel, delay_ms in ((0, 19), (1, 27)):
        delay = round(delay_ms * SR / 1000)
        if delay < len(shaped):
            stereo[delay:, channel] += ROOM[role] * room_source[:-delay]
    return stereo

rows = json.loads(SOURCE.read_text(encoding="utf-8"))
selected = [
    row for row in rows
    if row["episode"] == 2 and row["tag"] in {"all", "visit"}
]
if not selected:
    raise RuntimeError("No Episode Two dialogue found.")

parts = []
speakers = set()
for row in selected:
    path = Path(row["file"])
    if not path.is_absolute():
        path = ROOT / path
    samples, rate = sf.read(path, dtype="float32")
    if rate != SR or samples.ndim != 1:
        raise RuntimeError(f"Unexpected audio format: {path}")
    if not np.isfinite(samples).all():
        raise RuntimeError(f"Invalid audio: {path}")
    parts.append(voice_mix(samples, row["role"]))
    parts.append(np.zeros((GAP, 2), dtype=np.float32))
    speakers.add(row["role"])

dialogue = np.concatenate(parts)
n = len(dialogue)
t = np.arange(n, dtype=np.float64) / SR
rng = np.random.default_rng(20260923)

def engine_noise():
    noise = rng.standard_normal(n).astype(np.float32)
    noise = filt(filt(noise, 85, "highpass"), 380, "lowpass")
    return noise / max(rms(noise), 1e-9)

# Mostly shared ambience with a little independent left/right texture.
# Steady engine tones: no alarms, rhythmic pulsing, or moving effects.
common = engine_noise()
left_texture = engine_noise()
right_texture = engine_noise()
tone = (
    .30 * np.sin(2*np.pi*96*t)
    + .13 * np.sin(2*np.pi*144*t + .4)
    + .06 * np.sin(2*np.pi*192*t + .9)
).astype(np.float32)

bed = np.column_stack((
    .82*common + .18*left_texture + tone,
    .82*common + .18*right_texture + tone,
)).astype(np.float32)

# Quiet by design: roughly 23 dB below the nominal speech RMS.
bed *= 10**(-46/20) / max(rms(bed), 1e-9)
fade = min(2*SR, n//2)
envelope = np.ones(n, dtype=np.float32)
envelope[:fade] = np.linspace(0, 1, fade)
envelope[-fade:] = np.linspace(1, 0, fade)
bed *= envelope[:, None]

mix = dialogue + bed
peak = float(np.max(np.abs(mix)))
gain = min(1., 10**(-1/20) / max(peak, 1e-9))
mix *= gain
bed *= gain
mono = mix.mean(axis=1)

if not np.isfinite(mix).all() or not np.isfinite(mono).all():
    raise RuntimeError("Non-finite samples in mix.")

sf.write(OUT / "bridge-stereo.wav", mix, SR, subtype="PCM_16")
sf.write(OUT / "bridge-mono.wav", mono, SR, subtype="PCM_16")
sf.write(OUT / "propulsion-bed-preview.wav", bed, SR, subtype="PCM_16")
sf.write(
    OUT / "voices-only-stereo.wav",
    dialogue * gain, SR, subtype="PCM_16"
)

duration = n / SR
report = [
    "SUCCESS: spatial preview generated",
    f"Duration: {int(duration//60)}m {int(duration%60):02d}s",
    "Speakers: " + ", ".join(sorted(speakers)),
    f"Stereo sample peak: {db(np.max(np.abs(mix))):.1f} dBFS",
    f"Mono sample peak: {db(np.max(np.abs(mono))):.1f} dBFS",
    f"Propulsion RMS: {db(rms(bed)):.1f} dBFS",
    "Mono comparison is the average of the stereo channels.",
    "No main-voice phase inversion or stereo delay.",
    "Listening review is still required.",
    f"Output folder: {OUT}",
]
(OUT / "report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report), flush=True)
