import hashlib
import json
import re
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

OUT = Path("outputs/mission-set-one")
CLIPS = OUT / "clips"
CLIPS.mkdir(parents=True, exist_ok=True)
RATE = 24000
CAST = {
    "ship": ("af_sarah", .92),
    "captain": ("am_michael", .91),
    "elena": ("af_heart", .90),
    "chase": ("am_fenrir", .96),
    "haven": ("af_bella", .92),
}
rows = []

# Preserve the existing First Shift dialogue from the reviewed source revision.
source_path = OUT / "first-shift-source.js"
if not source_path.exists():
    url = (
        "https://raw.githubusercontent.com/bestpolity-llc/rift-signal/"
        "75cf65a718bd844aec8b387beb50a828722b4c72/docs/play/mission.js"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "RiftSignalAudio"})
    with urllib.request.urlopen(request, timeout=60) as response:
        source = response.read().decode("utf-8")
    source_path.write_text(source, encoding="utf-8")
else:
    source = source_path.read_text(encoding="utf-8")

def field(block, name):
    match = re.search(r'\b' + name + r':\s*("(?:\\.|[^"\\])*")', block)
    if not match:
        raise ValueError(f"Missing field: {name}")
    return json.loads(match.group(1))

scenes = {}
for sid, block in re.findall(
    r'\{\s*id:\s*"([^"]+)"(.*?)\n  \}', source, re.S
):
    scenes[sid] = {
        "role": field(block, "role"),
        "text": field(block, "narration"),
    }
if len(scenes) != 22:
    raise ValueError(f"Expected 22 First Shift scenes; found {len(scenes)}")

aliases = {"mentor": "elena", "pilot": "chase"}
for sid, scene in scenes.items():
    tag = (
        "planet" if sid.startswith("planet_") or sid == "choose_planet"
        else "stars" if sid.startswith("stars_") or sid == "choose_stars"
        else "all"
    )
    rows.append({
        "episode": 1, "tag": tag,
        "role": aliases.get(scene["role"], scene["role"]),
        "text": scene["text"], "id": sid,
    })

