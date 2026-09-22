import { SCENES, SCENE_MAP, ROLE_VOICES } from "./mission.js";

const $ = (selector) => document.querySelector(selector);
const actionRow = $("#actionRow");
const sceneImage = $("#sceneImage");
const sceneFallback = $("#sceneFallback");
const choiceMeter = $("#choiceMeter");

let currentId = "welcome";
let scanTimer = null;
let scanIndex = 0;
let choiceTimer = null;
let currentAudio = null;
let cachedSiteArt = null;

const DVD_AUDIO_PATH = id => `assets/audio/${id}.wav`;
const DVD_IMAGE_PATH = id => `assets/scenes/${id}.jpg`;

function currentScene() {
  return SCENE_MAP[currentId];
}

function stopNarration() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

function tone(freq = 440, duration = 0.07) {
  if (!$("#soundToggle").checked) return;
  try {
    const ctx = tone.ctx ||= new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = freq;
    gain.gain.value = 0.035;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.stop(ctx.currentTime + duration + 0.01);
  } catch {}
}

function cue(name) {
  if (!name || !$("#soundToggle").checked) return;
  const frequencies = { incoming: 620, connected: 520, confirm: 760, sent: 880 };
  tone(frequencies[name] || 500, 0.08);
}

function pickBrowserVoice(role) {
  const voices = speechSynthesis.getVoices();
  if (!voices.length) return null;
  const english = voices.filter(v => /^en/i.test(v.lang));
  const pool = english.length ? english : voices;
  const preferred = {
    captain: ["male", "david", "daniel", "alex"],
    pilot: ["male", "guy", "ryan", "alex"],
    mentor: ["female", "samantha", "victoria", "zira"],
    haven: ["female", "samantha", "aria", "zira"],
    ship: ["female", "samantha", "aria", "zira"]
  }[role] || [];
  return pool.find(v => preferred.some(key => v.name.toLowerCase().includes(key))) || pool[0];
}

