from pathlib import Path
from itertools import groupby
import json

root = Path.cwd()
out = root/"dvd/full-build"
out.mkdir(parents=True, exist_ok=True)
domains = {
    "view": ["planet", "stars"],
    "conversation": ["visit", "picture"],
    "feature": ["edge", "cloud", "pair", "group"],
    "message": ["detail", "discovery"],
    "farewell": ["thanks", "evening"],
    "earth": ["ocean", "land"],
    "planet_visit": ["mars", "saturn"],
    "galaxy_shape": ["spiral", "elliptical"],
    "web_region": ["strand", "void"],
}
labels = {
    "planet":"Blue planet", "stars":"Star field",
    "visit":"Ask about the observatory visit", "picture":"Ask about the picture",
    "edge":"Bright edge", "cloud":"Cloud bands",
    "pair":"Bright pair", "group":"Wider group",
    "detail":"Invite Haven to look closely",
    "discovery":"Ask Haven what they notice",
    "thanks":"Thank Haven", "evening":"Wish Haven a good evening",
    "ocean":"Ocean", "land":"Land", "mars":"Mars", "saturn":"Saturn",
    "spiral":"Spiral galaxy", "elliptical":"Elliptical galaxy",
    "strand":"Follow a filament", "void":"Look into a void",
}
lookup = {tag: name for name, tags in domains.items() for tag in tags}
nodes, chapters = {}, []
sources, represented = set(), set()

def new(kind, **data):
    key = f"n{len(nodes)+1:04d}"
    nodes[key] = {"kind":kind, **data}
    return key

def connect(exits, target):
    for key in exits:
        nodes[key]["next"] = target

def audio(row):
    p = Path(row["processed_file"])
    if not p.is_absolute():
        p = root/p
    if not p.is_file():
        raise RuntimeError(f"Missing audio: {p}")
    return str(p)

def chain(rows):
    first, exits = None, []
    for row in rows:
        key = new("dialogue", source=row["_source"], role=row["role"],
                  text=row["text"], tag=row["tag"], audio=audio(row), next=None)
        represented.add(row["_source"])
        if first is None:
            first = key
        connect(exits, key)
        exits = [key]
    return first, exits

def category(row):
    return "all" if row["tag"] == "all" else lookup[row["tag"]]

start, pending = None, []
for set_number, name in enumerate(
    ("mission-set-one","mission-set-two","mission-set-three"), 1
):
    rows = json.loads(
        (root/"outputs/production-audio-v1"/name/"manifest.json").read_text()
    )
    for i, row in enumerate(rows):
        row["_source"] = f"{name}:{i}"
        sources.add(row["_source"])
    for episode in range(1,6):
        selected = [r for r in rows if r["episode"] == episode]
        if not selected:
            raise RuntimeError(f"Empty episode: {name}/{episode}")
        first, seen = None, set()
        for domain, group in groupby(selected, key=category):
            batch = list(group)
            if domain == "all":
                entry, exits = chain(batch)
            else:
                choose = domain not in seen and (
                    domain not in {"view","feature","message"}
                    or (domain == "view" and set_number == 1 and episode in (1,3))
                    or (domain in {"feature","message"}
                        and set_number == 1 and episode == 4)
                )
                variable = domain if set_number == 1 else f"set{set_number}_{domain}"
                entry = new("choice" if choose else "remembered_choice",
                            variable=variable, options={})
                if choose and domain == "view":
                    nodes[entry]["clear"] = ["feature"]
                if domain == "feature":
                    nodes[entry]["allowed_by_view"] = {
                        "planet":["edge","cloud"], "stars":["pair","group"]
                    }
                exits = []
                for tag in domains[domain]:
                    branch = [r for r in batch if r["tag"] == tag]
                    if not branch:
                        continue
                    cues = []
                    if set_number == 1 and episode == 1 and domain == "view" and choose:
                        cues = [r for r in branch
                                if "press now to choose" in r["text"].lower()]
                        branch = [r for r in branch if r not in cues]
                    cue_data = []
                    for cue in cues:
                        cue_data.append({"source":cue["_source"],
                                         "text":cue["text"], "audio":audio(cue)})
                        represented.add(cue["_source"])
                    if not branch:
                        raise RuntimeError(f"Empty response: {domain}/{tag}")
                    target, ends = chain(branch)
                    nodes[entry]["options"][tag] = {
                        "label":labels[tag], "target":target, "choice_audio":cue_data
                    }
                    exits.extend(ends)
                seen.add(domain)
            if start is None:
                start = entry
            if first is None:
                first = entry
            connect(pending, entry)
            pending = exits
        chapters.append({"set":set_number, "episode":episode, "entry":first,
                         "note":"Direct chapter entry requires inherited story state."})

connect(pending, new("end"))
if sources != represented:
    raise RuntimeError("Some dialogue was omitted.")

print("Checking every complete route...", flush=True)
stack, reached, routes = [(start, {}, 0)], set(), 0
while stack:
    key, state, steps = stack.pop()
    if steps > len(nodes):
        raise RuntimeError("Unexpected story cycle.")
    n = nodes[key]
    reached.add(key)
    if n["kind"] == "end":
        routes += 1
        continue
    if n["kind"] == "dialogue":
        if n["next"] not in nodes:
            raise RuntimeError(f"Broken link: {key}")
        stack.append((n["next"], state, steps+1))
        continue
    allowed = list(n["options"])
    if "allowed_by_view" in n:
        view = state.get("view")
        if view not in n["allowed_by_view"]:
            raise RuntimeError("Close-up reached without a selected view.")
        allowed = [t for t in allowed if t in n["allowed_by_view"][view]]
    if n["kind"] == "remembered_choice":
        tag = state.get(n["variable"])
        if tag not in allowed:
            raise RuntimeError(f"Invalid remembered choice at {key}: {tag}")
        allowed = [tag]
    if not allowed:
        raise RuntimeError(f"No available choice at {key}")
    for tag in allowed:
        updated = dict(state)
        if n["kind"] == "choice":
            updated[n["variable"]] = tag
            for clear in n.get("clear", []):
                updated.pop(clear, None)
        target = n["options"][tag]["target"]
        if target not in nodes:
            raise RuntimeError(f"Broken choice at {key}")
        stack.append((target, updated, steps+1))
if reached != set(nodes):
    raise RuntimeError("Some story nodes are unreachable.")

graph = {
    "version":1, "start":start, "chapters":chapters, "nodes":nodes,
    "interaction":{
        "ordinary_scene":"Hold for OK after playback.",
        "choice":"Cycle eligible options; OK selects the displayed option.",
        "choice_timing":"Finish option narration before cycling.",
        "button_guard_seconds":1.0
    },
    "status":"Validated story graph; DVD menu compilation remains."
}
(out/"branch-map.json").write_text(
    json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8"
)
report = [
    "SUCCESS: fifteen-episode branch map validated.",
    f"Dialogue clips preserved: {len(sources)}",
    f"Story nodes: {len(nodes)}",
    f"Choice points: {sum(n['kind']=='choice' for n in nodes.values())}",
    f"Complete routes checked: {routes}",
    "All nodes reachable; all audio files present.",
    "Selected view, close-up and Haven message stay consistent.",
    "Recordings unchanged. No disc rebuilt or burned.",
    f"Saved: {out/'branch-map.json'}",
]
(out/"branch-report.txt").write_text("\n".join(report), encoding="utf-8")
print("\n".join(report), flush=True)
