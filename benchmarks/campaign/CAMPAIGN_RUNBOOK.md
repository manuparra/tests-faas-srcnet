# Exact Benchmark Campaign Runbook (1h token-safe)

This runbook executes the benchmark matrix from 3 client locations (`node_a`, `node_b`, `node_c`) while respecting a 1-hour token lifetime.

## 1) Scope and matrix

Targets:

- Function types: `nohup`, `cpu_data`
- Regions: `uk`, `sweden`, `spain`, `switzerland`, `italy`

Execution is split into 2 independent suites:

- `main` suite: baseline + concurrency
- `cold_warm` suite: cold vs warm only

Default timings are reduced so each suite can finish within one token window.

## 2) Timings per suite (default)

Per target:

- Main suite:
  - Baseline: 1 request every 1-2 s, 120 s
  - Concurrency: 1, 10, 50 users, 60 s per level
- Cold/warm suite:
  - Warm: every 3 s for 30 s
  - Idle: 2 min
  - Cold: 5 requests

Approximate runtime per node:

- Main suite: ~50 min
- Cold/warm suite: ~25-30 min

## 3) Pre-flight on each node

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
python3 --version
curl --version
```

Set token:

```bash
export SKA_TOKEN="<your_token>"
```

Optional (plots later):

```bash
python3 -m pip install -r benchmarks/requirements.txt
```

## 4) Pick one shared campaign ID

Use one campaign id for all nodes and both suites:

```bash
export CAMPAIGN_ID="20260224_180000"
```

## 5) Run suite 1: main (baseline + concurrency)

### Node A

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
nohup ./benchmarks/campaign/run_node_campaign.sh \
  --node node_a \
  --campaign-id "$CAMPAIGN_ID" \
  --suite main \
  > benchmarks/results/campaign_${CAMPAIGN_ID}_node_a_main.out 2>&1 &
```

### Node B

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
nohup ./benchmarks/campaign/run_node_campaign.sh \
  --node node_b \
  --campaign-id "$CAMPAIGN_ID" \
  --suite main \
  > benchmarks/results/campaign_${CAMPAIGN_ID}_node_b_main.out 2>&1 &
```

### Node C

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
nohup ./benchmarks/campaign/run_node_campaign.sh \
  --node node_c \
  --campaign-id "$CAMPAIGN_ID" \
  --suite main \
  > benchmarks/results/campaign_${CAMPAIGN_ID}_node_c_main.out 2>&1 &
```

Monitor:

```bash
tail -f benchmarks/results/campaign_${CAMPAIGN_ID}_node_a_main.out
```

## 6) Refresh token and run suite 2: cold_warm

After main finishes, get a fresh token on each node:

```bash
export SKA_TOKEN="<new_token>"
```

### Node A

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
nohup ./benchmarks/campaign/run_node_campaign.sh \
  --node node_a \
  --campaign-id "$CAMPAIGN_ID" \
  --suite cold_warm \
  > benchmarks/results/campaign_${CAMPAIGN_ID}_node_a_coldwarm.out 2>&1 &
```

### Node B

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
nohup ./benchmarks/campaign/run_node_campaign.sh \
  --node node_b \
  --campaign-id "$CAMPAIGN_ID" \
  --suite cold_warm \
  > benchmarks/results/campaign_${CAMPAIGN_ID}_node_b_coldwarm.out 2>&1 &
```

### Node C

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
nohup ./benchmarks/campaign/run_node_campaign.sh \
  --node node_c \
  --campaign-id "$CAMPAIGN_ID" \
  --suite cold_warm \
  > benchmarks/results/campaign_${CAMPAIGN_ID}_node_c_coldwarm.out 2>&1 &
```

## 7) Merge node results

Run on a host with all node outputs:

```bash
cd /Users/manuparra/repos/tests-faas-srcnet
./benchmarks/campaign/merge_campaign.sh \
  --campaign-id "$CAMPAIGN_ID" \
  --nodes node_a,node_b,node_c
```

Merged CSV:

- `benchmarks/results/campaign_<campaign_id>/multi_node_summary.csv`

## 8) Generate plots

```bash
python3 benchmarks/plot_results.py benchmarks/results/campaign_${CAMPAIGN_ID}/multi_node_summary.csv \
  --output-dir benchmarks/plots/campaign_${CAMPAIGN_ID}
```

## 9) Quick validation mode

Main quick run:

```bash
./benchmarks/campaign/run_node_campaign.sh --node node_a --campaign-id test_quick --suite main --quick
```

Cold/warm quick run:

```bash
./benchmarks/campaign/run_node_campaign.sh --node node_a --campaign-id test_quick --suite cold_warm --quick
```

## 10) Deliverables checklist

- Per node: baseline/concurrency summaries (main suite)
- Per node: cold_warm summary (cold_warm suite)
- Combined multi-node CSV
- `Concurrency vs P95` plots
- `Req/s vs errors` plots
- Cold vs warm delta from `summary.md` (`delta_p95_s`)
