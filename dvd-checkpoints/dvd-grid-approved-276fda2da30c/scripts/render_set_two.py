import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

OUT = Path("outputs/mission-set-two")
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
TITLES = {
    1: "Our Home",
    2: "Earth and Its Moon",
    3: "A Star and Its Planets",
    4: "The Sun's Far Reach",
    5: "Our Place in the Milky Way",
}

SCRIPT = """
1|all|ship|Signal Operations. Observation display available. Today's assignment: Our Place in Space.
1|all|haven|Hello, Asterion. After your last observation, we kept talking about the pictures. We have a new question for your crew. Where does Earth fit into all of this? We know it is our home, but we would like to see the bigger picture.
1|all|captain|That sounds like a job for our map display. Operator, we will build Haven a picture guide, beginning at Earth and moving outward. You will help choose some of the views. At the end, we will bring the whole journey back home.
1|all|elena|This time, we are exploring a map. We are not flying these enormous distances in a few minutes. The display lets us change our viewpoint while the ship stays where it is. Think of opening a map of a town, then pulling back to see the country around it.
1|all|chase|Here is Earth. It is a planet, a large, nearly round world moving around the Sun. From this view, blue oceans cover much of its surface. There are broad areas of land and white clouds above them. Everything in this picture belongs to the same world.
1|all|elena|The room where you are listening is on that world. So are the roads outside, the places you visit, and people you have never met. A picture from far away cannot show all those details. They are still there, even when they are too small to see.
1|all|chase|Around Earth is a layer of gases called the atmosphere. That is where our air is. Clouds and weather happen within it. From the ground, the sky can seem to go on forever. From space, the atmosphere makes a thin layer around a much larger planet.
1|all|elena|We can take a closer look at the ocean or the land. Both are parts of home. The choices will take turns. Pick the view you would like to put into Haven's guide.
1|all|elena|Look at the ocean.
1|all|elena|Look at the land.
1|ocean|chase|The ocean view is selected. Water stretches across a huge part of the picture, with clouds above it. Down at the surface, there are waves, coastlines, and living things. From here, those smaller details blend into broad areas of color.
1|land|chase|The land view is selected. We can see different colors across the surface. There are mountains, plains, forests, and dry regions. The streets and buildings that seem large when we are beside them are too small to pick out in this view.
1|all|ship|Home picture saved.
1|all|captain|We have our starting point. Whatever else we discover, Earth will stay marked on our map.
1|all|elena|We do not have to leave everything familiar behind to think about space. The familiar things are already in space, with us, on Earth. Next, we will pull back just far enough to find a neighbor.

2|all|ship|Map view expanding. Earth and its Moon.
2|all|chase|There is Earth again. Beside it on our diagram is the Moon. I have enlarged both worlds so they are easy to recognize. Their sizes and the gap on this display are not shown at the same scale. In space, there is much more room between them than this little diagram suggests.
2|all|elena|We sometimes see the Moon from a window or outside during the evening. Sometimes we can see it during the day. Here on the map, it becomes a whole place, with its own surface. It is not just a light attached to Earth's sky.
2|all|chase|The Moon travels around Earth. That journey is called an orbit. Gravity helps keep the two connected. The Moon does not stay over one building or one town. It moves around our planet while Earth and the Moon travel around the Sun together.
2|all|captain|Let us bring the lunar surface closer. Operator, open the close view.
2|all|ship|Close view available.
2|all|chase|These round hollows are craters. Many formed when objects from space struck the surface. The Moon also has darker plains made from ancient lava. Through a telescope, some places look rough and crowded with craters, while other areas look smoother.
2|all|elena|A picture can make it seem as though we could reach out and touch those ridges. But we are looking across a great distance. Our display is bringing the view closer; it is not bringing the Moon closer to Earth.
2|all|haven|We have another question. Sometimes the Moon looks round, and sometimes it looks like a thin curve. Is part of it missing?
2|all|chase|No. The Moon stays a whole, nearly round world. The Sun lights roughly half of it at a time. As the Moon goes around Earth, we see different amounts of that sunlit half. Those changing views are the Moon's phases.
2|all|elena|Imagine holding a ball beside a lamp. One side catches the light. When you change where you stand, you see more or less of the bright side. The ball has not lost a piece. Your view of its light and shadow has changed.
2|all|chase|Moonlight is sunlight reflected from the Moon's surface. The Moon does not make its own sunlight. And the ordinary changes from crescent to full Moon are not Earth casting a shadow over it. Earth's shadow on the Moon is a different event, called a lunar eclipse.
2|all|ship|Earth and Moon picture ready to save.
2|all|captain|Add it to the guide. We have home, and we have our nearest large celestial neighbor.
2|all|elena|Now there is another question waiting. If sunlight lights the Moon, where does that light begin? Our next map will bring the Sun into view.

3|all|ship|Solar system map available.
3|all|captain|Our guide has reached the Sun. It is the star at the center of our solar system. Earth and the other planets orbit it. This diagram spreads the worlds out so we can identify them; it is not a photograph of the planets lined up together.
3|all|chase|The Sun makes its own light. Deep inside, nuclear reactions release energy. Some of that energy eventually reaches Earth as sunlight. The light arriving here has traveled through space for about eight minutes. Even light takes time to make the journey.
3|all|elena|So the light on a sunny wall has come from a star. That makes the Sun part of ordinary life as well as part of astronomy. It helps warm our world and supplies the energy that most plants use to grow.
3|all|chase|There are eight planets in our solar system. Starting nearest the Sun, they are Mercury, Venus, Earth, and Mars. Farther out are Jupiter, Saturn, Uranus, and Neptune. You do not have to remember the whole list to use the map. We can return to any name when we need it.
3|all|elena|Here is our Earth marker again. It sits on the third planet from the Sun. Pulling back has made home smaller on the screen, but it has not changed what Earth is. We are simply fitting more of the neighborhood into one view.
3|all|chase|The four inner planets have rocky surfaces. The four outer planets are much larger and very different from Earth. Jupiter and Saturn are called gas giants. Uranus and Neptune are called ice giants. Those names describe kinds of planets, not places with ordinary ground and weather like ours.
3|all|captain|We have room for a closer look in Haven's guide. Operator, choose Mars or Saturn.
3|all|elena|Explore Mars.
3|all|elena|Explore Saturn.
3|mars|chase|Mars is a rocky world. Much of its surface looks reddish because of iron-bearing minerals that have rusted. Robotic rovers have traveled across parts of it and sent photographs back to Earth. Those pictures show a real landscape, with rocks, dust, hills, and traces of a very different past.
3|saturn|chase|Saturn is surrounded by bright rings. From far away, they can look like solid bands, but they contain enormous numbers of separate pieces, mostly ice. Those pieces orbit Saturn. A close view helps us understand that something which looks smooth from a distance can have a complicated structure.
3|all|haven|That gives us something to compare with Earth. These are all planets, but that does not mean they all look alike.
3|all|elena|Exactly. A shared name can belong to very different places.
3|all|chase|The solar system also includes moons, asteroids, comets, and dwarf planets, including Pluto. Our map is a beginning, not a picture of every object.
3|all|captain|Save the planet view. Next we will explore something the Sun sends far beyond these worlds.

4|all|ship|Map display changing. The Sun's surrounding region.
4|all|elena|We have been looking at worlds with surfaces or visible clouds. Now we are going to add something much harder to see. The map will use colors and lines to help explain it. Those marks are part of the illustration, not glowing walls outside the ship.
4|all|chase|The Sun sends out more than light. A stream of tiny charged particles flows outward from it. Scientists call that stream the solar wind. It is very different from the air moving through trees on Earth. This wind travels through the space between the planets.
4|all|captain|As that flow spreads outward, it helps make a huge region around the Sun. The name of that region is the heliosphere.
4|all|elena|That is a long name for a useful idea. We can picture it as an enormous bubble made by the Sun's outward flow. Earth and all eight planets are inside it. We have been inside it throughout our journey on the map.
4|all|chase|This illustration draws a simple outline so we can talk about the region. Its actual shape is more complicated, and scientists are still studying it. It is not a hard shell. A spacecraft does not hit a wall when it reaches the boundary.
4|all|haven|How do people know about a place they cannot see like a planet?
4|all|chase|They use instruments. A spacecraft can measure particles and magnetic fields around it. Those measurements tell scientists about the space it is traveling through. A camera is one way to learn about a place, but it is not the only way.
4|all|captain|There is a real example for our guide. Both Voyager spacecraft traveled beyond the heliosphere into interstellar space, the space between stars. Their instruments detected changes in their surroundings. People on Earth used those measurements to understand the crossings.
4|all|elena|They did not reach another star when they crossed that boundary. There was still an enormous distance ahead of them. Leaving one region is not the same as arriving at the next familiar object on a map.
4|all|chase|The Sun's gravity reaches beyond this bubble, too. Some objects that orbit the Sun travel much farther out. That is why the boundary of the heliosphere and the outer limits of the solar system are not simply the same thing.
4|all|haven|Then we should not label this picture, the place where everything ends.
4|all|elena|Right. We can label it, the Sun's surrounding bubble. Beyond it, there is more space to explore. And sunlight does not stop at the outline, either.
4|all|ship|Heliosphere illustration ready.
4|all|captain|Add it to the guide, with its explanation. Our map now shows more than objects we can photograph. It also shows a region we understand by making measurements. Next, we will see where this whole neighborhood belongs.

5|all|ship|Wider map available. The Milky Way galaxy.
5|all|chase|As we pull back, the planets disappear into the tiny area marked as our solar system. They have not vanished from space. They are too small to show separately at this scale. The Sun becomes one star among a vast number of others.
5|all|elena|This is the moment to check what each mark means. Earlier, one circle stood for a planet. Now the bright points stand for stars, and the picture contains far more stars than we can pick out one by one.
5|all|captain|Our Sun belongs to the Milky Way, our home galaxy. A galaxy is an enormous collection of stars, gas, dust, and dark matter, held together by gravity. Our solar system is one small part of that much larger structure.
5|all|chase|This outside view of the Milky Way is an illustration informed by observations. Nobody has sent a camera far beyond our galaxy to take this portrait. We are inside it, so astronomers put together many kinds of measurements to understand its overall shape.
5|all|elena|The illustration shows a broad disk with spiral arms. Our Sun is away from the center, in a region called the Orion Spur. We will keep a marker there. Earth is much too small to draw here, but the marker tells us where to begin looking for home.
5|all|haven|When people talk about seeing the Milky Way in the night sky, are they seeing this whole shape?
5|all|chase|They are seeing it from inside. Under a dark sky, part of our galaxy can look like a faint band across the heavens. Many distant stars blend together in that view. It is a different viewpoint on the same galaxy, not another object with the same name.
5|all|elena|Like being inside a building instead of looking at a drawing of it from above. The view changes, and the drawing helps us connect what we see with the larger place.
5|all|captain|Our guide is ready. Before we send it, let us follow the map back.
5|all|ship|Milky Way. Our solar system. The Sun and its planets. Earth and its Moon. Earth.
5|all|elena|Here are the oceans and land again. Somewhere on this world is the place where you are listening. We have changed the scale of our map many times, and we have found our way back to the same home.
5|all|haven|Guide received, Asterion. We will put the pictures in order, so people can move outward and come back again. It helps to know what the smaller picture belongs to.
5|all|chase|There are other galaxies beyond ours. That can be another journey. We do not have to fit the whole universe into one visit.
5|all|captain|For today, the assignment is complete. Operator, you helped give Haven a way to explore our place in space.
5|all|elena|Our place in space includes the place you are right now. We will leave the map here, at Earth.
"""

