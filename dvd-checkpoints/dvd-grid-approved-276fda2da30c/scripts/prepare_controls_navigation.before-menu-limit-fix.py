import copy
import itertools
import json
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

ROOT = Path.cwd()
BASE = ROOT / "dvd/full-build"
SOURCE = BASE / "hud-draft-v3"
OUT = BASE / "controls-navigation-v1"
OUT.mkdir(parents=True, exist_ok=True)

plan = json.loads(
    (BASE/"navigation-preparation-v1/dvd-menu-plan.json").read_text()
)
graph = json.loads((BASE/"branch-map.json").read_text())
nodes = graph["nodes"]
registers = plan["registers"]
codes = plan["value_codes"]
variables = sorted(registers, key=lambda v: int(registers[v][1:]))

assert len(variables) == 9, "Unexpected story register count."
assert set(registers.values()) == {f"g{i}" for i in range(9)}
radices = [max(codes[v].values()) + 1 for v in variables]
capacity = 1
for radix in radices:
    capacity *= radix
assert capacity <= 65536, "Bookmark state does not fit one register."

def pack(state):
    result = 0
    for value, radix in zip(state, radices):
        result = result * radix + value
    return result

def unpack(value):
    result = []
    for radix in reversed(radices):
        result.append(value % radix)
        value //= radix
    return tuple(reversed(result))

for state in itertools.product(*(range(r) for r in radices)):
    assert unpack(pack(state)) == state
print(f"Bookmark packing checked: {capacity} story states.", flush=True)

def set_story(state):
    return " ".join(
        f"{registers[v]} = {value};"
        for v, value in zip(variables, state)
    )

pack_commands = ["g11 = 0;"]
for variable, radix in zip(variables, radices):
    pack_commands += [
        f"g11 = g11 * {radix};",
        f"g11 = g11 + {registers[variable]};",
    ]

restore_commands = ["g12 = g11;"]
for variable, radix in reversed(list(zip(variables, radices))):
    restore_commands += [
        f"{registers[variable]} = g12;",
        f"{registers[variable]} = {registers[variable]} % {radix};",
        f"g12 = g12 / {radix};",
    ]

# Find an actually reachable story state for each scene.
# Direct scene selection loads that matching route.
initial = (0,) * len(variables)
queue = deque([(graph["start"], initial)])
visited = set()
canonical = {}

def eligible(node, option, state):
    allowed = node.get("allowed_by_view")
    if not allowed:
        return True
    view_value = state[variables.index("view")]
    view_name = next(
        (name for name, value in codes["view"].items()
         if value == view_value), None
    )
    return option in allowed.get(view_name, [])

while queue:
    node_id, state = queue.popleft()
    key = (node_id, state)
    if key in visited:
        continue
    visited.add(key)
    canonical.setdefault(node_id, state)
    node = nodes[node_id]
    kind = node["kind"]

    if kind == "dialogue":
        queue.append((node["next"], state))
    elif kind in ("choice", "remembered_choice"):
        variable = node["variable"]
        index = variables.index(variable)
        for option, detail in node["options"].items():
            if not eligible(node, option, state):
                continue
            value = codes[variable][option]
            if kind == "remembered_choice":
                if state[index] == value:
                    queue.append((detail["target"], state))
            else:
                changed = list(state)
                changed[index] = value
                for cleared in node.get("clear", []):
                    changed[variables.index(cleared)] = 0
                queue.append((detail["target"], tuple(changed)))

dialogue = [r for r in plan["render"] if r["kind"] == "dialogue"]
assert all(r["node"] in canonical for r in dialogue), (
    "Some scene-entry states could not be established."
)
print(f"Matching entry states found for {len(dialogue)} scenes.", flush=True)

tree = ET.parse(SOURCE/"dvdauthor.xml")
root = tree.getroot()
assert root.get("jumppad") == "yes"
vmgm = root.find("vmgm")
vm = vmgm.find("menus")
sets = root.findall("titleset")
assert len(sets) == 15
groups = {i: ts.find("menus") for i, ts in enumerate(sets, 1)}
original_pgcs = {i: group.findall("pgc")[:] for i, group in groups.items()}
original_render_count = len(plan["render"])
new_screens = []

def text(parent, tag, value):
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    child.text = value
    return child

def allocate(group, pre="", button=None, post=None, screen=None):
    number = len(group.findall("pgc")) + 1
    pgc = ET.SubElement(group, "pgc")
    ET.SubElement(pgc, "pre").text = pre or "button = 1024;"
    if screen is not None:
        filename = f"new-media/{screen['id']}.mpg"
        ET.SubElement(pgc, "vob", file=filename)
        ET.SubElement(pgc, "button", name="continue").text = button or ""
        ET.SubElement(pgc, "post").text = post or ""
        screen["media"] = filename
        new_screens.append(screen)
    return number, pgc

