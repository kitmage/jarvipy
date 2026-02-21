# Jarvis Pi

This repository is currently at **Slice 2** from `AGENT_INSTRUCTIONS.md`.

## Current status
- Slice 1 foundation: typed config, structured logging, startup health checks
- Implemented motion trigger core logic (6-frame consecutive trigger + cooldown)
- Implemented object detection interfaces and person/vehicle routing helper
- Implemented state machine motion routing (`STANDBY` -> `CONVERSATION` or `ANNOUNCE`)

## Run
```bash
python main.py
python scripts/smoke_test.py
pytest -q
```
