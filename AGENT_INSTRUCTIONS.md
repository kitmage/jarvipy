# AGENT_INSTRUCTIONS.md

## Purpose
This document is an execution plan for implementing the full Raspberry Pi Jarvis system described in `PROJECT_SPEC.md`. It is written so a coding agent can deliver a production-ready repository incrementally, with clear module responsibilities, interfaces, and validation checkpoints.

---

## 1) Delivery Strategy

Implement in **vertical slices** rather than building all modules in isolation. Each slice should produce runnable behavior and tests.

### Slice order
1. **Scaffold + configuration + logging + health checks**
2. **Vision standby loop (motion + object detection) + state machine core**
3. **ANNOUNCE mode with gating + LLM JSON response + TTS playback**
4. **CONVERSATION mode (VAD/STT/LLM/TTS streaming) + presence policy**
5. **Resilience and recovery behavior**
6. **Install/deploy artifacts (systemd, install.sh, logrotate)**
7. **Performance instrumentation + validation scripts + docs hardening**

After each slice: run tests, update docs, and keep the app runnable from `main.py`.

---

## 2) Required Repository Layout

Create exactly this structure first:

```text
jarvis-pi/
├── motion/
│   └── motion_watch.py
├── vision/
│   └── detect_objects.py
├── audio/
│   ├── vad.py
│   ├── stt.py
│   ├── tts.py
├── brain/
│   ├── llm.py
│   ├── memory.py
├── state/
│   └── state_machine.py
├── infra/
│   ├── config.py
│   ├── logging.py
│   ├── errors.py
│   └── time_utils.py
├── scripts/
│   ├── validate_idle_cpu.sh
│   ├── validate_latency.py
│   └── smoke_test.py
├── tests/
│   ├── test_state_machine.py
│   ├── test_announce_gating.py
│   ├── test_presence_policy.py
│   ├── test_memory.py
│   └── test_config.py
├── main.py
├── requirements.txt
├── .env.example
├── install.sh
├── jarvis.service
├── jarvis.logrotate
├── README.md
└── PROJECT_SPEC.md
```

Notes:
- Add `__init__.py` files where needed.
- Use Python 3.11+.
- Keep business logic out of shell scripts and service file.

---

## 3) Architecture and Contracts

Define explicit interfaces early to prevent coupling.

### 3.1 `infra/config.py`
- Load `.env` + environment variables.
- Provide a typed `Settings` dataclass (or Pydantic model) with defaults from spec.
- Validate ranges (e.g., confidence in `[0,1]`, positive intervals).
- Expose parsed quiet-hours helper (supports cross-midnight ranges).

### 3.2 `infra/logging.py`
- JSON structured logger writing to `/var/log/jarvis.log`.
- On open/permission failure, fallback to `/tmp/jarvis.log` and emit warning to stdout/journald.
- Include standard fields: timestamp, level, module, event_type, state, session_id, metadata.

### 3.3 `state/state_machine.py`
- Enum states: `STANDBY`, `ANNOUNCE`, `CONVERSATION`.
- Single controller class that owns transitions and timers.
- No hardware-specific code inside transition logic; call dependency interfaces.

### 3.4 Component contracts
Use protocols/ABCs to allow mocking:
- Motion watcher: yields motion events + snapshot path.
- Detector: accepts frame/path, returns list of detections (`label`, `confidence`, `bbox`).
- TTS: `speak(text)`, `stop()`, playback state, interruption hooks.
- STT stream: yields final transcript chunks/events.
- LLM client: supports normal completion and streaming completion.

---

## 4) Module-by-Module Implementation Plan

## 4.1 Motion (`motion/motion_watch.py`)
Implement:
- OpenCV camera capture at 320x240, target 8–12 FPS.
- Background subtraction + contour-area threshold check.
- Trigger condition: contour area > threshold for 6 consecutive frames.
- Cooldown: no new motion events for `COOLDOWN_SECONDS` after trigger.
- Save snapshot to `/tmp` with timestamp-based filename.

Testing:
- Unit test trigger counting and cooldown logic with synthetic frame metadata.
- Integration smoke test with mocked camera frames.

## 4.2 Object detection (`vision/detect_objects.py`)
Implement:
- TFLite SSD MobileNet local CPU inference.
- Label map support.
- Return normalized detection objects with confidence.
- Helper: `contains_person_or_vehicle(detections)` using vehicle class set.

