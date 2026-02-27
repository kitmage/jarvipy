#!/usr/bin/env bash
set -euo pipefail

WARMUP_SECONDS=30
RUNS=3
SAMPLES_PER_RUN=60

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <jarvis_pid>" >&2
  exit 2
fi

PID="$1"

if ! command -v pidstat >/dev/null 2>&1; then
  echo "pidstat not found. Install sysstat before running this validation." >&2
  exit 2
fi

if ! ps -p "${PID}" >/dev/null 2>&1; then
  echo "PID ${PID} is not running." >&2
  exit 2
fi

echo "Warming up for ${WARMUP_SECONDS}s..."
sleep "${WARMUP_SECONDS}"

declare -a means=()

for run in $(seq 1 "${RUNS}"); do
  echo "Run ${run}/${RUNS}: collecting ${SAMPLES_PER_RUN} samples..."
  output="$(pidstat -p "${PID}" -u 1 "${SAMPLES_PER_RUN}")"

  mean_cpu="$(printf '%s\n' "${output}" | awk -v pid="${PID}" '
    BEGIN {sum=0; count=0}
    $0 ~ /^[0-9]/ && $3 == pid {
      sum += $7 + $8
      count += 1
    }
    END {
      if (count == 0) {
        print "NaN"
      } else {
        printf "%.3f", sum / count
      }
    }
  ')"

  if [[ "${mean_cpu}" == "NaN" ]]; then
    echo "Unable to parse CPU samples for PID ${PID}." >&2
    exit 1
  fi

  means+=("${mean_cpu}")
  echo "Run ${run} mean CPU: ${mean_cpu}%"
done

overall_mean="$(printf '%s\n' "${means[@]}" | awk '
  BEGIN {sum=0; count=0}
  {sum += $1; count += 1}
  END {printf "%.3f", sum / count}
')"

echo "Per-run means: ${means[*]}"
echo "Overall mean CPU: ${overall_mean}%"
