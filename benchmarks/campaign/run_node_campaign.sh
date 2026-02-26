#!/usr/bin/env bash
set -euo pipefail

# Run a SRCNet FaaS benchmark campaign from one client node.
# Output: benchmarks/results/campaign_<campaign_id>/<node_name>/

usage() {
  cat <<USAGE
Usage:
  $(basename "$0") --node <node_name> [--campaign-id <id>] [--suite <main|cold_warm|all>] [--python <python_bin>] [--quick]

Options:
  --node         Required. Client node label (e.g. node_a, node_b, node_c)
  --campaign-id  Optional. Campaign identifier. Default: UTC timestamp YYYYMMDD_HHMMSS
  --suite        Optional. Which suite to run. Default: main
                 main      => baseline + concurrency (fits under ~1h)
                 cold_warm => cold vs warm only (fits under ~1h)
                 all       => main + cold_warm (requires token refresh handling by operator)
  --python       Optional. Python binary. Default: python3
  --quick        Optional. Fast validation run (short durations, no idle wait)

Environment:
  SKA_TOKEN      Required bearer token
USAGE
}

NODE_NAME=""
CAMPAIGN_ID=""
PYTHON_BIN="python3"
QUICK_MODE="false"
SUITE="main"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --node)
      NODE_NAME="${2:-}"
      shift 2
      ;;
    --campaign-id)
      CAMPAIGN_ID="${2:-}"
      shift 2
      ;;
    --suite)
      SUITE="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --quick)
      QUICK_MODE="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$NODE_NAME" ]]; then
  echo "Error: --node is required" >&2
  usage
  exit 1
fi

if [[ "$SUITE" != "main" && "$SUITE" != "cold_warm" && "$SUITE" != "all" ]]; then
  echo "Error: --suite must be one of: main, cold_warm, all" >&2
  usage
  exit 1
fi

if [[ -z "${SKA_TOKEN:-}" ]]; then
  echo "Error: SKA_TOKEN is required" >&2
  exit 1
fi

if [[ -z "$CAMPAIGN_ID" ]]; then
  CAMPAIGN_ID="$(date -u +%Y%m%d_%H%M%S)"
fi

ROOT_DIR="benchmarks/results/campaign_${CAMPAIGN_ID}/${NODE_NAME}"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "$LOG_DIR"

MANIFEST="${ROOT_DIR}/manifest.env"
: > "$MANIFEST"

echo "CAMPAIGN_ID=${CAMPAIGN_ID}" >> "$MANIFEST"
echo "NODE_NAME=${NODE_NAME}" >> "$MANIFEST"
echo "SUITE=${SUITE}" >> "$MANIFEST"
echo "STARTED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MANIFEST"

run_phase() {
  local phase="$1"
  shift

  local phase_log="${LOG_DIR}/${phase}.log"
  local phase_json="${LOG_DIR}/${phase}_metadata.json"

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting phase: ${phase}" | tee -a "$phase_log"

  "$PYTHON_BIN" benchmarks/run_benchmarks.py "$@" | tee "$phase_json" >> "$phase_log"

  local summary_path
  summary_path="$($PYTHON_BIN -c 'import json,sys; print(json.load(open(sys.argv[1]))["summary"])' "$phase_json")"
  local raw_path
  raw_path="$($PYTHON_BIN -c 'import json,sys; print(json.load(open(sys.argv[1]))["raw"])' "$phase_json")"

  echo "${phase^^}_SUMMARY=${summary_path}" >> "$MANIFEST"
  echo "${phase^^}_RAW=${raw_path}" >> "$MANIFEST"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Finished phase: ${phase}" | tee -a "$phase_log"
}

run_main_suite() {
  if [[ "$QUICK_MODE" == "true" ]]; then
    run_phase baseline \
      --results-dir "$ROOT_DIR" \
      --scenarios baseline \
      --baseline-duration 60 \
      --baseline-interval-min 1 \
      --baseline-interval-max 2

    run_phase concurrency \
      --results-dir "$ROOT_DIR" \
      --scenarios concurrency \
      --concurrency-levels 1,10,50 \
      --concurrency-duration 30
  else
    # ~50 minutes for 10 targets (kept under 1h token lifetime)
    run_phase baseline \
      --results-dir "$ROOT_DIR" \
      --scenarios baseline \
      --baseline-duration 120 \
      --baseline-interval-min 1 \
      --baseline-interval-max 2

    run_phase concurrency \
      --results-dir "$ROOT_DIR" \
      --scenarios concurrency \
      --concurrency-levels 1,10,50 \
      --concurrency-duration 60
  fi
}

run_cold_warm_suite() {
  if [[ "$QUICK_MODE" == "true" ]]; then
    run_phase cold_warm \
      --results-dir "$ROOT_DIR" \
      --scenarios cold_warm \
      --warm-interval 3 \
      --warm-duration 20 \
      --idle-minutes 1 \
      --cold-repeats 3 \
      --skip-idle-wait
  else
    # ~25-30 minutes for 10 targets (kept under 1h token lifetime)
    run_phase cold_warm \
      --results-dir "$ROOT_DIR" \
      --scenarios cold_warm \
      --warm-interval 3 \
      --warm-duration 30 \
      --idle-minutes 2 \
      --cold-repeats 5
  fi
}

if [[ "$SUITE" == "main" ]]; then
  run_main_suite
elif [[ "$SUITE" == "cold_warm" ]]; then
  run_cold_warm_suite
else
  run_main_suite
  run_cold_warm_suite
fi

echo "ENDED_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$MANIFEST"
echo "Manifest: $MANIFEST"
echo "Campaign on ${NODE_NAME} finished"
