import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path.cwd()
OUT = ROOT / "outputs/four-rooms-preview"
OUT.mkdir(parents=True, exist_ok=True)
SR = 24000
rng = np.random.default_rng(2044)
rows = json.loads(
    (ROOT/"outputs/mission-set-one/manifest.json").read_text()
)

def pick(role, start):
    matches = [
        r for r in rows
        if r["episode"] == 2 and r["role"] == role
        and r["text"].startswith(start)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Cannot identify dialogue: {start}")
    return matches[0]

def filt(x, frequency, kind):
    return sosfilt(
        butter(2, frequency, btype=kind, fs=SR, output="sos"), x
    ).astype(np.float32)

def rms(x):
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))

def set_level(x, db):
    return x * (10**(db/20) / max(rms(x), 1e-9))

def fade(x, seconds):
    x = x.copy()
    n = min(round(seconds*SR), len(x)//2)
    if n:
        shape = (n,) + (1,)*(x.ndim-1)
        x[:n] *= np.linspace(0, 1, n).reshape(shape)
        x[-n:] *= np.linspace(1, 0, n).reshape(shape)
    return x

def stereo(x, pan=0):
    return np.column_stack((x*(1-pan), x*(1+pan))).astype(np.float32)

def quiet(seconds):
    return np.zeros((round(seconds*SR), 2), dtype=np.float32)

def noise(n, low, high):
    x = rng.standard_normal(n).astype(np.float32)
    return filt(filt(x, low, "highpass"), high, "lowpass")

def tone(hz, seconds, db, pan=0):
    t = np.arange(round(seconds*SR))/SR
    wave = fade(np.sin(2*np.pi*hz*t).astype(np.float32), .025)
    return stereo(set_level(wave, db), pan)

def add(target, effect, offset):
    end = min(len(target), offset + len(effect))
    if end > offset:
        target[offset:end] += effect[:end-offset]

def environment(n, room):
    t = np.arange(n)/SR
    if room == "quarters":
        # Very quiet, low ventilation. No pitched propulsion.
        common = set_level(noise(n, 65, 210), -61)
        detail = set_level(noise(n, 100, 260), -70)
        bed = np.column_stack((common + detail, common))
    elif room == "operations":
        # Low equipment texture, distinct from the captain's room.
        common = set_level(noise(n, 110, 420), -59)
        equipment = set_level(
            np.sin(2*np.pi*180*t) + .2*np.sin(2*np.pi*270*t), -66
        )
        bed = np.column_stack((common + equipment, common + .9*equipment))
    elif room == "cockpit":
        # Smooth low propulsion, without high-frequency air hiss.
        common = set_level(noise(n, 55, 170), -59)
        engine = set_level(
            np.sin(2*np.pi*82*t) + .22*np.sin(2*np.pi*164*t), -64
        )
        bed = np.column_stack((common + .9*engine, common + engine))
    else:
        raise ValueError(room)
    return fade(bed.astype(np.float32), 1.3)

PAN = {
    "captain": -.10,
    "elena": .06,
    "chase": .10,
    "ship": .015,
    "haven": -.025,
}

def process_voice(row):
    path = Path(row["file"])
    if not path.is_absolute():
        path = ROOT/path
    x, rate = sf.read(path, dtype="float32")
    if rate != SR or x.ndim != 1 or not np.isfinite(x).all():
        raise RuntimeError(f"Unexpected source audio: {path}")

    role = row["role"]
    x = filt(x, 65, "highpass")

    if role == "ship":
        # Mostly original speech with a small electronic modulation.
        # Full bandwidth distinguishes it from Haven's comms filter.
        t = np.arange(len(x))/SR
        electronic = x * np.cos(2*np.pi*72*t)
        x = .90*x + .10*electronic
        presence = x - filt(x, 1600, "lowpass")
        x = x + .025*presence
    elif role == "haven":
        # Human voice over a clean communications channel.
        x = filt(filt(x, 220, "highpass"), 4800, "lowpass")
    elif role == "captain":
        x = x + .055*filt(x, 420, "lowpass")
    elif role == "chase":
        x = .97*x + .03*filt(x, 2500, "lowpass")

    x *= np.clip(10**(-23/20)/max(rms(x), 1e-9), .5, 2.)
    mixed = stereo(x, PAN[role])

    # Tiny local reflections; direct voice is never delayed or inverted.
    if role not in {"ship", "haven"}:
        amount = {"captain": .006, "elena": .011, "chase": .017}[role]
        reflected = filt(x, 2200, "lowpass")
        for channel, ms in ((0, 17), (1, 25)):
            delay = round(ms*SR/1000)
            if delay < len(x):
                mixed[delay:, channel] += amount*reflected[:-delay]

    if role == "haven":
        # Barely audible remote station ventilation, present only
        # while the communications channel carries Haven's voice.
        remote = set_level(noise(len(x), 170, 600), -65)
        mixed += stereo(fade(remote, .15), PAN["haven"])
    return mixed

def build(dialogue, room, effects=False):
    parts = [quiet(1)]
    cursor = SR
    ordinary_gaps = []
    for i, row in enumerate(dialogue):
        audio = process_voice(row)
        parts.append(audio)
        cursor += len(audio)

        next_role = dialogue[i+1]["role"] if i+1 < len(dialogue) else None
        end_transmission = row["role"] == "haven" and next_role != "haven"
        gap = quiet(.8)

        if end_transmission:
            add(gap, tone(820, .09, -38, -.025), round(.12*SR))
        else:
            ordinary_gaps.append(cursor)

        parts.append(gap)
        cursor += len(gap)

    parts.append(quiet(1))
    result = np.concatenate(parts)
    result += environment(len(result), room)

    if effects and ordinary_gaps:
        # One quiet console click and one distant two-note door cue.
        click = fade(noise(round(.045*SR), 450, 1800), .012)
        add(
            result, stereo(set_level(click, -47), .08),
            ordinary_gaps[0] + round(.12*SR)
        )
        if len(ordinary_gaps) >= 3:
            door = np.concatenate((
                tone(520, .14, -47, .12),
                quiet(.045),
                tone(390, .18, -47, .12),
            ))
            add(
                result, door,
                ordinary_gaps[len(ordinary_gaps)//2] + round(.1*SR)
            )
    return result

scenes = [
    (
        "01-captains-quarters",
        build([
            pick("captain", "We have a little time"),
            pick("captain", "The channel is ready"),
        ], "quarters")
    ),
    (
        "02-signal-operations",
        build([
            pick("ship", "Haven research station"),
            pick("elena", "Now I understand why"),
            pick("elena", "What did your sister"),
            pick("elena", "What do you like"),
            pick("ship", "Navigation report ready"),
            pick("elena", "We will let you"),
        ], "operations", effects=True)
    ),
    (
        "03-cockpit",
        build([
            pick("chase", "Hello, Signal Operations"),
            pick("chase", "My sister sent it"),
            pick("chase", "Of course"),
            pick("chase", "I will join the observation"),
        ], "cockpit")
    ),
    (
        "04-haven-comms",
        build([
            pick("haven", "Haven to Asterion"),
            pick("elena", "Their voice is coming"),
            pick("ship", "Reply ready"),
            pick("haven", "We hear you clearly"),
            pick("haven", "Then we will make room"),
            pick("ship", "Connection confirmed"),
        ], "operations")
    ),
]

peak = max(float(np.max(np.abs(audio))) for _, audio in scenes)
gain = min(1., 10**(-1/20)/max(peak, 1e-9))
combined = []
report = ["SUCCESS: four-room sound preview generated."]

for i, (name, audio) in enumerate(scenes):
    audio *= gain
    if not np.isfinite(audio).all():
        raise RuntimeError(f"Invalid samples: {name}")
    sf.write(OUT/f"{name}.wav", audio, SR, subtype="PCM_16")
    combined.append(audio)
    if i+1 < len(scenes):
        combined.append(quiet(3))
    report.append(f"{name}: {len(audio)/SR:.1f} seconds")

mix = np.concatenate(combined)
sf.write(OUT/"four-rooms-stereo.wav", mix, SR, subtype="PCM_16")
sf.write(
    OUT/"four-rooms-mono.wav",
    mix.mean(axis=1), SR, subtype="PCM_16"
)
seconds = len(mix)/SR
report.extend([
    f"Total: {int(seconds//60)}m {int(seconds%60):02d}s",
    f"Peak: {20*np.log10(max(float(np.max(np.abs(mix))), 1e-12)):.1f} dBFS",
    "Computer: light electronic texture; original speech timing retained.",
    "Haven: filtered human voice, remote room tone, transmission-end beep.",
    "Three-second silence separates room comparisons.",
    "Original dialogue files unchanged. Listening review required.",
    f"Output folder: {OUT}",
])
(OUT/"report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report), flush=True)
