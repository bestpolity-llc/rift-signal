#!/usr/bin/env bash
set -euo pipefail

SRC="${1:-$HOME/rift-remaster/rift-signal-remaster}"
REPO="${2:-$(pwd)}"

if [[ ! -f "$SRC/missions/mission-001/mission.json" ]]; then
  echo "Mission 001 source not found at: $SRC" >&2
  exit 1
fi

mkdir -p "$REPO/docs/play/source" "$REPO/docs/play/assets/audio" "$REPO/docs/play/assets/scenes"

cp "$SRC/missions/mission-001/mission.json" "$REPO/docs/play/source/"
cp "$SRC/missions/mission-001/flow.txt" "$REPO/docs/play/source/"
cp "$SRC/missions/mission-001/script.md" "$REPO/docs/play/source/"
cp "$SRC/missions/mission-001/voice-cast.json" "$REPO/docs/play/source/"
cp "$SRC/assets/audio/narration/"*.wav "$REPO/docs/play/assets/audio/"
cp "$SRC/assets/audio/cues/"*.wav "$REPO/docs/play/assets/audio/"
cp "$SRC/dvd/menus/"*.jpg "$REPO/docs/play/assets/scenes/"

echo "Mission 001 DVD source, Kokoro narration, cues, and rendered scene art copied into docs/play."
echo "Run: node tests/web_mission_001.mjs"
