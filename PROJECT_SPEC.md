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

Presence policy (must be configurable):

* `CONVERSATION_PRESENCE_CONFIDENCE_THRESHOLD` (default: `0.65`) is the minimum confidence for counting a `person` or vehicle detection as present.
* `CONVERSATION_ABSENCE_MISSES_REQUIRED` (default: `3`) is the number of consecutive presence re-checks below threshold before counting the scene as absent.
* `CONVERSATION_KEEPALIVE_CLASS_MODE` controls keep-alive behavior:

  * `person_or_vehicle` (default): any qualifying person or vehicle detection keeps conversation alive.
  * `person_only`: only qualifying person detections keep conversation alive; vehicles alone do not.

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
   * A re-check counts as **present** only when detection confidence meets `CONVERSATION_PRESENCE_CONFIDENCE_THRESHOLD` and matches `CONVERSATION_KEEPALIVE_CLASS_MODE`
   * Count absence only after `CONVERSATION_ABSENCE_MISSES_REQUIRED` consecutive non-qualifying re-checks
   * Start the 20-second absence timer only after absence is counted
   * Any qualifying re-check while timer is running resets absence state and clears the 20-second timer
   * If counted-absent state lasts 20 seconds → exit

State-transition example (2-second re-check interval, threshold `0.65`, misses required `3`, mode `person_or_vehicle`):

* `t=0s` person `0.78` → present, timer not running.
* `t=2s` none detected → miss #1.
* `t=4s` bicycle `0.72` → present again, miss count reset.
* `t=6s` car `0.60` (below threshold) → miss #1.
* `t=8s` none → miss #2.
* `t=10s` none → miss #3, absence is now counted, 20-second timer starts.
* `t=18s` person `0.81` → timer resets and miss count clears (conversation continues).
* `t=20s`, `22s`, `24s` none → miss #3 again at `24s`, timer restarts.
* No qualifying detections through `t=44s` → 20 seconds elapsed since counted absence, exit conversation.

5. On exit:

   * Speak: “Standing by.”
   * Return to STANDBY

---

## Barge-In Behavior

If user begins speaking while TTS is active:

* Immediately stop TTS playback with a maximum interruption latency of **<= 300 ms** from VAD speech-start detection to audible playback halt.
* Any queued/buffered TTS chunks not yet played must be **dropped** (do not drain stale response audio after interruption).
* The interrupted assistant response is **discarded** (non-resumable); the next turn should be generated from fresh ASR/LLM input.
* Resume listening immediately after stop.

Acceptance test scenario (barge-in timing):

* `t=0 ms`: Assistant starts speaking response chunk 1.
* `t=900 ms`: Response chunks 2 and 3 are already queued in the audio buffer.
* `t=1200 ms`: User speech starts and VAD flags speech start.
* `t=1460 ms`: TTS playback is fully halted (`260 ms` interruption latency, passes `<= 300 ms` target).
* `t=1465 ms`: Queued chunks 2 and 3 are dropped and never played.
* `t=1500 ms`: System is back in listening/ASR capture state for the user utterance.
* Expected result: no further audio from the interrupted response is heard, and no resume of the prior response occurs.

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
CONVERSATION_PRESENCE_CONFIDENCE_THRESHOLD=
CONVERSATION_ABSENCE_MISSES_REQUIRED=
CONVERSATION_KEEPALIVE_CLASS_MODE=person_or_vehicle
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
* Deployment configuration must explicitly define the runtime service account:

  * `jarvis.service` must run as `User=jarvis` and `Group=jarvis`
  * `install.sh` must create the `jarvis` system user/group if absent (`useradd --system` / `groupadd --system`)
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
* `install.sh` must create the log target during install:

  * Ensure parent directory exists
  * Create `/var/log/jarvis.log` if missing
  * Set ownership to `jarvis:jarvis`
  * Set permissions to `0640` (owner read/write, group read, no world access)
* Rotation expectations:

  * Include a `logrotate` policy (or equivalent) for `jarvis.log`
  * Recommended baseline: daily rotation, keep 7 files, compress old logs, `copytruncate` if process does not reopen file handles on `SIGHUP`
* Fallback behavior when `/var/log/jarvis.log` is not writable:

  * Application must automatically fall back to a writable local path (`/tmp/jarvis.log` minimum requirement)
  * Emit a warning to journald/stdout indicating fallback activation and the active log path
  * Continue service operation (logging degradation must not crash the main process)

---

## Performance Constraints

* CPU usage idle < 20%
* Conversation response latency < 3 seconds (excluding network delay)
* Motion detection must not block audio thread

### Test / Validation

Performance constraints must be validated with repeatable measurement procedures:

* **Idle CPU measurement**

  * Tool: `pidstat -u 1` (from `sysstat`) against the running `jarvis` process.
  * Sampling window: collect 60 consecutive 1-second samples after a 30-second warm-up while the system remains in `STANDBY` with no motion/audio events.
  * Report: use the mean `%CPU` across the 60 samples as idle CPU.

* **Conversation latency measurement**

  * Measure per turn using monotonic timestamps emitted in code at these exact timing points:

    * **Start timestamp (`t_start`)**: when final user transcript is emitted from `audio/stt.py` and handed off to the LLM request path.
    * **LLM first-token timestamp (`t_llm_first`)**: when the first streamed token/chunk is received in `brain/llm.py`.
    * **TTS-start timestamp (`t_tts_start`)**: when playback of synthesized response audio begins in `audio/tts.py`.
  * Primary conversation latency metric: `t_tts_start - t_start`.
  * Diagnostic sub-metric: `t_llm_first - t_start` (to separate LLM time from TTS start delay).

* **Minimum runs and pass/fail thresholds**

  * Idle CPU: run at least **3 independent idle windows** (60s each); pass if each window mean is `< 20%` and overall mean is `< 18%`.
  * Conversation latency: run at least **30 conversation turns** (minimum 10 turns across each of 3 sessions); pass if:

    * 95th percentile of `t_tts_start - t_start` is `< 3.0s`.
    * Maximum `t_tts_start - t_start` is `<= 3.5s`.
    * No missing timing records from `audio/stt.py`, `brain/llm.py`, or `audio/tts.py`.

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