# g9: current scene; g10: bookmarked scene; g11: saved story state.
# g12: restoration scratch. Jumppad registers g13–g15 remain untouched.
scene_ids = {
    row["node"]: number for number, row in enumerate(dialogue, 1)
}
by_chapter = {
    chapter: [r for r in dialogue if int(r["chapter"]) == chapter]
    for chapter in groups
}
return_dispatch = {}
resume_dispatch = {}
scene_menus = {}

for chapter, group in groups.items():
    return_dispatch[chapter] = allocate(group)[0]
    resume_dispatch[chapter] = allocate(group)[0]

# VMGM helpers and menu options are allocated before links are written.
hub_items = [("return", "Return to current scene"),
             ("resume", "Resume session bookmark")]
hub_items += [
    (f"episode-{i}", f"Set {c['set']}, episode {c['episode']}")
    for i, c in enumerate(plan["chapters"], 1)
]
hub = []
for key, label in hub_items:
    number, pgc = allocate(
        vm, screen={"id": f"main-{key}", "kind": "main-menu",
                    "label": label, "spoken_text": label,
                    "selection_tail_seconds": 4}
    )
    hub.append((key, number, pgc))
hub_start = hub[0][1]
return_router, return_router_pgc = allocate(vm)
resume_router, resume_router_pgc = allocate(vm)
restore_menu, restore_pgc = allocate(vm)
empty_number, empty_pgc = allocate(
    vm, button=f"jump menu {hub_start};",
    post=f"jump menu {hub_start};",
    screen={
        "id": "no-bookmark", "kind": "notice",
        "label": "No session bookmark yet",
        "spoken_text": "No bookmark has been set in this session. Returning to the main menu.",
        "selection_tail_seconds": 4,
    }
)

# Initialize only when the disc starts, never on a main-menu visit.
fpc = vmgm.find("fpc")
if fpc is None:
    fpc = ET.Element("fpc")
    vmgm.insert(0, fpc)
fpc.text = " ".join(f"g{i} = 0;" for i in range(13)) + " jump vmgm menu 1;"
welcome = vm.findall("pgc")[0]
text(welcome, "pre", "button = 1024;")
text(welcome, "button", f"jump menu {hub_start};")

for chapter, group in groups.items():
    rows = by_chapter[chapter]
    local_returns = []
    local_resumes = []
    picker = []

    for row in rows:
        node_id = row["node"]
        sid = scene_ids[node_id]
        original_number = int(row["menu"])
        pgc = original_pgcs[chapter][original_number - 1]
        original_action = pgc.find("button").text
        assert len(pgc.findall("vob")) == 1
        pgc.find("vob").attrib.pop("pause", None)
        text(pgc, "pre", f"g9 = {sid}; button = 1024;")

        controls = []
        for action, label in (
            ("continue", "Continue"),
            ("main-menu", "Main menu"),
            ("bookmark", "Bookmark"),
        ):
            number, control = allocate(
                group, screen={
                    "id": f"{node_id}-control-{action}",
                    "kind": "footer-control", "node": node_id,
                    "source_media": row["media"],
                    "label": label, "spoken_text": label,
                    "selection_tail_seconds": 4,
                    "chapter": chapter,
                }
            )
            controls.append((number, control))
        first_control = controls[0][0]

        # Narration completes before footer scanning begins.
        # OK during narration retains the existing Continue behavior.
        text(pgc, "post", f"jump menu {first_control};")
        actions = [
            original_action,
            f"jump vmgm menu {hub_start};",
            " ".join(
                [f"g10 = {sid};"] + pack_commands
                + [f"jump menu {first_control};"]
            ),
        ]
        for index, (_, control) in enumerate(controls):
            text(control, "button", actions[index])
            text(control, "post",
                 f"jump menu {controls[(index + 1) % 3][0]};")

        local_returns.append(f"if (g9 == {sid}) jump menu {first_control};")
        local_resumes.append(f"if (g9 == {sid}) jump menu {original_number};")

        label = f"Scene {len(picker) + 1}: {row['role']}"
        number, choice = allocate(
            group,
            button=set_story(canonical[node_id])
                   + f" jump menu {original_number};",
            screen={
                "id": f"select-{node_id}", "kind": "scene-selection",
                "node": node_id, "chapter": chapter, "label": label,
                "excerpt": row["text"],
                "spoken_text": label + ". " + row["text"],
                "selection_tail_seconds": 4,
                "entry_state": dict(zip(variables, canonical[node_id])),
                "note": "Loads a matching route; does not overwrite the bookmark.",
            }
        )
        picker.append((number, choice))

    back_number, back_pgc = allocate(
        group, button=f"jump vmgm menu {hub_start};",
        screen={
            "id": f"episode-{chapter}-back",
            "kind": "scene-selection", "chapter": chapter,
            "label": "Back to main menu",
            "spoken_text": "Back to main menu",
            "selection_tail_seconds": 4,
        }
    )
    picker.append((back_number, back_pgc))
    scene_menus[chapter] = picker[0][0]
    for index, (_, pgc) in enumerate(picker):
        text(pgc, "post", f"jump menu {picker[(index + 1) % len(picker)][0]};")

    pgcs = group.findall("pgc")
    text(pgcs[return_dispatch[chapter] - 1], "pre",
         " ".join(local_returns) + f" jump vmgm menu {hub_start};")
    text(pgcs[resume_dispatch[chapter] - 1], "pre",
         " ".join(local_resumes) + f" jump vmgm menu {hub_start};")