# Fields: episode | branch | speaker | spoken dialogue.
# "all" plays on every route. Other labels select alternate passages.
SCRIPT = """
2|all|ship|Haven research station has requested an observation session. Their common-room receiver is warming up.
2|all|captain|We have a little time before they call. Chase is preparing our observation positions. Operator, check in with him while I speak with the station coordinator. Once Haven is ready, we will bring everyone onto the same channel.
2|all|chase|Hello, Signal Operations. I am just finishing the route check. You caught me moving this picture again. Every time I put it somewhere sensible, a report opens over it.
2|all|elena|I have seen that picture on your console, but I do not know the story. Where did it come from?
2|all|chase|My sister sent it. She visited an observatory and took a picture through one of its telescopes. She thought I would laugh because I spend my working day looking out into space.
2|all|elena|But you kept it.
2|all|chase|Of course. I like knowing what she could see from where she was standing.
2|all|elena|Now I understand why it stays on his console. A moment ago, I only knew it was a picture. There are a couple of things we could ask him about it.
2|all|elena|What did your sister enjoy about the visit?
2|all|elena|What do you like about the picture?
2|visit|chase|She liked the moment when the telescope came into focus. At first, she could only see a bright blur. Then the rings appeared. She said she called the person beside her over to look, because she did not want them to miss it.
2|picture|chase|I like that it is a little crooked. The planet is off to one side, and there is a dark corner where the camera did not line up. It looks like somebody taking a picture in a hurry because they were pleased with what they saw.
2|visit|elena|So part of what she enjoyed was getting to show somebody else.
2|visit|chase|Yes. And then she sent it to me, so I got a turn too.
2|picture|elena|The crooked part helps you imagine her taking it.
2|picture|chase|Exactly. A perfect picture would show me the planet. This one reminds me of her visit.
2|all|ship|Navigation report ready.
2|all|chase|That is my route check. I need to read it before we move. Thank you for asking about the picture. I enjoyed telling you.
2|all|elena|We will let you get back to it.
2|all|chase|I will join the observation channel when the captain calls. There are two good views for the operator to choose from.
2|all|haven|Haven to Asterion. Our receiver is ready. Can you hear us?
2|all|elena|Their voice is coming through clearly. Let us check that they can hear us too.
2|all|captain|Asterion to Haven. Our Signal Operator is at the station. We are preparing your observation.
2|all|ship|Reply ready to transmit.
2|all|haven|We hear you clearly. The picture you sent earlier has people wondering what else is out there. We thought we could gather by the display and look together.
2|all|captain|We can do that. Our pilot has prepared two observation positions. The operator will help choose our view.
2|all|haven|Then we will make room. Call when you are in position.
2|all|ship|Connection confirmed.
2|all|elena|Chase had a picture from someone else's window on the world. Now we are getting ready to share ours.
2|all|captain|The channel is ready and navigation has its report. That completes this part of the shift. Next, we choose where to take the Asterion.

3|all|captain|Our connection with Haven is ready. Now we need a view worth sharing. Chase has found two places where the Asterion can make an observation. We have time to hear about both. Operator, your choice will help decide what the people at Haven see when their gathering begins.
3|all|chase|I have kept the observation window covered while we travel. In a moment, I will show you our two possibilities. The ship can hold a steady position at either one. There is no wrong destination here. We are choosing what we want to spend some time noticing.
3|all|chase|Here is the planet. From this position, its curved edge runs across the window. There is a bright line where sunlight meets the atmosphere. Farther in, bands of cloud stretch over the surface. We could stay here and look at the difference between that bright edge and the clouds.
3|all|chase|Here is the open star field. With the planet out of the way, we can see lights across the whole window. Some appear close together. Others have more space around them. Two bright points make a pair near the middle. We could stay here and explore those patterns.
3|all|elena|I noticed the clouds first. Chase noticed the pair of lights. We can look at the same possibilities and want to explore different things.
3|all|chase|Both positions are ready. My job is to get us there; you can choose which view we spend time with.
3|all|elena|The planet and the star field will take turns on the display. Choose the one you want.
3|all|elena|Planet view.
3|all|elena|Star field.
3|planet|chase|Planet view selected. I will bring the bright edge and the cloud bands into our observation window.
3|stars|chase|Star field selected. I will position the ship so the pair of lights and the wider group are both in view.
3|all|captain|We have our destination. Let us prepare the ship.
3|all|ship|Observation camera secured. Communication link available. Cabin systems ready.
3|all|chase|The route is clear, and the ship is ready to move.
3|all|captain|I authorize the change of position.
3|all|elena|You have heard the reports. The crew has prepared its part. Your signal tells everyone that we are ready to take this step together.
3|all|ship|Ready signal received. Changing observation position.
3|all|chase|The movement you see is our view changing as the ship turns. We are keeping the ride gentle. I will bring us to a steady stop before we open the observation.
3|all|elena|Haven is getting its room ready while we get our window ready.
3|all|chase|We are in position. The ship is holding steady, and the camera has a clear view.
3|all|haven|We heard your arrival report. People are coming into the common room now. We have left the main display clear for your observation. Give us a call when you have something you want to share.
3|all|captain|Position confirmed. You helped choose our destination and brought the crew's preparations together.
3|all|elena|We now have a connection and a place to look. In the next episode, we will explore your view and make an observation for Haven. For now, this part of the job is complete.

4|all|captain|We have reached the place you chose. Today we will turn that view into something we can share. A useful observation does not have to explain everything outside the ship. We can notice one part, take a closer look, and tell Haven what caught our attention.
4|planet|chase|The whole planet view is on the display. The bright edge curves along one side. Cloud bands lie farther across the surface. Keeping this wider picture will help Haven see where our closer view belongs.
4|stars|chase|The whole star field is on the display. The bright pair sits near the middle. A looser group spreads across one side. Keeping this wider picture will help Haven see where our closer view belongs.
4|all|elena|We have saved the wide picture. Now we can choose a part to explore. You do not need to search for a hidden answer. The display will offer two details from your view. Pick the one you would like to hear more about, and Chase will bring it closer.
4|planet|elena|Bright edge.
4|planet|elena|Cloud bands.
4|stars|elena|Bright pair.
4|stars|elena|Wider group.
4|edge|chase|Here is the bright edge. From this angle, the light makes a thin curved line beside the darker space. The curve continues beyond our close view. In the wide picture, you can see how this small part belongs to the larger shape.
4|cloud|chase|Here are the cloud bands. Some areas look brighter and thicker than others. There are spaces between them where the surface is less covered. In the wide picture, those separate areas become a pattern stretching across a much larger part of the planet.
4|pair|chase|Here are the two bright points. On our display, they appear beside one another, with dark space between them. A picture tells us where they appear from here. It does not, by itself, tell us how close they really are to each other.
4|group|chase|Here is the wider group. The lights do not fill every part of the picture evenly. Some have neighbors nearby on the display, and some stand apart. We can describe that pattern without needing to give every point a name or count them all.
4|all|elena|Now we have two pictures with different jobs. The wide one shows where we were looking. The closer one shows what you picked out. Haven will be able to move between them, just as we did. Your choice has given the observation its own point of interest.
4|edge|elena|Does the bright edge look like that all the way around?
4|edge|chase|We cannot see the whole planet from here. We can describe this part, but we would need another view to answer that.
4|cloud|elena|Are those clouds moving?
4|cloud|chase|This picture cannot tell us. We could take another one later and compare them. For this report, we can show the pattern we see now.
4|pair|elena|Are those two lights really next to each other?
4|pair|chase|They look close together from our window. One could be much farther away. We would need more information to find out.
4|group|elena|I can almost see a shape in that group. Does it have a name?
4|group|chase|I would need to check our star chart. We can still show Haven the pattern without pretending we know its name.
4|all|elena|Then our report can include what we noticed and something we still wonder about.
4|all|elena|We can send an invitation with the pictures. One message invites Haven to look closely at your chosen detail. The other invites them to explore the whole view and find something of their own. Both fit the observation. Which invitation would you like the crew to include?
4|all|elena|Look at this detail.
4|all|elena|What do you notice?
4|all|ship|Observation report. One wide picture. One selected detail. One invitation.
4|detail|captain|Here is the view from our ship. Our Signal Operator chose this detail for a closer look. We invite you to spend a moment with it.
4|discovery|captain|Here is the view from our ship. Our Signal Operator has shared a closer look as well. What do you notice in these pictures?
4|all|captain|Report approved. You chose what to explore and how to invite Haven into the observation. We have a complete message ready to send.
4|all|elena|The pictures are saved. We do not have to do it all again. Next comes the part where the people at the other end get to respond.

5|all|haven|Haven to Asterion. Our gathering is ready. Some people are sitting close to the display, and others are farther back where they can see the whole picture. We have told them that your Signal Operator chose the observation. Whenever you are ready, we would like to see it.
5|all|elena|Everything you prepared is still here: the wide picture, the detail you chose, and your invitation. We will send them in that order. First, Haven gets to see where we were looking. Then we show what you picked out. Finally, they hear the message that goes with it.
5|all|ship|Haven connection open. Receiver check complete. Observation report available.
5|all|captain|Haven, this is the Asterion. Our Signal Operator has prepared two views for your gathering. We will begin with the wider picture.
5|all|elena|The connection is ready, and the report is ready. One press will send the first picture across.
5|planet|haven|We have the planet view. The curve reaches across our display. We can see the bright edge and the clouds together.
5|stars|haven|We have the star field. The lights spread across our display. We can see the bright pair and the wider group together.
5|all|haven|Now we know where your ship has been looking.
5|all|haven|The closer picture has arrived beside the first one. That gives us a new way to look. We can find the detail in the wide picture, then return to see it larger.
5|all|chase|That is the detail our Signal Operator selected. We kept both pictures so you could explore the connection between them.
5|detail|captain|Our Signal Operator invites you to look closely at this detail.
5|discovery|captain|Our Signal Operator asks: what do you notice in these pictures?
5|all|haven|Thank you. We can use that question here together. People may notice different things, and we have time to hear their answers.
5|all|haven|We have put the two pictures beside each other. From the back of the room, the wide view is easiest to see. Up close, the detail catches your attention. We are going to keep both.
5|all|chase|I wondered which one would work better on your display.
5|all|haven|They work together. And your invitation gives us somewhere to begin. We can carry on looking after the ship signs off.
5|all|elena|Our observation has reached its destination. Before we close the channel, you can choose our goodbye. We can thank Haven for joining us, or wish everyone a good evening at the station. There is no special answer to find. This is simply how you would like to end our visit.
5|all|elena|Thank you for joining us.
5|all|elena|Have a good evening.
5|thanks|captain|Thank you for joining us, Haven. We were glad to share the view.
5|evening|captain|Have a good evening, Haven. We hope you enjoy the pictures.
5|all|haven|And thank you, Signal Operator. Your choices brought this observation to our room. Goodbye from everyone here.
5|all|ship|Conversation complete. Closing the channel.
5|all|captain|You answered a request, checked our connection, helped choose a destination, and prepared an observation. Then you carried it through to the people waiting at Haven.
5|all|elena|That is the end of this mission set. You can leave the ship here for today. If you return, there will be other choices to try. For now, your work is complete.
"""

