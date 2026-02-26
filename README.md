# SRCNet FaaS Benchmark Suite

A benchmark suite to measure latency and error behavior of SRCNet FaaS functions, covering:

- `baseline` with no load (1 client, 1 request every 1-2 s)
- `concurrency` for `1`, `10`, `50` concurrent users
- `cold_warm` to compare cold start vs warm behavior
- `local` to measure local `cpu_data` (no token required)
- latency percentiles `P50/P95/P99`
- plots: `concurrency vs P95`, `req/s vs errors`

## Requirements

- `python3` (3.9+ recommended)
- `curl`
- `SKA_TOKEN` environment variable (required for non-local scenarios)
- (optional for plots) `matplotlib`

Install optional plotting dependency:

```bash
python3 -m pip install -r benchmarks/requirements.txt
```

## Endpoint configuration

File: `benchmarks/config/endpoints.json`

Includes function types:

- `cpu_data`
- `nohup`

Included regions:

- `uk`, `sweden`, `spain`, `switzerland`, `italy`

## Quick run (full suite)

```bash
export SKA_TOKEN="<your_token>"
python3 benchmarks/run_benchmarks.py \
  --scenarios baseline,concurrency,cold_warm \
  --concurrency-levels 1,10,50
```

Results are written to `benchmarks/results/<run_id>/`:

- `raw.jsonl` (per-request samples)
- `summary.csv` (aggregated metrics)
- `summary.md` (readable table + cold/warm delta)
- `metadata.json`

## Recommended scenarios

### 1) Baseline latency (10-15 min)

```bash
python3 benchmarks/run_benchmarks.py \
  --scenarios baseline \
  --baseline-duration 900 \
  --baseline-interval-min 1 \
  --baseline-interval-max 2
```

### 2) Concurrency (1, 10, 50)

```bash
python3 benchmarks/run_benchmarks.py \
  --scenarios concurrency \
  --concurrency-levels 1,10,50 \
  --concurrency-duration 300
```

### 3) Cold vs warm

```bash
python3 benchmarks/run_benchmarks.py \
  --scenarios cold_warm \
  --warm-interval 5 \
  --warm-duration 300 \
  --idle-minutes 15,60 \
  --cold-repeats 20
```

Notes:

- `cold_warm` waits the full `15` and `60` minutes by default.
- For fast validation runs, use `--skip-idle-wait`.

### 4) Local CPU+data (no token)

```bash
python3 benchmarks/run_benchmarks.py \
  --scenarios local \
  --local-url http://localhost:8080/ska/datasets/soda \
  --local-source-url "https://gitlab.com/manuparra/test-data-faas/-/raw/main/PTF10tce.fits?inline=false" \
  --local-id "ivo://src.skao.org/datasets/fits?PTF10tce.fits" \
  --local-duration 600 \
  --local-interval-min 1 \
  --local-interval-max 2
```

Notes:

- Local scenario sends no `Authorization` header.
- Local scenario downloads the FITS source file before every request.
- It uses the same summary outputs (`summary.csv`, `summary.md`) so you can compare latency against remote runs.

Local concurrency (1/10/50):

```bash
python3 benchmarks/run_benchmarks.py \
  --scenarios concurrency \
  --function-types cpu_data \
  --regions local \
  --concurrency-levels 1,10,50 \
  --concurrency-duration 60 \
  --local-url http://localhost:8080/ska/datasets/soda \
  --local-source-url "https://gitlab.com/manuparra/test-data-faas/-/raw/main/PTF10tce.fits?inline=false" \
  --local-id "ivo://src.skao.org/datasets/fits?PTF10tce.fits"
```

## Filter by function type or region

Run only `nohup` in `uk` and `spain`:

```bash
python3 benchmarks/run_benchmarks.py \
  --function-types nohup \
  --regions uk,spain
```

## Plots

```bash
python3 benchmarks/plot_results.py benchmarks/results/<run_id>/summary.csv \
  --output-dir benchmarks/plots/<run_id>
```

## Multi-client locations (node A/B/C)

Run the benchmark on each client node, then copy each `summary.csv` to one host.

Merge:

```bash
python3 benchmarks/merge_runs.py \
  --input node_a=benchmarks/results/<runA>/summary.csv \
  --input node_b=benchmarks/results/<runB>/summary.csv \
  --input node_c=benchmarks/results/<runC>/summary.csv \
  --output benchmarks/results/multi_node_summary.csv
```

## Key output metrics

Fields in `summary.csv`:

- `scenario`, `phase`, `function_type`, `region`, `concurrency`, `idle_minutes`
- `requests`, `success`, `errors`, `error_rate`, `rps`
- `p50_s`, `p95_s`, `p99_s`, `mean_s`

`summary.md` also reports:

- `delta_p95_s = P95_cold - P95_warm`

## Suggested benchmark campaign

1. Node A: run the full suite.
2. Node B: run the same configuration.
3. Node C: run the same configuration.
4. Merge outputs with `merge_runs.py`.
5. Generate per-node and global plots.

## Warnings

- `cpu_data` downloads FITS files temporarily and removes them after each request.
- For high concurrency tests, check client OS/network limits before scaling.
