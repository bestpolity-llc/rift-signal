import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path.cwd()
SOURCE = ROOT / "dvd/source-template-v1/rift-signal-remaster"
OUT = ROOT / "dvd/picture-test-v2"
for folder in (
    "scripts", "missions/mission-001", "dvd/menus",
    "dvd/chapters", "dvd/build/logs",
):
    (OUT/folder).mkdir(parents=True, exist_ok=True)

for name in ("author.py", "layout.py"):
    shutil.copy2(SOURCE/"scripts"/name, OUT/"scripts"/name)


import ast
author_path = OUT / "scripts/author.py"
author_tree = ast.parse(author_path.read_text())

class InvisibleButtonMasks(ast.NodeTransformer):
    def visit_Expr(self, node):
        call = node.value
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "rectangle"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "d"
        ):
            return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)

author_tree = InvisibleButtonMasks().visit(author_tree)
ast.fix_missing_locations(author_tree)
author_path.write_text(ast.unparse(author_tree) + "\n")

font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def font(size):
    return ImageFont.truetype(font_path, size)

def label(draw, text, y, size=30, color="#edf6ff"):
    draw.text((640,y), text, font=font(size), fill=color, anchor="mt")

def shell(args, name):
    log = OUT/"dvd/build/logs"/f"{name}.log"
    with log.open("w") as stream:
        result = subprocess.run(
            args, cwd=OUT,
            env=dict(os.environ, VIDEO_FORMAT="NTSC"),
            stdout=stream, stderr=subprocess.STDOUT,
        )
    if result.returncode:
        raise RuntimeError(
            log.read_text(errors="replace")[-7000:] + f"\nLog: {log}"
        )

# Square-pixel 16:9 artwork. Encoding below converts it to
# anamorphic DVD pixels while preserving the displayed proportions.
im = Image.new("RGB",(1280,720),"#061019")
d = ImageDraw.Draw(im)
label(d,"RIFT SIGNAL / PICTURE TEST",40,30,"#75d8ff")
d.ellipse((465,145,815,495),outline="#ffffff",width=9)
d.line((640,145,640,495),fill="#547080",width=2)
d.line((465,320,815,320),fill="#547080",width=2)
label(d,"This circle should look round, not wide or tall.",525,28)
d.rectangle((80,582,1200,648),outline="#68ddda",width=3)
label(d,"PRESS OK TO SEE THE CAPTAIN",598,28)
im.save(OUT/"dvd/menus/welcome.png")

# A proportional upper-body crop of the original portrait.
# No horizontal stretching, mirroring, or change to the character.
portrait_path = SOURCE/"assets/crew/captain-marcus-value.png"
with Image.open(portrait_path) as original:
    portrait = original.convert("RGB")
    portrait = portrait.crop((
        0, 0, portrait.width, round(portrait.height*.62)
    ))
    portrait.thumbnail((1120,475), Image.Resampling.LANCZOS)

im = Image.new("RGB",(1280,720),"#061019")
im.paste(portrait,((1280-portrait.width)//2,40))
d = ImageDraw.Draw(im)
label(d,"CAPTAIN MARCUS",527,30,"#75d8ff")

im.save(OUT/"dvd/menus/captain.png")

manifest = json.loads(
    (ROOT/"outputs/production-audio-v1/mission-set-one/manifest.json")
    .read_text()
)
candidates = [r for r in manifest if r["role"]=="captain"]
if not candidates:
    raise RuntimeError("No approved captain recording found.")
row = next((r for r in candidates if len(r["text"])<160),candidates[0])
audio = Path(row["processed_file"])
if not audio.is_absolute():
    audio = ROOT/audio
if not audio.is_file():
    raise RuntimeError(f"Missing captain audio: {audio}")
import soundfile as sf
duration = sf.info(audio).duration + 1.0

for scene, seconds in (("welcome",8.0),("captain",duration)):
    args = [
        "ffmpeg","-hide_banner","-y",
        "-loop","1","-framerate","30000/1001",
        "-i",str(OUT/f"dvd/menus/{scene}.png"),
    ]
    if scene=="captain":
        args += ["-i",str(audio),"-af","apad"]
    else:
        args += ["-f","lavfi","-i","anullsrc=r=48000:cl=stereo"]
    args += [
        "-t",str(seconds),
        "-vf","scale=720:480:flags=lanczos,setsar=32/27",
        "-target","ntsc-dvd","-aspect","16:9",
        "-ac","2","-ar","48000","-b:a","192k",
        str(OUT/f"dvd/menus/{scene}.mpg"),
    ]
    print(f"Encoding {scene}...",flush=True)
    shell(args,scene)

shell([
    "ffmpeg","-hide_banner","-y",
    "-f","lavfi","-i","color=c=black:s=720x480:r=30000/1001",
    "-f","lavfi","-i","anullsrc=r=48000:cl=stereo",
    "-t","1","-vf","setsar=32/27","-target","ntsc-dvd",
    "-aspect","16:9","-ac","2","-ar","48000","-b:a","192k",
    str(OUT/"dvd/chapters/title-return.mpg"),
],"dummy-title")

mission = {
    "button_guard_seconds":1.0,
    "scenes":[
        {"id":"welcome","next":"captain"},
        {"id":"captain","next":"welcome"},
    ],
}
(OUT/"missions/mission-001/mission.json").write_text(json.dumps(mission))
shell([sys.executable,str(OUT/"scripts/author.py")],"author")

print("\nENCODED VIDEO SETTINGS")
for scene in ("welcome","captain"):
    result = subprocess.run([
        "ffprobe","-v","error","-select_streams","v:0",
        "-show_entries",
        "stream=width,height,sample_aspect_ratio,display_aspect_ratio",
        "-of","json",str(OUT/f"dvd/build/muxed/{scene}.mpg"),
    ],capture_output=True,text=True,check=True)
    stream = json.loads(result.stdout)["streams"][0]
    print(scene+": "+json.dumps(stream))
    if (stream.get("width"),stream.get("height"))!=(720,480):
        raise RuntimeError("Unexpected DVD dimensions.")
    if stream.get("display_aspect_ratio")!="16:9":
        raise RuntimeError("Encoded video does not report widescreen.")

iso = OUT/"dvd/build/rift-signal-mission-001-kokoro-widescreen-ntsc.iso"
if not iso.is_file():
    raise RuntimeError("Test ISO missing.")
print("\nSUCCESS: widescreen picture test created.")
print("Circle screen checks display proportions.")
print("Captain screen uses a larger upper-body crop of the original portrait.")
print("OK moves between the two screens.")
print("On the TV, check: circle round, face natural, portrait large enough.")
print(f"ISO: {iso}")
print("Captain screen: portrait and name only; button masks transparent.")
print("No disc burned. Previous tests and recordings unchanged.")
