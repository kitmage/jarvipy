# PROJECT_SPEC.md

## Raspberry Pi “Jarvis” Vision + Conversation System

---

## Overview

Build a Raspberry Pi system that:

1. Runs in low-power standby watching a USB webcam for motion.
2. When motion is detected:

   * Captures a frame.
   * Performs object detection.
3. If a **person or vehicle** is detected:

   * Enter streaming conversation mode (voice interaction).
4. Otherwise:

   * Generate a short contextual spoken response (Jarvis-style) and return to standby.
5. Automatically exits conversation mode if presence disappears.

System must be modular, production-ready, and deployable via systemd.

---

## Target Hardware

* Raspberry Pi 4 (assume 4GB RAM)
* USB webcam
* USB speaker
* USB microphone (required for conversation mode)

---

## System Architecture

### Core States

* `STANDBY`
* `ANNOUNCE`
* `CONVERSATION`

### State Transitions

STANDBY
→ motion detected
→ object detection

If person or vehicle → CONVERSATION
Else → ANNOUNCE → STANDBY

CONVERSATION exits if:

* No presence for 20 seconds
* No speech for 60 seconds
* Session exceeds 5 minutes

---

## Tech Stack Requirements

### Vision

* OpenCV for:

  * Motion detection (background subtraction)
  * Frame capture
* Object detection:

  * Use TFLite SSD MobileNet
  * Must run locally on CPU
  * No cloud vision

### Audio

* Voice Activity Detection: `webrtcvad`
* Speech-to-text: `vosk` (streaming mode)
* LLM:

  * Use remote API (OpenAI-compatible endpoint)
  * Must support streaming responses
* Text-to-speech:

  * Use Piper (local TTS)
  * Must support interruption (barge-in)

---

## Functional Requirements

### Motion Detection

* 320x240 resolution
* 8–12 fps
* Background subtraction
* Trigger if contour area > threshold for 6 consecutive frames
* 8 second cooldown between events
* Save snapshot to `/tmp`

---

### Object Detection

* Run only on motion event
* Return:

  * List of objects
  * Confidence scores
* Define vehicles as:

  * car
  * truck
  * bus
  * motorcycle
  * bicycle

---

### ANNOUNCE Mode

If motion but no person/vehicle:

* Call LLM with:

  * Detected objects
  * Time of day
  * Previous event summary (if any)
* LLM returns JSON:

```
{
  "say": "string",
  "priority": "normal|high"
}
```

* Speak `say`
* Return to STANDBY

Speech in `ANNOUNCE` mode is allowed only when all gating checks pass after a non-person/vehicle motion event:

1. Current local time is outside configured quiet hours (`QUIET_HOURS_START` → `QUIET_HOURS_END`).
2. Top detected non-person object confidence is at least `ANNOUNCE_MIN_CONFIDENCE` (default: `0.60`).
3. At least one of the following is true:

   * The same object class was detected in 2 events within `ANNOUNCE_REPEAT_WINDOW_SECONDS` (default: `30` seconds), or
   * The LLM response priority is `high`.

If any gating check fails, skip TTS output, log the reason, and return to `STANDBY` silently.

Expected behavior examples:

* **Daytime:** Motion at 14:20 with `cat (0.82)` detected twice in 20 seconds → gating passes, system speaks the `say` text, then returns to `STANDBY`.
* **Nighttime:** Motion at 02:10 with `dog (0.91)` and normal priority, but within quiet hours → no speech; event is logged and system returns to `STANDBY`.
* **Low confidence:** Motion at 16:45 with `unknown (0.41)` below threshold → no speech even if outside quiet hours; event is logged and system returns to `STANDBY`.

---

### CONVERSATION Mode

Triggered only if person or vehicle detected.

Steps:

1. Speak:
   “Hello. How can I help?”

2. Begin streaming loop:

   * VAD detects speech
   * Stream audio to Vosk
   * Send transcript to LLM
   * Stream LLM response
   * Speak response

3. Maintain rolling memory (last 10 exchanges max)

4. Presence monitoring:

   * Re-check camera every 2 seconds
   * If no person/vehicle for 20 seconds → exit

5. On exit:

   * Speak: “Standing by.”
   * Return to STANDBY

---

## Barge-In Behavior

If user begins speaking while TTS is active:

* Immediately stop TTS playback
* Resume listening

---

## Configuration

Create `.env` support:

```
LLM_API_KEY=
LLM_ENDPOINT=
LLM_MODEL=
MOTION_AREA_THRESHOLD=
COOLDOWN_SECONDS=
QUIET_HOURS_START=
QUIET_HOURS_END=
ANNOUNCE_MIN_CONFIDENCE=
ANNOUNCE_REPEAT_WINDOW_SECONDS=
```

All thresholds must be configurable.

---

## Project Structure

```
jarvis-pi/
│
├── motion/
│   └── motion_watch.py
│
├── vision/
│   └── detect_objects.py
│
├── audio/
│   ├── vad.py
│   ├── stt.py
│   ├── tts.py
│
├── brain/
│   ├── llm.py
│   ├── memory.py
│
├── state/
│   └── state_machine.py
│
├── main.py
│
├── requirements.txt
├── .env.example
├── install.sh
├── jarvis.service
└── README.md
```

---

## Non-Functional Requirements

* Must start automatically on boot via systemd
* Must log to file:

  * Motion events
  * Detected objects
  * LLM responses
  * Errors
* Must fail gracefully if:

  * Camera disconnects
  * API unavailable
  * Mic not detected
* Must auto-recover from transient failures

---

## Logging

* Write logs to:
  `/var/log/jarvis.log`
* Use structured logging (JSON preferred)

---

## Performance Constraints

* CPU usage idle < 20%
* Conversation response latency < 3 seconds (excluding network delay)
* Motion detection must not block audio thread

---

## Deliverables

AI agent must:

1. Create full GitHub-ready repository
2. Include:

   * Clean modular code
   * Type hints
   * Docstrings
   * README with setup instructions
3. Provide install steps:

   * OS dependencies
   * Python dependencies
   * Model downloads
4. Include systemd service file
5. Provide testing instructions

---

## Stretch Goals (Optional but Preferred)

* GPIO mute button support
* Web dashboard for logs
* Event image archive
* Confidence-based speech tone (e.g., uncertain if confidence < 0.6)
* Configurable personality prompt

---

## Personality Prompt

Use system prompt:

“You are Jarvis, a concise, observant AI assistant embedded in a physical environment. Speak clearly, intelligently, and briefly. Avoid verbosity. Do not hallucinate unseen facts.”

Responses must be:

* Short (1–3 sentences)
* Context-aware
* Calm tone

---

## Final Goal

Produce a stable, modular, production-ready Raspberry Pi system that:

* Watches
* Detects
* Identifies
* Speaks
* Converses
* Returns to standby

No monolithic scripts. No prototype shortcuts.
This should be maintainable and extendable.

---

End of specification.
