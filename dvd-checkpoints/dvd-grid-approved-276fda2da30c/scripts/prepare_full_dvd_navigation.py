import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path.cwd()
BUILD = ROOT / "dvd/full-build"
OUT = BUILD / "navigation-preparation-v1"
OUT.mkdir(parents=True, exist_ok=True)
graph = json.loads((BUILD / "branch-map.json").read_text())
nodes = graph["nodes"]
chapters = graph["chapters"]

def number(key):
    match = re.fullmatch(r"n(\d+)", key)
    if not match:
        raise RuntimeError(f"Unexpected node identifier: {key}")
    return int(match.group(1))

chapters = sorted(chapters, key=lambda c: number(c["entry"]))
if len(chapters) != 15:
    raise RuntimeError("Expected fifteen chapters.")

starts = [number(c["entry"]) for c in chapters]
if starts != sorted(set(starts)):
    raise RuntimeError("Chapter entries must be distinct and ordered.")

owner = {}
for key in nodes:
    candidates = [i for i, start in enumerate(starts)
                  if start <= number(key)]
    if not candidates:
        raise RuntimeError(f"Node precedes first chapter: {key}")
    owner[key] = max(candidates) + 1

variables = sorted({
    n["variable"] for n in nodes.values()
    if n["kind"] in ("choice", "remembered_choice")
})
if len(variables) > 13:
    raise RuntimeError("Too many story variables for DVD registers.")
registers = {name: f"g{i}" for i, name in enumerate(variables)}
codes = {}
for name in variables:
    values = sorted({
        value for n in nodes.values()
        if n.get("variable") == name
        for value in n["options"]
    })
    codes[name] = {value: i + 1 for i, value in enumerate(values)}

# Each ordinary scene gets a menu. A choice gets one menu per option.
menus = {i: [] for i in range(1, 16)}
location = {}
option_location = {}

for key in sorted(nodes, key=number):
    node = nodes[key]
    chapter = owner[key]
    if node["kind"] == "choice":
        options = list(node["options"])
        if not options:
            raise RuntimeError(f"Empty choice: {key}")
        for value in options:
            entry = {
                "node": key, "kind": "choice",
                "option": value, "chapter": chapter,
                "menu": len(menus[chapter]) + 1,
            }
            menus[chapter].append(entry)
            option_location[key, value] = (chapter, entry["menu"])
        location[key] = option_location[key, options[0]]
    else:
        entry = {
            "node": key, "kind": node["kind"],
            "chapter": chapter, "menu": len(menus[chapter]) + 1,
        }
        menus[chapter].append(entry)
        location[key] = (chapter, entry["menu"])

def jump_to(destination, current):
    chapter, menu = destination
    if chapter == current:
        return f"jump menu {menu};"
    return f"jump titleset {chapter} menu {menu};"

def jump(key, current):
    if key not in location:
        raise RuntimeError(f"Unknown destination: {key}")
    return jump_to(location[key], current)

def command(parent, tag, value, **attrs):
    ET.SubElement(parent, tag, attrs).text = value

def formats(parent, menu=False):
    ET.SubElement(parent, "video", format="ntsc", aspect="16:9",
                  resolution="720x480", widescreen="nopanscan")
    ET.SubElement(parent, "audio", format="ac3", channels="2",
                  samplerate="48khz", lang="en")
    if menu:
        sub = ET.SubElement(parent, "subpicture", lang="en")
        ET.SubElement(sub, "stream", mode="widescreen", id="0")
        ET.SubElement(sub, "stream", mode="letterbox", id="1")

reset = " ".join(f"{reg} = 0;" for reg in registers.values())
root = ET.Element("dvdauthor", dest="disc", jumppad="yes")
vmgm = ET.SubElement(root, "vmgm")
command(vmgm, "fpc", "jump vmgm menu 1;")
vmmenus = ET.SubElement(vmgm, "menus", lang="en")
formats(vmmenus, True)
welcome = ET.SubElement(vmmenus, "pgc", entry="title")
command(welcome, "pre", reset + " button = 1024;")
ET.SubElement(welcome, "vob", file="media/welcome.mpg", pause="inf")
command(welcome, "button", jump(graph["start"], 0), name="continue")
command(welcome, "post", "jump menu 1;")

render = [{
    "kind": "welcome", "media": "media/welcome.mpg",
    "title": "Rift Signal", "action": "JOIN YOUR CREW",
    "hold_after_playback": True,
}]
dispatches = 0

