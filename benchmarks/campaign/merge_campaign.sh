#!/usr/bin/env bash
set -euo pipefail

# Merge campaign summaries from node manifests into one CSV.
# Usage:
#   ./benchmarks/campaign/merge_campaign.sh --campaign-id 20260224_180000 --nodes node_a,node_b,node_c

usage() {
  cat <<USAGE
Usage:
  $(basename "$0") --campaign-id <id> --nodes <node_a,node_b,node_c> [--output <file>] [--python <python_bin>]

Options:
  --campaign-id  Required campaign id used during node runs
  --nodes        Required comma-separated node list
  --output       Optional output CSV path
  --python       Optional Python binary (default: python3)
USAGE
}

CAMPAIGN_ID=""
NODES=""
OUTPUT=""
PYTHON_BIN="python3"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --campaign-id)
      CAMPAIGN_ID="${2:-}"
      shift 2
      ;;
    --nodes)
      NODES="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --python)
      PYTHON_BIN="${2:-}"
      shift 2
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

if [[ -z "$CAMPAIGN_ID" || -z "$NODES" ]]; then
  echo "Error: --campaign-id and --nodes are required" >&2
  usage
  exit 1
fi

if [[ -z "$OUTPUT" ]]; then
  OUTPUT="benchmarks/results/campaign_${CAMPAIGN_ID}/multi_node_summary.csv"
fi

IFS=',' read -r -a NODE_ARRAY <<< "$NODES"

ARGS=()
for node in "${NODE_ARRAY[@]}"; do
  manifest="benchmarks/results/campaign_${CAMPAIGN_ID}/${node}/manifest.env"
  if [[ ! -f "$manifest" ]]; then
    echo "Missing manifest: $manifest" >&2
    exit 1
  fi

  # shellcheck disable=SC1090
  source "$manifest"

  for phase in BASELINE_SUMMARY CONCURRENCY_SUMMARY COLD_WARM_SUMMARY; do
    value="${!phase:-}"
    if [[ -n "$value" ]]; then
      ARGS+=("--input" "${node}=${value}")
    fi
  done
done

"$PYTHON_BIN" benchmarks/merge_runs.py "${ARGS[@]}" --output "$OUTPUT"
echo "Merged output: $OUTPUT"
