export const ROLE_VOICES = {
  ship: { label: "Ship guidance", kokoro: "af_sarah", rate: 0.92 },
  captain: { label: "Captain Marcus Vale", kokoro: "am_michael", rate: 0.91 },
  mentor: { label: "Elena Torres", kokoro: "af_heart", rate: 0.90 },
  pilot: { label: "Pilot Chase Mercer", kokoro: "am_fenrir", rate: 0.96 },
  haven: { label: "Haven research station", kokoro: "af_bella", rate: 0.92 }
};

export const SCENES = [
  {
    id: "welcome", role: "ship", title: "Welcome aboard",
    narration: "Welcome aboard the Asterion. Your first shift begins at Signal Operations. The crew is ready when you are.",
    action: "BEGIN FIRST SHIFT", next: "captain", visual: "bridge", cue: "connected"
  },
  {
    id: "captain", role: "captain", title: "Captain Marcus Vale",
    narration: "Signal Operator, welcome aboard. Every station on this ship has a job. Yours is to notice the signal, make the choice, and send it when the crew is ready.",
    action: "CONTINUE", next: "mentor", visual: "captain"
  },
  {
    id: "mentor", role: "mentor", title: "Meet your mentor",
    narration: "I’m Elena Torres. I’ll stay with you through the shift. There is no rush. One clear choice at a time is enough.",
    action: "CONTINUE", next: "receiver", visual: "mentor"
  },
  {
    id: "receiver", role: "ship", title: "Incoming signal",
    narration: "Signal Operations: incoming transmission detected. Source identified as Haven research station.",
    action: "OPEN CHANNEL", next: "request", visual: "signal", cue: "incoming"
  },
  {
    id: "request", role: "haven", title: "A request from Haven",
    narration: "Asterion, this is Haven research station. Our common room needs something from the outside. Could your Signal Operator send us a picture from your current position?",
    action: "ACCEPT REQUEST", next: "pilot", visual: "signal"
  },
  {
    id: "pilot", role: "pilot", title: "Two views available",
    narration: "I can give you two clean views from here: the blue planet below us, or the stars beyond the ship. You choose which picture we send.",
    action: "CONTINUE", next: "choice_intro", visual: "pilot"
  },
  {
    id: "choice_intro", role: "mentor", title: "Choose the picture",
    narration: "The two views will take turns on your screen. When the one you want is showing, press once to choose it.",
    action: "START CHOICE", next: "choose_planet", visual: "choice"
  },
  {
    id: "choose_planet", role: "mentor", title: "Blue planet",
    narration: "The blue planet is in view. Press now to choose the planet, or wait and the stars will appear.",
    action: "CHOOSE BLUE PLANET", choose: "planet_view", alternate: "choose_stars", timed: true, visual: "planet"
  },
  {
    id: "choose_stars", role: "mentor", title: "Star field",
    narration: "The stars are in view. Press now to choose the stars, or wait and the blue planet will return.",
    action: "CHOOSE THE STARS", choose: "stars_view", alternate: "choose_planet", timed: true, visual: "stars"
  },
  {
    id: "planet_view", role: "pilot", title: "Planet view",
    narration: "Planet view is steady. Cloud bands and the bright edge of the atmosphere are clear from this angle.",
    action: "CONTINUE", next: "planet_capture", visual: "planet"
  },
  {
    id: "planet_capture", role: "mentor", title: "Capture the planet",
    narration: "That’s your view. When you’re ready, capture the picture for Haven.",
    action: "CAPTURE PICTURE", next: "planet_link", visual: "planet", cue: "confirm"
  },
  {
    id: "planet_link", role: "ship", title: "Link to Haven",
    narration: "Picture captured. Establishing a signal link to Haven research station.",
    action: "CONNECT", next: "planet_sent", visual: "signal", cue: "connected"
  },
  {
    id: "planet_sent", role: "ship", title: "Planet picture sent",
    narration: "Connection confirmed. The planet picture has been transmitted to Haven.",
    action: "CONTINUE", next: "planet_thanks", visual: "signal", cue: "sent"
  },
  {
    id: "planet_thanks", role: "haven", title: "Haven responds",
    narration: "We received it. The blue planet looks beautiful from there. Thank you, Signal Operator. We’re putting it in the common room.",
    action: "RETURN TO CREW", next: "debrief", visual: "planet"
  },
  {
    id: "stars_view", role: "pilot", title: "Star view",
    narration: "Star field is steady. You’ve got a clear view beyond the Asterion.",
    action: "CONTINUE", next: "stars_capture", visual: "stars"
  },
  {
    id: "stars_capture", role: "mentor", title: "Capture the stars",
    narration: "That’s your view. When you’re ready, capture the picture for Haven.",
    action: "CAPTURE PICTURE", next: "stars_link", visual: "stars", cue: "confirm"
  },
  {
    id: "stars_link", role: "ship", title: "Link to Haven",
    narration: "Picture captured. Establishing a signal link to Haven research station.",
    action: "CONNECT", next: "stars_sent", visual: "signal", cue: "connected"
  },
  {
    id: "stars_sent", role: "ship", title: "Star picture sent",
    narration: "Connection confirmed. The star picture has been transmitted to Haven.",
    action: "CONTINUE", next: "stars_thanks", visual: "signal", cue: "sent"
  },
  {
    id: "stars_thanks", role: "haven", title: "Haven responds",
    narration: "We received it. Those stars will be a good reminder that there is a lot beyond this station. Thank you, Signal Operator.",
    action: "RETURN TO CREW", next: "debrief", visual: "stars"
  },
  {
    id: "debrief", role: "captain", title: "Mission complete",
    narration: "Good work. Haven asked for something, you made the choice, and the crew carried your signal through. That is what your station is here to do.",
    action: "END SHIFT", next: "crew_room", visual: "captain"
  },
  {
    id: "crew_room", role: "mentor", title: "Crew quarters",
    narration: "We’re off duty now. This is a good time to talk about the picture you chose, what you noticed, and what you might choose next time.",
    action: "CONTINUE", next: "off_duty", visual: "crew"
  },
  {
    id: "off_duty", role: "mentor", title: "First Shift complete",
    narration: "Your first shift aboard the Asterion is complete. Signal Operations will be ready for you when the next mission begins.",
    action: "RESTART FIRST SHIFT", next: "welcome", visual: "crew", end: true
  }
];

export const SCENE_MAP = Object.fromEntries(SCENES.map(scene => [scene.id, scene]));
export const DVD_SCENE_ORDER = SCENES.map(scene => scene.id);