for number, line in enumerate(SCRIPT.strip().splitlines(), 1):
    if not line.strip():
        continue
    episode, tag, role, text = line.split("|", 3)
    rows.append({
        "episode": int(episode), "tag": tag, "role": role,
        "text": text, "id": f"line-{number:03d}",
    })

(OUT / "script.json").write_text(
    json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
)
pipeline = KPipeline(lang_code="a", device="cpu")

for index, row in enumerate(rows, 1):
    voice, speed = CAST[row["role"]]
    key = hashlib.sha256(
        json.dumps([voice, speed, row["text"]]).encode()
    ).hexdigest()[:16]
    path = CLIPS / (
        f"ep{row['episode']}-{row['id']}-{row['role']}-{key}.wav"
    )
    valid = False
    if path.exists():
        try:
            samples, rate = sf.read(path, dtype="float32")
            valid = (
                rate == RATE and samples.size > 0
                and np.isfinite(samples).all()
                and np.max(np.abs(samples)) > 0
            )
        except Exception:
            pass
    if not valid:
        print(f"[{index}/{len(rows)}] Episode {row['episode']}: "
              f"{row['role']} / {row['id']}", flush=True)
        chunks = []
        for _, _, audio in pipeline(row["text"], voice=voice, speed=speed):
            if audio is not None:
                if hasattr(audio, "detach"):
                    audio = audio.detach().cpu().numpy()
                chunks.append(np.asarray(audio, dtype=np.float32))
        if not chunks:
            raise RuntimeError(f"No audio for {row['id']}")
        samples = np.concatenate(chunks)
        if not np.isfinite(samples).all() or np.max(np.abs(samples)) == 0:
            raise RuntimeError(f"Invalid audio for {row['id']}")
        temporary = path.with_suffix(".tmp.wav")
        sf.write(temporary, samples, RATE, subtype="PCM_16")
        temporary.replace(path)
    else:
        print(f"[{index}/{len(rows)}] Reusing {path.name}", flush=True)
    row["file"] = str(path)
    row["seconds"] = len(samples) / RATE

