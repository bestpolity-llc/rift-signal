import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
OUT = ROOT / "outputs/room-preview-softer"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000
rng = np.random.default_rng(20260924)
rows = json.loads(
    (ROOT / "outputs/mission-set-one/manifest.json").read_text()
)

def find(role, beginning):
    matches = [
        r for r in rows
        if r["episode"] == 2 and r["role"] == role
        and r["text"].startswith(beginning)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Cannot identify dialogue: {beginning}")
    return matches[0]

def filter_audio(x, cutoff, kind):
    sos = butter(2, cutoff, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x).astype(np.float32)

def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))

def level(x, db):
    return x * (10**(db/20) / max(rms(x), 1e-9))

def fade(x, seconds=.03):
    x = x.copy()
    count = min(round(seconds*SR), len(x)//2)
    if count:
        shape = (count,) + (1,)*(x.ndim-1)
        x[:count] *= np.linspace(0, 1, count).reshape(shape)
        x[-count:] *= np.linspace(1, 0, count).reshape(shape)
    return x

def silence(seconds):
    return np.zeros((round(seconds*SR), 2), dtype=np.float32)

def position(x, pan):
    return np.column_stack((x*(1-pan), x*(1+pan))).astype(np.float32)

def soft_tone(hz, seconds, db, pan=0):
    t = np.arange(round(seconds*SR)) / SR
    x = fade(np.sin(2*np.pi*hz*t).astype(np.float32), .025)
    return position(level(x, db), pan)

def voice(row, room):
    path = Path(row["file"])
    if not path.is_absolute():
        path = ROOT / path
    x, rate = sf.read(path, dtype="float32")
    if rate != SR or x.ndim != 1 or not np.isfinite(x).all():
        raise RuntimeError(f"Unexpected audio: {path}")

    role = row["role"]
    x = filter_audio(x, 65, "highpass")
    if role == "haven":
        # Clean wideband telephone-like timbre; no static or distortion.
        x = filter_audio(filter_audio(x, 180, "highpass"), 5200, "lowpass")
    elif role == "captain":
        x += .045 * filter_audio(x, 450, "lowpass")

    x *= np.clip(10**(-23/20) / max(rms(x), 1e-9), .5, 2.)
    pans = {
        "captain": -.07, "chase": .07, "elena": -.015,
        "ship": 0., "haven": .035,
    }
    stereo = position(x, pans[role])

    # Haven comes through a console, without local room reflections.
    if role != "haven":
        amount = .008 if room == "quarters" else .014
        reflection = filter_audio(x, 2800, "lowpass")
        for channel, ms in ((0, 17), (1, 23)):
            delay = round(ms*SR/1000)
            if delay < len(x):
                stereo[delay:, channel] += amount*reflection[:-delay]
    return stereo

def texture(n, low, high):
    x = rng.standard_normal(n).astype(np.float32)
    return filter_audio(filter_audio(x, low, "highpass"), high, "lowpass")

def ambience(n, room):
    if room == "quarters":
        # Air only: no engine tones.
        common = texture(n, 70, 240)
        left = texture(n, 70, 240)
        right = texture(n, 70, 240)
        bed = np.column_stack((
            .9*common + .1*left,
            .9*common + .1*right,
        ))
        return fade(level(bed, -55), 1.5).astype(np.float32)

    common = level(texture(n, 85, 400), -47)
    air_left = level(texture(n, 300, 1600), -55)
    air_right = level(texture(n, 300, 1600), -55)
    t = np.arange(n) / SR
    tone = level(
        np.sin(2*np.pi*96*t) + .3*np.sin(2*np.pi*192*t),
        -53
    )
    bed = np.column_stack((
        common + air_left + tone,
        common + air_right + tone,
    ))
    return fade(bed, 1.5).astype(np.float32)

def add_at(target, effect, offset):
    end = min(len(target), offset + len(effect))
    if end > offset:
        target[offset:end] += effect[:end-offset]

def make_scene(dialogue, room):
    parts = [silence(1)]
    gaps = []
    cursor = SR
    beep_count = 0

    for index, row in enumerate(dialogue):
        audio = voice(row, room)
        parts.append(audio)
        cursor += len(audio)

        next_role = (
            dialogue[index+1]["role"] if index+1 < len(dialogue) else None
        )
        end_of_haven_turn = row["role"] == "haven" and next_role != "haven"
        pause = silence(.7 if not end_of_haven_turn else .9)
        if end_of_haven_turn:
            beep = soft_tone(880, .10, -35, .035)
            add_at(pause, beep, round(.12*SR))
            beep_count += 1
        else:
            gaps.append(cursor)

        parts.append(pause)
        cursor += len(pause)

    parts.append(silence(1))
    scene = np.concatenate(parts)
    scene += ambience(len(scene), room)

    if room == "operations":
        # Sparse effects placed in dialogue gaps.
        if gaps:
            for offset in (gaps[0], gaps[-1]):
                click = texture(round(.045*SR), 700, 3200)
                click = position(level(fade(click, .012), -43), -.08)
                add_at(scene, click, offset + round(.12*SR))
        if len(gaps) >= 3:
            chime = np.concatenate((
                soft_tone(620, .16, -42, .12),
                silence(.045),
                soft_tone(460, .20, -42, .12),
            ))
            add_at(scene, chime, gaps[len(gaps)//2] + round(.08*SR))

    return scene, beep_count

quarters_rows = [
    find("captain", "We have a little time"),
    find("elena", "Now I understand why"),
    find("captain", "The channel is ready"),
]

operations_rows = [
    find("ship", "Navigation report ready"),
    find("chase", "That is my route check"),
    find("elena", "We will let you"),
    find("chase", "I will join the observation"),
    find("haven", "Haven to Asterion"),
    find("elena", "Their voice is coming"),
    find("captain", "Asterion to Haven"),
    find("ship", "Reply ready"),
    find("haven", "We hear you clearly"),
    find("captain", "We can do that"),
    find("haven", "Then we will make room"),
    find("ship", "Connection confirmed"),
    find("elena", "Chase had a picture"),
]

quarters, _ = make_scene(quarters_rows, "quarters")
operations, beeps = make_scene(operations_rows, "operations")

# Apply the same gain to both rooms to preserve their relative levels.
peak = max(np.max(np.abs(quarters)), np.max(np.abs(operations)))
gain = min(1., 10**(-1/20)/max(float(peak), 1e-9))
quarters *= gain
operations *= gain
combined = np.concatenate((quarters, silence(3), operations))

if not np.isfinite(combined).all():
    raise RuntimeError("Invalid mixed samples.")

sf.write(OUT/"captains-quarters.wav", quarters, SR, subtype="PCM_16")
sf.write(OUT/"signal-operations.wav", operations, SR, subtype="PCM_16")
sf.write(OUT/"room-preview-stereo.wav", combined, SR, subtype="PCM_16")
sf.write(
    OUT/"room-preview-mono.wav",
    combined.mean(axis=1), SR, subtype="PCM_16"
)

duration = len(combined)/SR
report = [
    "SUCCESS: room and comms preview generated.",
    "First scene: captain's quarters, quiet ventilation only.",
    "Three seconds of silence separate the scenes.",
    "Second scene: Signal Operations, quiet propulsion and sparse effects.",
    f"Haven end-of-transmission beeps: {beeps}",
    f"Duration: {int(duration//60)}m {int(duration%60):02d}s",
    f"Peak: {20*np.log10(max(float(np.max(np.abs(combined))), 1e-12)):.1f} dBFS",
    "Dialogue excerpts are for sound comparison, not a revised story sequence.",
    "Listening review remains necessary.",
    f"Output folder: {OUT}",
]
(OUT/"report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report), flush=True)
