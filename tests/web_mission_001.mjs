import assert from "node:assert/strict";
import { SCENES, SCENE_MAP, DVD_SCENE_ORDER, ROLE_VOICES } from "../docs/play/mission.js";

assert.equal(SCENES.length, 22, "Mission 001 must preserve all 22 DVD scenes");
assert.equal(new Set(DVD_SCENE_ORDER).size, 22, "Scene IDs must be unique");
assert.deepEqual(
  DVD_SCENE_ORDER,
  ["welcome","captain","mentor","receiver","request","pilot","choice_intro","choose_planet","choose_stars","planet_view","planet_capture","planet_link","planet_sent","planet_thanks","stars_view","stars_capture","stars_link","stars_sent","stars_thanks","debrief","crew_room","off_duty"]
);
assert.deepEqual(
  SCENES.filter(s => s.timed).map(s => s.id),
  ["choose_planet","choose_stars"],
  "Only the two DVD picture-choice screens should be timed"
);

function reachesEnd(start) {
  const seen = new Set();
  const stack = [start];
  while (stack.length) {
    const id = stack.pop();
    if (id === "off_duty") return true;
    if (seen.has(id)) continue;
    seen.add(id);
    const scene = SCENE_MAP[id];
    if (!scene) continue;
    if (scene.next) stack.push(scene.next);
    if (scene.choose) stack.push(scene.choose);
    if (scene.alternate && !seen.has(scene.alternate)) stack.push(scene.alternate);
  }
  return false;
}

assert.ok(reachesEnd("planet_view"), "Planet branch must reach end of shift");
assert.ok(reachesEnd("stars_view"), "Stars branch must reach end of shift");
assert.equal(ROLE_VOICES.captain.kokoro, "am_michael");
assert.equal(ROLE_VOICES.mentor.kokoro, "af_heart");
assert.equal(ROLE_VOICES.pilot.kokoro, "am_fenrir");
assert.equal(ROLE_VOICES.haven.kokoro, "af_bella");
assert.equal(ROLE_VOICES.ship.kokoro, "af_sarah");

console.log("PASS: Web Mission 001 preserves the 22-scene DVD graph, both branches, timed choice pair, and Kokoro cast mapping.");