Testing:
- Mock interpreter test for filtering/confidence parsing.
- Classifier utility tests for person/vehicle determination.

## 4.3 ANNOUNCE logic
Location:
- Decision logic in `state/state_machine.py` (or dedicated helper in `brain/announce.py` if preferred).

Implement gating checks exactly:
1. Not within quiet hours.
2. Top non-person confidence >= `ANNOUNCE_MIN_CONFIDENCE`.
3. Repeated object in window OR LLM priority high.

LLM interaction:
- Send objects + local time + previous event summary.
- Parse strict JSON response with fallback handling.
- If parsing fails: log and skip speech or use safe fallback sentence.

Testing:
- Table-driven tests for gating pass/fail reasons.
- Quiet-hours cross-midnight tests.
- LLM JSON parsing robustness tests.

## 4.4 Conversation pipeline (`audio/*`, `brain/llm.py`, state integration)
Implement end-to-end loop:
- Greeting: “Hello. How can I help?”
- VAD detects speech start/stop windows.
- Streaming STT via Vosk.
- Pass final user transcript to LLM streaming API.
- Stream response to TTS.
- Maintain rolling memory of last 10 exchanges.

Instrumentation timestamps:
- `t_start` in STT handoff.
- `t_llm_first` on first LLM chunk.
- `t_tts_start` when playback begins.

Testing:
- Unit tests for memory truncation.
- Simulated conversation integration test with mocked VAD/STT/LLM/TTS.

## 4.5 Presence policy and conversation exit
Implement policy params:
- `CONVERSATION_PRESENCE_CONFIDENCE_THRESHOLD`
- `CONVERSATION_ABSENCE_MISSES_REQUIRED`
- `CONVERSATION_KEEPALIVE_CLASS_MODE`

Behavior:
- Re-check every 2 seconds.
- Count misses until threshold; then mark absent and start 20-second timer.
- Any qualifying detection resets miss count + absence timer.
- Independent exit timers: no speech 60s, max session 5 min.
- Exit phrase: “Standing by.”

Testing:
- Deterministic time-based tests reproducing spec timeline.
- Separate tests for `person_or_vehicle` vs `person_only`.

## 4.6 Barge-in in `audio/tts.py`
Implement:
- Interruptible playback queue.
- On VAD speech start during playback:
  - stop audio within <=300 ms,
  - clear queued chunks,
  - return control to listening state.

Testing:
- Timing-focused test harness with mocked playback clock.
- Assert no resumed playback from interrupted chunks.

## 4.7 Resilience
Add robust recovery behaviors:
- Camera disconnect: log error, retry with backoff, continue service.
- LLM API errors/timeouts: graceful user message (or silent fallback in announce), continue loop.
- Missing mic/audio device: log and retry initialization periodically.
- Never crash main loop on recoverable subsystem failure.

Testing:
- Fault injection tests for each subsystem.
- Verify process continues and state returns to standby when applicable.

---

## 5) Deployment Artifacts

## 5.1 `install.sh`
Must:
- Install OS packages and Python venv dependencies.
- Create `jarvis` system group/user if missing (`groupadd --system`, `useradd --system`).
- Create `/var/log/jarvis.log`, set ownership `jarvis:jarvis`, mode `0640`.
- Install `jarvis.service` and `jarvis.logrotate`.
- Enable and restart service.

## 5.2 `jarvis.service`
Must include:
- `User=jarvis`
- `Group=jarvis`
- Working directory and ExecStart in venv.
- Restart policy (`on-failure`) and sane restart delay.
- Environment file loading (`.env` path).

## 5.3 `jarvis.logrotate`
Include:
- Daily rotation
- Keep 7
- Compress
- `copytruncate` (unless app handles log reopen signals)

---

## 6) Performance Validation Plan

Implement scripts:
- `scripts/validate_idle_cpu.sh`
  - Warm-up 30s.
  - Collect `pidstat -u 1` for 60 samples.
  - Compute mean CPU for each run.
  - Repeat 3 runs; report per-run and overall mean.

- `scripts/validate_latency.py`
  - Parse structured logs for timestamp triplets.
  - Compute per-turn latency metrics.
  - Enforce pass criteria:
    - p95(`t_tts_start - t_start`) < 3.0s
    - max <= 3.5s
    - no missing records.

Document exact commands in README.