rows = []
for i, line in enumerate(SCRIPT.strip().splitlines(), 1):
    if not line.strip():
        continue
    episode, tag, role, text = line.split("|", 3)
    rows.append({
        "episode": int(episode), "tag": tag, "role": role,
        "text": text, "id": f"line-{i:03d}",
    })

(OUT / "script.json").write_text(
    json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
)
readable = []
for episode, title in TITLES.items():
    readable.append(f"\n## {episode}. {title}\n")
    for row in rows:
        if row["episode"] == episode:
            branch = "" if row["tag"] == "all" else f" [{row['tag']}]"
            readable.append(f"**{row['role'].title()}{branch}:** {row['text']}\n")
(OUT / "script.md").write_text("\n".join(readable), encoding="utf-8")

pipeline = KPipeline(lang_code="a", device="cpu")
for index, row in enumerate(rows, 1):
    voice, speed = CAST[row["role"]]
    key = hashlib.sha256(
        json.dumps([voice, speed, row["text"]]).encode()
    ).hexdigest()[:16]
    path = CLIPS / f"ep{row['episode']}-{row['id']}-{row['role']}-{key}.wav"
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
              f"{row['role']}", flush=True)
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
        temp = path.with_suffix(".tmp.wav")
        sf.write(temp, samples, RATE, subtype="PCM_16")
        temp.replace(path)
    else:
        print(f"[{index}/{len(rows)}] Reusing {row['id']}", flush=True)
    row["file"] = str(path)
    row["seconds"] = len(samples) / RATE

