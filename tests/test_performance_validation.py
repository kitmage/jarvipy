import json
from pathlib import Path

from scripts.validate_latency import extract_samples, validate


def test_validate_idle_cpu_script_matches_slice7_requirements() -> None:
    content = Path("scripts/validate_idle_cpu.sh").read_text()
    assert "WARMUP_SECONDS=30" in content
    assert "RUNS=3" in content
    assert "SAMPLES_PER_RUN=60" in content
    assert "pidstat" in content
    assert "Overall mean CPU" in content


def test_latency_validation_passes_when_thresholds_met(tmp_path: Path) -> None:
    records = [
        {"metadata": {"t_start": 10.0, "t_llm_first": 10.2, "t_tts_start": 12.1}},
        {"metadata": {"t_start": 20.0, "t_llm_first": 20.2, "t_tts_start": 22.3}},
        {"metadata": {"t_start": 30.0, "t_llm_first": 30.3, "t_tts_start": 32.4}},
    ]
    log_path = tmp_path / "jarvis.log"
    log_path.write_text("\n".join(json.dumps(record) for record in records))

    samples, missing = extract_samples(log_path)
    result = validate(samples, missing)

    assert result.count == 3
    assert result.missing_records == 0
    assert result.p95 < 3.0
    assert result.max_latency <= 3.5
    assert result.passed


def test_latency_validation_fails_for_missing_triplets(tmp_path: Path) -> None:
    records = [
        {"metadata": {"t_start": 1.0, "t_llm_first": 1.2, "t_tts_start": 2.0}},
        {"metadata": {"t_start": 2.0, "t_llm_first": 2.2}},
    ]
    log_path = tmp_path / "jarvis.log"
    log_path.write_text("\n".join(json.dumps(record) for record in records))

    samples, missing = extract_samples(log_path)
    result = validate(samples, missing)

    assert result.count == 1
    assert result.missing_records == 1
    assert not result.passed


def test_latency_validation_rejects_non_monotonic_triplets(tmp_path: Path) -> None:
    records = [
        {"metadata": {"t_start": 1.0, "t_llm_first": 1.2, "t_tts_start": 2.0}},
        {"metadata": {"t_start": 3.0, "t_llm_first": 2.9, "t_tts_start": 3.4}},
        {"metadata": {"t_start": 4.0, "t_llm_first": 4.2, "t_tts_start": 3.8}},
    ]
    log_path = tmp_path / "jarvis.log"
    log_path.write_text("\n".join(json.dumps(record) for record in records))

    samples, missing = extract_samples(log_path)
    result = validate(samples, missing)

    assert result.count == 1
    assert result.missing_records == 2
    assert not result.passed