---

## 7) Testing & Quality Gates

Minimum CI/local gate before each commit:
1. `ruff check .`
2. `black --check .`
3. `mypy .`
4. `pytest -q`
5. `python scripts/smoke_test.py`

Additional integration gates before release:
- Simulated end-to-end state transitions.
- Device-available sanity run on Raspberry Pi.
- Service restart + boot persistence check.

---

## 8) Coding Conventions

- Type hints on all public functions.
- Docstrings for public classes/functions.
- Dataclasses for event payloads.
- Use monotonic time for timers/latency.
- Avoid global mutable state.
- Keep pure logic separated from IO/hardware adapters.
- Prefer dependency injection for camera, detector, mic, and speaker clients.

---

## 9) Suggested Execution Checklist for Agent

1. Scaffold repo and config/logging foundations.
2. Implement + test motion detector.
3. Implement + test object detector.
4. Build base state machine and standby->announce transitions.
5. Add announce LLM call + gating rules.
6. Implement conversation pipeline stubs end-to-end.
7. Replace stubs with real VAD/Vosk/streaming LLM/Piper adapters.
8. Implement presence + timeout exits.
9. Implement barge-in interruption guarantees.
10. Add resilience/retry logic.
11. Add install/service/logrotate assets.
12. Add performance validation scripts.
13. Finalize README with setup, models, runbook, and troubleshooting.
14. Run all gates; fix regressions; tag release candidate.

---

## 10) README Requirements (must be included)

README must cover:
- Hardware prerequisites.
- OS package install.
- Python setup and `requirements.txt` install.
- TFLite/Vosk/Piper model download paths.
- `.env` configuration reference.
- Run instructions for foreground mode.
- systemd deployment steps.
- Log file and fallback behavior.
- Test commands and performance validation commands.
- Known limitations and troubleshooting.

---

## 11) Definition of Done

The implementation is complete when all are true:
- All spec-required modules/artifacts exist and are wired.
- State behavior matches transitions and timeouts.
- ANNOUNCE gating rules enforced exactly.
- Conversation mode supports streaming + barge-in.
- Presence policy is configurable and tested.
- Service deploys as `jarvis:jarvis` and survives failures.
- Structured logging + fallback path implemented.
- Performance scripts produce pass/fail outputs per spec.
- README enables a clean setup by a new operator.

---

## 12) Pre-Deployment Completion Steps (Repo Review)

Based on current repository status (`README` indicates Slice 5), the following steps must be completed before production deployment:

1. **Finish deployment automation (`install.sh`)**
   - Replace placeholder logic with full installer flow:
     - install required OS packages,
     - create `jarvis` system group/user if absent,
     - create Python virtualenv and install `requirements.txt`,
     - create and permission `/var/log/jarvis.log` (`jarvis:jarvis`, `0640`),
     - install/copy `jarvis.service` and `jarvis.logrotate`,
     - run daemon reload + enable/restart service.

2. **Complete performance validation tooling**
   - Implement `scripts/validate_idle_cpu.sh` per spec (30s warm-up, 60 samples/run, 3 runs, per-run + overall mean).
   - Implement `scripts/validate_latency.py` to parse timing triplets and enforce pass/fail criteria (p95 < 3.0s, max <= 3.5s, no missing records).

3. **Close Slice 6/7 documentation and operator runbook gaps**
   - Expand `README.md` to include full setup + deployment documentation required in Section 10:
     - hardware/OS deps,
     - model downloads (TFLite/Vosk/Piper),
     - `.env` reference,
     - systemd deployment + operations,
     - logging + fallback behavior,
     - validation commands and thresholds,
     - troubleshooting and known limitations.

4. **Execute and record all quality/performance gates before release**
   - Run required code-quality/tests (`ruff`, `black --check`, `mypy`, `pytest -q`, smoke test).
   - Run additional release gates: simulated end-to-end transitions, Raspberry Pi device sanity run, service reboot persistence check.
   - Run performance validation scripts and archive evidence/results for release sign-off.

5. **Verify release readiness against Definition of Done**
   - Confirm all Section 11 criteria are demonstrably satisfied (module wiring, ANNOUNCE gating, streaming conversation + barge-in, presence policy, resilience, deploy artifacts, logging fallback, performance outputs, complete README).
   - Resolve any remaining TODO placeholders before tagging a deployable release.
