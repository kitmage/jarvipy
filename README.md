# Jarvis Pi

This repository is currently at **Slice 7** from `AGENT_INSTRUCTIONS.md`.

## Current status
- Slice 1 foundation: typed config, structured logging, startup health checks.
- Slice 2 foundation: motion trigger core + detector contracts + state routing.
- Slice 3 foundation: ANNOUNCE gating rules + strict LLM JSON parsing + TTS playback hooks.
- Slice 4 foundation: conversation turn pipeline, rolling memory, and presence-policy tracking.
- Slice 5 foundation: recoverable-failure retry primitives and resilient subsystem loop behavior.
- Slice 6 foundation: install/deploy artifacts for systemd service and log rotation.
- Slice 7 foundation: performance validation scripts and operator runbook hardening.

## Hardware prerequisites
- Raspberry Pi 4/5 class device (4GB+ recommended).
- USB microphone.
- Speaker or audio HAT output device.
- Camera module or USB camera.

## OS dependencies
Install baseline packages (Debian/Raspberry Pi OS):

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip libatlas-base-dev libportaudio2 ffmpeg logrotate sysstat
```

## Python setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Models and local assets
Place required models in local paths referenced by your `.env` values:
- TFLite detection model + labels for `vision/detect_objects.py`.
- Vosk speech model for STT.
- Piper voice model for TTS.

> This repo provides integration contracts and control logic. You must supply model files specific to your deployment.

## Configuration (`.env`)
Create `.env` in the repository root (or in `/opt/jarvis-pi/.env` for systemd) with values for:
- detector/model paths
- quiet-hour window
- announce thresholds
- conversation presence policy
- LLM provider credentials/endpoints

See `infra/config.py` for all supported environment variables and defaults.

## Run locally
```bash
python main.py
python scripts/smoke_test.py
pytest -q
```

## Deployment with systemd
Install as root using the included installer:

```bash
sudo ./install.sh
```

The installer:
- installs OS and Python dependencies,
- creates `jarvis:jarvis` system account,
- syncs app into `/opt/jarvis-pi` (configurable with `INSTALL_DIR`),
- creates `/var/log/jarvis.log` with `0640` permissions,
- installs `jarvis.service` and `jarvis.logrotate`,
- enables and restarts the service.

## Operations and logs
- Primary log: `/var/log/jarvis.log`
- Fallback log path on permission/open failure: `/tmp/jarvis.log`
- Service status:

```bash
sudo systemctl status jarvis.service
sudo journalctl -u jarvis.service -f
```

## Validation and quality gates
Before release, run:

```bash
ruff check .
black --check .
mypy .
pytest -q
python scripts/smoke_test.py
```

Performance validation:

```bash
# Idle CPU: pass running Jarvis PID
scripts/validate_idle_cpu.sh <jarvis_pid>

# Latency: evaluates p95 and max thresholds from structured logs
python scripts/validate_latency.py /var/log/jarvis.log
```

Latency pass criteria enforced by `validate_latency.py`:
- p95(`t_tts_start - t_start`) < 3.0s
- max(`t_tts_start - t_start`) <= 3.5s
- no missing timing triplets

## Known limitations
- Hardware adapters are interface-first; production audio/vision backends require deployment-specific tuning.
- Performance scripts assume Linux tooling (`pidstat`) and structured logs are available.
- End-to-end Raspberry Pi hardware validation remains required before release tagging.

## Troubleshooting
- **Installer fails on `pidstat`/`sysstat` checks**: ensure `sysstat` package is installed.
- **Service starts but no logs appear in `/var/log`**: check journald output; app may have fallen back to `/tmp/jarvis.log` due to permissions.
- **Latency validation reports missing records**: confirm conversation turn events emit all `t_start`, `t_llm_first`, and `t_tts_start` fields.
