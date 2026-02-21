# Jarvis Pi

This repository is currently at **Slice 4** from `AGENT_INSTRUCTIONS.md`.

## Current status
- Slice 1 foundation: typed config, structured logging, startup health checks
- Slice 2 foundation: motion trigger core + detector contracts + state routing
- Slice 3 foundation: ANNOUNCE gating rules + strict LLM JSON parsing + TTS playback hooks
- Slice 4 foundation: conversation turn pipeline, rolling memory, and presence-policy tracking

## Run
```bash
python main.py
python scripts/smoke_test.py
pytest -q
```