for index, (key, _, pgc) in enumerate(hub):
    if key == "return":
        action = f"jump menu {return_router};"
    elif key == "resume":
        action = f"jump menu {restore_menu};"
    else:
        chapter = int(key.split("-")[1])
        action = f"jump titleset {chapter} menu {scene_menus[chapter]};"
    text(pgc, "button", action)
    text(pgc, "post", f"jump menu {hub[(index + 1) % len(hub)][1]};")

for router, dispatch in (
    (return_router_pgc, return_dispatch),
    (resume_router_pgc, resume_dispatch),
):
    commands = [f"if (g9 == 0) jump menu {hub_start};"]
    for chapter, rows in by_chapter.items():
        if rows:
            maximum = max(scene_ids[r["node"]] for r in rows)
            commands.append(
                f"if (g9 <= {maximum}) jump titleset {chapter} menu {dispatch[chapter]};"
            )
    commands.append(f"jump menu {hub_start};")
    text(router, "pre", " ".join(commands))

text(restore_pgc, "pre", " ".join(
    [f"if (g10 == 0) jump menu {empty_number};"]
    + restore_commands
    + ["g9 = g10;", f"jump menu {resume_router};"]
))

# Save the production navigation plan; new media is not rendered yet.
ET.indent(tree, space="  ")
tree.write(OUT/"navigation.xml", encoding="utf-8", xml_declaration=True)
(OUT/"new-screens.json").write_text(
    json.dumps(new_screens, indent=2), encoding="utf-8"
)
(OUT/"session-bookmark.json").write_text(json.dumps({
    "current_scene_register": "g9",
    "bookmark_scene_register": "g10",
    "bookmark_story_register": "g11",
    "scratch_register": "g12",
    "variables": variables, "radices": radices,
    "scene_ids": scene_ids,
    "persistence": "Current session only; no power-off or eject guarantee.",
    "resume_behavior": "Replay bookmarked scene with saved story choices.",
    "direct_scene_entry": "Load a canonically reachable matching story state.",
}, indent=2), encoding="utf-8")

# Compile all new commands against a known-working single-button clip.
# This produces test DVD files, not a review ISO.
test_dir = Path(tempfile.mkdtemp(prefix="compile-", dir=OUT))
test_root = copy.deepcopy(root)
disc = test_dir/"disc"
test_root.set("dest", str(disc))
placeholder = SOURCE/"media/welcome.mpg"
assert placeholder.is_file(), f"Missing test clip: {placeholder}"
for menus in test_root.iter("menus"):
    for vob in menus.iter("vob"):
        vob.set("file", str(placeholder))

test_xml = test_dir/"test.xml"
ET.indent(test_root, space="  ")
ET.ElementTree(test_root).write(
    test_xml, encoding="utf-8", xml_declaration=True
)
log = test_dir/"dvdauthor.log"
print("Compiling the scene menus, footer controls and bookmark commands...", flush=True)
with log.open("w") as output:
    result = subprocess.run(
        ["dvdauthor", "-x", str(test_xml)],
        cwd=SOURCE, env=dict(os.environ, VIDEO_FORMAT="NTSC"),
        stdout=output, stderr=subprocess.STDOUT,
    )
if result.returncode:
    print(log.read_text(errors="replace")[-7000:])
    raise RuntimeError(f"Navigation compilation failed. Full log: {log}")

required = [disc/"VIDEO_TS/VIDEO_TS.IFO"]
required += [disc/f"VIDEO_TS/VTS_{i:02d}_0.IFO" for i in range(1, 16)]
assert all(p.is_file() and p.stat().st_size for p in required)

report = [
    "SUCCESS: expanded DVD navigation commands compiled.",
    f"Episode selectors: {len(sets)}",
    f"Individual scene selectors: {len(dialogue)}",
    "Footer cycle: Continue > Main menu > Bookmark.",
    "Bookmarks preserve the scene and all nine story variables.",
    f"Bookmark packing states checked: {capacity}",
    "Direct scene entry uses a matching story route.",
    "Bookmark persistence: current session only.",
    "New screen artwork, spoken controls and playback testing remain.",
    "No review ISO created. No disc burned. Approved build unchanged.",
    f"New screen plan: {OUT/'new-screens.json'}",
    f"Compilation log: {log}",
]
(OUT/"report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n" + "\n".join(report), flush=True)
