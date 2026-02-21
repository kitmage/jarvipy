# AGENT_LOG

## Execution Log

### Step 1 - Scaffold + config + logging + health checks
- Started implementation of Slice 1 from `AGENT_INSTRUCTIONS.md`.
- Created the required repository/module structure and package initializers.
- Added initial `infra/config.py` with typed settings, validation, and quiet-hours helper.
- Added initial `infra/logging.py` with JSON logs and fallback log path.
- Added `main.py` startup health checks and a smoke-test entry point.
- Added baseline test scaffolding to validate config and state controller behavior.

### Step 2 - Vision standby loop (motion + object detection) + state machine core
- Replaced placeholder motion module with concrete trigger logic and OpenCV-backed watcher scaffold.
- Added `MotionTrigger` unit-testable core for 6-consecutive-frame threshold and cooldown behavior.
- Replaced placeholder object detection module with normalized `Detection` model, detector protocol, and person/vehicle helper.
- Upgraded state controller to process motion signals via detector dependency and route to `ANNOUNCE` vs `CONVERSATION`.
- Added tests for motion trigger behavior, object detection parsing/filtering, and state machine routing decisions.

### Step 3 - ANNOUNCE mode with gating + LLM JSON response + TTS playback
- Added strict ANNOUNCE LLM JSON parser in `brain/llm.py` (`say` + `priority` validation).
- Added TTS protocol and in-memory adapter in `audio/tts.py` for deterministic tests.
- Extended `state/state_machine.py` with `process_announce` gating flow:
  - quiet-hours suppression
  - top non-person confidence threshold check
  - repeated-object-in-window or high-priority gate
  - invalid LLM JSON fallback to silent skip
- Added table-driven ANNOUNCE gating tests and LLM JSON robustness tests.

### Step 4 - CONVERSATION mode (VAD/STT/LLM/TTS streaming) + presence policy
- Implemented `ConversationMemory` with rolling max-10 exchange truncation in `brain/memory.py`.
- Added VAD/STT streaming contracts in `audio/vad.py` and `audio/stt.py`.
- Extended LLM contract with streaming conversation support in `brain/llm.py`.
- Extended `StateController` with conversation methods:
  - `start_conversation()` greeting
  - `process_conversation_turn()` with LLM chunk streaming aggregation, TTS output, and turn timing fields (`t_start`, `t_llm_first`, `t_tts_start`)
- Added `PresenceTracker` with configurable confidence threshold, misses-required counting, keepalive mode handling (`person_or_vehicle` / `person_only`), and 20-second absence exit condition.
- Added tests for memory truncation, deterministic presence policy timeline, keepalive-mode behavior, and conversation turn integration.

### Step 5 - Resilience and recovery behavior
- Added explicit recoverable exception classes for camera, LLM, and audio device failures in `infra/errors.py`.
- Implemented retry/backoff primitives in `infra/recovery.py` with bounded exponential backoff and recoverable-error filtering.
- Extended `main.py` with a resilient subsystem cycle that retries camera/audio/llm ticks and logs recoverable exhaustion without crashing startup.
- Added fault-injection resilience tests validating transient recovery, retry exhaustion behavior, and per-subsystem retry in `run_resilient_cycle`.