routes = {
    "main": {"all", "ocean", "mars"},
    "alternate": {"all", "land", "saturn"},
}
gap = np.zeros(int(RATE * .55), dtype=np.float32)
between = np.zeros(RATE * 2, dtype=np.float32)
report = ["SET TWO: OUR PLACE IN SPACE"]

for route, tags in routes.items():
    total = 0
    transcript = []
    with sf.SoundFile(
        OUT / f"full-listening-draft-{route}.wav",
        mode="w", samplerate=RATE, channels=1, subtype="PCM_16"
    ) as full:
        for episode, title in TITLES.items():
            transcript.append(f"\n## {episode}. {title}\n")
            selected = [
                row for row in rows
                if row["episode"] == episode and row["tag"] in tags
            ]
            seconds = 0
            with sf.SoundFile(
                OUT / f"episode-{episode:02d}-{route}.wav",
                mode="w", samplerate=RATE, channels=1, subtype="PCM_16"
            ) as track:
                for row in selected:
                    samples, _ = sf.read(row["file"], dtype="float32")
                    track.write(samples)
                    track.write(gap)
                    full.write(samples)
                    full.write(gap)
                    seconds += len(samples) / RATE + .55
                    transcript.append(
                        f"**{row['role'].title()}:** {row['text']}\n"
                    )
            full.write(between)
            total += seconds + 2
            report.append(
                f"{route}: episode {episode}: "
                f"{int(seconds//60)}m {int(seconds%60):02d}s"
            )
    report.append(
        f"{route}: TOTAL {int(total//60)}m {int(total%60):02d}s"
    )
    (OUT / f"transcript-{route}.md").write_text(
        "\n".join(transcript), encoding="utf-8"
    )

(OUT / "manifest.json").write_text(
    json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
)
report.extend([
    f"Generated or reused {len(rows)} dialogue clips.",
    "Audio review only; illustrations are not generated.",
    "Timings exclude player response delays and unvisited branches.",
    f"Output folder: {OUT.resolve()}",
])
(OUT / "timing-report.txt").write_text("\n".join(report), encoding="utf-8")
print("\nSUCCESS\n" + "\n".join(report), flush=True)