routes = {
    "main": {"all", "visit", "planet", "edge", "detail", "thanks"},
    "alternate": {"all", "picture", "stars", "pair", "discovery", "evening"},
}
report = []
gap = np.zeros(int(RATE * .55), dtype=np.float32)
episode_gap = np.zeros(RATE * 2, dtype=np.float32)

for route, tags in routes.items():
    complete_path = OUT / f"full-listening-draft-{route}.wav"
    total_seconds = 0
    with sf.SoundFile(
        complete_path, mode="w", samplerate=RATE,
        channels=1, subtype="PCM_16"
    ) as full:
        for episode in range(1, 6):
            selected = [
                row for row in rows
                if row["episode"] == episode and row["tag"] in tags
            ]
            episode_path = OUT / f"episode-{episode:02d}-{route}.wav"
            duration = 0
            with sf.SoundFile(
                episode_path, mode="w", samplerate=RATE,
                channels=1, subtype="PCM_16"
            ) as track:
                for row in selected:
                    samples, _ = sf.read(row["file"], dtype="float32")
                    track.write(samples)
                    track.write(gap)
                    full.write(samples)
                    full.write(gap)
                    duration += len(samples)/RATE + .55
            full.write(episode_gap)
            total_seconds += duration + 2
            report.append(
                f"{route}: episode {episode}: "
                f"{int(duration//60)}m {int(duration%60):02d}s"
            )
    report.append(
        f"{route}: TOTAL {int(total_seconds//60)}m "
        f"{int(total_seconds%60):02d}s"
    )

# The remaining two detail branches are preserved individually and in an appendix.
extra_path = OUT / "additional-detail-branches.wav"
with sf.SoundFile(
    extra_path, mode="w", samplerate=RATE, channels=1, subtype="PCM_16"
) as appendix:
    for tag in ("cloud", "group"):
        for row in rows:
            if row["tag"] == tag:
                samples, _ = sf.read(row["file"], dtype="float32")
                appendix.write(samples)
                appendix.write(gap)
        appendix.write(episode_gap)

(OUT / "manifest.json").write_text(
    json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
)
report.append(f"Generated or reused {len(rows)} dialogue clips.")
report.append("Timings exclude player response delays and unvisited branches.")
report.append(f"Output folder: {OUT.resolve()}")
(OUT / "timing-report.txt").write_text("\n".join(report), encoding="utf-8")
print("\nSUCCESS\n" + "\n".join(report), flush=True)