for chapter, entries in menus.items():
    ts = ET.SubElement(root, "titleset")
    container = ET.SubElement(ts, "menus", lang="en")
    formats(container, True)

    for entry in entries:
        key = entry["node"]
        node = nodes[key]
        kind = node["kind"]
        pgc = ET.SubElement(
            container, "pgc",
            **({"entry": "root"} if entry["menu"] == 1 else {})
        )
        pre = ["button = 1024;"]

        if kind == "remembered_choice":
            variable = node["variable"]
            for value, option in node["options"].items():
                pre.append(
                    f"if ({registers[variable]} == "
                    f"{codes[variable][value]}) "
                    + jump(option["target"], chapter)
                )
            # Missing state returns to the beginning instead of
            # silently choosing a story branch.
            pre.append("jump vmgm menu 1;")
            command(pgc, "pre", " ".join(pre))
            dispatches += 1
            continue

        description = dict(entry)
        description["set"] = chapters[chapter - 1]["set"]
        description["episode"] = chapters[chapter - 1]["episode"]
        suffix = "-" + entry["option"] if kind == "choice" else ""
        media = f"media/{key}{suffix}.mpg"
        description["media"] = media

        if kind == "choice":
            value = entry["option"]
            variable = node["variable"]
            option = node["options"][value]
            values = list(node["options"])
            following = values[(values.index(value) + 1) % len(values)]
            cycle = jump_to(option_location[key, following], chapter)

            allowed = node.get("allowed_by_view")
            if allowed:
                if "view" not in registers:
                    raise RuntimeError("Feature choice has no view state.")
                eligible = [v for v, choices in allowed.items()
                            if value in choices]
                if not eligible:
                    raise RuntimeError(f"Ineligible option: {key}/{value}")
                condition = " || ".join(
                    f"{registers['view']} == {codes['view'][v]}"
                    for v in eligible
                )
                pre.append(f"if (!({condition})) {{ {cycle} }}")

            action = [
                f"{registers[variable]} = {codes[variable][value]};"
            ]
            for cleared in node.get("clear", []):
                action.append(f"{registers[cleared]} = 0;")
            action.append(jump(option["target"], chapter))
            button = " ".join(action)
            post = cycle
            description.update(
                label=option["label"],
                choice_audio=option.get("choice_audio", []),
                hold_after_playback=False,
                rendering_note=(
                    "Speak the option and allow selection time before "
                    "cycling. Do not substitute a silent timed label."
                ),
            )
        elif kind == "dialogue":
            audio = Path(node["audio"])
            if not audio.is_file():
                raise RuntimeError(f"Missing processed audio: {audio}")
            button = jump(node["next"], chapter)
            post = jump(key, chapter)
            description.update(
                audio=str(audio), role=node["role"],
                text=node["text"], tag=node.get("tag", "all"),
                source=node.get("source"),
                hold_after_playback=True,
            )
        elif kind == "end":
            button = "jump vmgm menu 1;"
            post = jump(key, chapter)
            description.update(
                title="Your mission is complete",
                action="START AGAIN", hold_after_playback=True,
            )
        else:
            raise RuntimeError(f"Unsupported node kind: {kind}")

        command(pgc, "pre", " ".join(pre))
        attrs = {"file": media}
        if description["hold_after_playback"]:
            attrs["pause"] = "inf"
        ET.SubElement(pgc, "vob", attrs)
        command(pgc, "button", button, name="continue")
        command(pgc, "post", post)
        render.append(description)

    titles = ET.SubElement(ts, "titles")
    formats(titles)
    pgc = ET.SubElement(titles, "pgc")
    ET.SubElement(pgc, "vob", file="media/title-return.mpg")
    command(pgc, "post", "call menu entry root;")

ET.indent(root, space="  ")
xml_path = OUT / "dvdauthor.xml"
ET.ElementTree(root).write(
    xml_path, encoding="utf-8", xml_declaration=True
)
ET.parse(xml_path)

plan = {
    "status": "Navigation prepared; media rendering and authoring pending.",
    "registers": registers,
    "value_codes": codes,
    "chapters": chapters,
    "node_locations": location,
    "render": render,
    "button_guard_seconds": 1.0,
    "button_coordinates": {
        "widescreen": [45, 388, 675, 432],
        "letterbox": [45, 352, 675, 384],
    },
    "requirements": [
        "Apply both widescreen and letterbox button overlays.",
        "Use the approved processed voices and quiet room ambience.",
        "Complete and review scene artwork before final rendering.",
        "Generate spoken prompts for choices lacking recorded prompts.",
        "Encode DVD-compliant MPEG-2 with stereo AC-3.",
        "Run dvdauthor to verify DVD command compilation.",
        "Test remembered choices and cycling on a physical player.",
    ],
}
(OUT / "dvd-menu-plan.json").write_text(
    json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
report = "\n".join([
    "SUCCESS: full DVD navigation preparation completed.",
    f"Episode sections: {len(chapters)}",
    f"Story variables allocated: {len(registers)}",
    f"Remembered-choice dispatch menus: {dispatches}",
    f"Visual menus to render, including welcome: {len(render)}",
    "Branch destinations resolved; XML is well formed.",
    "DVD command compilation has not yet been tested.",
    "Next: scene artwork, spoken choice prompts, and media rendering.",
    "No recordings changed. No ISO built. No disc burned.",
    f"Saved: {OUT}",
]) + "\n"
(OUT / "preparation-report.txt").write_text(report, encoding="utf-8")
print(report)
