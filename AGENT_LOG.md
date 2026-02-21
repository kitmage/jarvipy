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