function fallbackSpeech(scene) {
  if (!$("#soundToggle").checked || !("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(scene.narration);
  const config = ROLE_VOICES[scene.role];
  utterance.rate = config?.rate || 0.92;
  const voice = pickBrowserVoice(scene.role);
  if (voice) utterance.voice = voice;
  speechSynthesis.speak(utterance);
}

function playNarration(scene) {
  stopNarration();
  if (!$("#soundToggle").checked) return;
  const audio = new Audio(DVD_AUDIO_PATH(scene.id));
  currentAudio = audio;
  let fellBack = false;
  const fallback = () => {
    if (fellBack || currentAudio !== audio) return;
    fellBack = true;
    currentAudio = null;
    fallbackSpeech(scene);
  };
  audio.addEventListener("error", fallback, { once: true });
  audio.play().catch(fallback);
}

async function loadSiteArt() {
  if (cachedSiteArt) return cachedSiteArt;
  try {
    const response = await fetch("../");
    const text = await response.text();
    const doc = new DOMParser().parseFromString(text, "text/html");
    cachedSiteArt = {
      hero: doc.querySelector(".hero-media img")?.src || "",
      captain: doc.querySelectorAll(".crew-card img")[0]?.src || "",
      mentor: doc.querySelectorAll(".crew-card img")[1]?.src || "",
      pilot: doc.querySelectorAll(".crew-card img")[2]?.src || ""
    };
  } catch {
    cachedSiteArt = {};
  }
  return cachedSiteArt;
}

function sceneAlt(scene) {
  const labels = {
    planet: "A blue planet seen from the Asterion",
    stars: "A wide star field beyond the Asterion",
    captain: "Captain Marcus Vale aboard the Asterion",
    mentor: "Elena Torres aboard the Asterion",
    pilot: "Pilot Chase Mercer aboard the Asterion",
    crew: "The Asterion crew",
    bridge: "The Asterion in deep space",
    signal: "Signal Operations aboard the Asterion",
    choice: "Asterion observation choices"
  };
  return labels[scene.visual] || "Aboard the Asterion";
}

async function renderVisual(scene) {
  sceneImage.hidden = true;
  sceneFallback.hidden = false;
  $("#fallbackLabel").textContent = scene.visual === "planet" ? "BLUE PLANET" :
    scene.visual === "stars" ? "STAR FIELD" :
    scene.visual === "signal" ? "SIGNAL OPERATIONS" :
    scene.visual === "crew" ? "CREW QUARTERS" : "ASTERION";

  sceneImage.alt = sceneAlt(scene);
  sceneImage.onerror = null;

  const exact = DVD_IMAGE_PATH(scene.id);
  const art = await loadSiteArt();
  const fallback = art[scene.visual] || art.hero || "";
  const candidates = [exact, fallback].filter(Boolean);
  let position = 0;

  const tryNext = () => {
    if (position >= candidates.length) {
      sceneImage.hidden = true;
      sceneFallback.hidden = false;
      return;
    }
    sceneImage.src = candidates[position++];
    sceneImage.onerror = tryNext;
    sceneImage.onload = () => {
      sceneFallback.hidden = true;
      sceneImage.hidden = false;
    };
  };
  tryNext();
}

function clearScan() {
  clearInterval(scanTimer);
  scanTimer = null;
  actionRow.querySelectorAll(".action").forEach(button => button.classList.remove("scan-focus"));
}

function resetScan() {
  clearScan();
  if (!$("#scanToggle").checked) return;
  const buttons = [...actionRow.querySelectorAll(".action:not(:disabled)")];
  if (!buttons.length) return;
  scanIndex = 0;
  buttons[0].classList.add("scan-focus");
  buttons[0].focus();
  if (buttons.length > 1) {
    scanTimer = setInterval(() => {
      const current = [...actionRow.querySelectorAll(".action:not(:disabled)")];
      if (!current.length) return;
      current.forEach(button => button.classList.remove("scan-focus"));
      scanIndex = (scanIndex + 1) % current.length;
      current[scanIndex].classList.add("scan-focus");
      current[scanIndex].focus();
      tone(360, 0.025);
    }, Number($("#scanSpeed").value));
  }
}

function clearChoiceTimer() {
  clearTimeout(choiceTimer);
  choiceTimer = null;
  choiceMeter.hidden = true;
}

function startChoiceTimer(scene) {
  clearChoiceTimer();
  if (!scene.timed) return;
  choiceMeter.hidden = false;
  const bar = choiceMeter.querySelector("span");
  bar.style.animation = "none";
  void bar.offsetWidth;
  bar.style.animation = "";
  choiceTimer = setTimeout(() => {
    currentId = scene.alternate;
    renderScene({ narrate: true });
  }, 5000);
}

function setAction(scene) {
  clearScan();
  actionRow.innerHTML = "";
  const button = document.createElement("button");
  button.className = "action";
  button.type = "button";
  button.textContent = scene.action;
  button.addEventListener("click", () => activateScene(scene));
  actionRow.appendChild(button);
  button.focus();
  resetScan();
}

function activateScene(scene) {
  cue(scene.cue || "confirm");
  clearChoiceTimer();
  if (scene.timed) {
    currentId = scene.choose;
  } else {
    currentId = scene.next;
  }
  renderScene({ narrate: true });
}

function progressFor(scene) {
  const index = SCENES.findIndex(item => item.id === scene.id);
  return `SCENE ${String(index + 1).padStart(2, "0")} / 22`;
}

async function renderScene({ narrate = true } = {}) {
  clearChoiceTimer();
  const scene = currentScene();
  if (!scene) return;

  $("#sceneTitle").textContent = scene.title;
  $("#sceneProgress").textContent = progressFor(scene);
  const role = ROLE_VOICES[scene.role];
  $("#speakerRole").textContent = scene.role.toUpperCase();
  $("#speakerName").textContent = role?.label || scene.role;
  $("#narration").textContent = scene.narration;
  $("#sceneHint").textContent = scene.timed
    ? "One-button choice: press while this view is showing, or wait for the other view."
    : scene.end
      ? "First Shift complete. Restart whenever you want to run it again."
      : "Press once to continue.";
  $("#systemState").textContent = scene.id === "off_duty" ? "SHIFT COMPLETE" : "SIGNAL OPS ONLINE";

  await renderVisual(scene);
  setAction(scene);
  startChoiceTimer(scene);
  if (narrate) playNarration(scene);
}

function activateSwitch() {
  const buttons = [...actionRow.querySelectorAll(".action:not(:disabled)")];
  if (!buttons.length) return;
  let target = $("#scanToggle").checked ? actionRow.querySelector(".scan-focus") : document.activeElement;
  if (!(target instanceof HTMLButtonElement) || !actionRow.contains(target)) target = buttons[0];
  target.click();
}

$("#scanToggle").addEventListener("change", resetScan);
$("#scanSpeed").addEventListener("input", event => {
  $("#scanSpeedLabel").textContent = (Number(event.target.value) / 1000).toFixed(1) + "s";
  resetScan();
});
$("#textSize").addEventListener("change", event => {
  document.documentElement.style.setProperty("--scale", event.target.value);
});
$("#reducedMotion").addEventListener("change", event => {
  document.body.classList.toggle("reduced-motion", event.target.checked);
});
$("#soundToggle").addEventListener("change", () => {
  if (!$("#soundToggle").checked) stopNarration();
  else playNarration(currentScene());
});
$("#replayBtn").addEventListener("click", () => playNarration(currentScene()));
$("#restartBtn").addEventListener("click", () => {
  currentId = "welcome";
  renderScene({ narrate: true });
});
$("#fullscreenBtn").addEventListener("click", async () => {
  try {
    if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
    else await document.exitFullscreen();
  } catch {}
});

window.addEventListener("keydown", event => {
  if ((event.code === "Space" || event.code === "Enter" || event.code === "NumpadEnter") &&
      !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    activateSwitch();
  }
});

window.addEventListener("beforeunload", stopNarration);
if ("speechSynthesis" in window) window.speechSynthesis.addEventListener?.("voiceschanged", () => {});

renderScene({ narrate: false });
