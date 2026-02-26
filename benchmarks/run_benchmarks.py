#!/usr/bin/env python3
import argparse
import asyncio
import csv
import json
import os
import random
import shlex
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DATASET_ID = "ivo://auth.example.org/datasets/fits?testing/5b/f5/PTF10tce.fits"
CIRCLE = "351.986728 8.778684 0.01"
RESPONSE_FORMAT = "application/fits"
LOCAL_SOURCE_URL = "https://gitlab.com/manuparra/test-data-faas/-/raw/main/PTF10tce.fits?inline=false"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


@dataclass
class EndpointTarget:
    function_type: str
    region: str
    url: str
    auth_required: bool = True
    request_params: Optional[Dict[str, str]] = None
    local_source_url: str = LOCAL_SOURCE_URL


class CurlInvoker:
    def __init__(self, ska_token: str, tmp_dir: Path):
        self.ska_token = ska_token
        self.tmp_dir = tmp_dir
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    async def _download_local_source(self, source_url: str, destination: Path) -> Dict[str, Any]:
        cmd = [
            "curl",
            "-sS",
            "-L",
            "--fail",
            "-o",
            str(destination),
            source_url,
        ]
        started = time.time()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        finished = time.time()
        return {
            "ok": proc.returncode == 0,
            "duration_s": finished - started,
            "stderr": stderr.decode("utf-8", errors="replace").strip(),
            "cmd": " ".join(shlex.quote(x) for x in cmd),
        }

    async def invoke(self, target: EndpointTarget) -> Dict[str, Any]:
        started = time.time()
        cmd = [
            "curl",
            "-s",
            "-k",
            "--get",
            "-w",
            "__CURL_META__ %{http_code} %{time_total} %{size_download}",
        ]
        if target.auth_required:
            cmd.extend(["-H", f"Authorization: Bearer {self.ska_token}"])

        output_file = None
        prefetch_duration_s = 0.0
        if target.function_type == "cpu_data":
            params = target.request_params or {
                "ID": DATASET_ID,
                "CIRCLE": CIRCLE,
                "RESPONSE_FORMAT": RESPONSE_FORMAT,
            }
            if target.region == "local":
                # Local benchmark requires downloading the FITS file before every invocation.
                local_source = self.tmp_dir / f"local_input_{uuid.uuid4().hex}.fits"
                prefetch = await self._download_local_source(target.local_source_url, local_source)
                prefetch_duration_s = float(prefetch["duration_s"])
                if not prefetch["ok"]:
                    finished = time.time()
                    return {
                        "ts_start": started,
                        "ts_end": finished,
                        "timestamp": utc_now_iso(),
                        "duration_s": finished - started,
                        "request_duration_s": 0.0,
                        "prefetch_duration_s": prefetch_duration_s,
                        "http_code": "000",
                        "bytes": 0,
                        "curl_rc": 1,
                        "success": False,
                        "error": f"local_prefetch_failed: {prefetch['stderr'] or 'unknown error'}",
                        "stderr": prefetch["stderr"],
                        "stdout_sample": "",
                        "cmd": "<local_prefetch_failed>",
                    }
                try:
                    local_source.unlink()
                except OSError:
                    pass

            output_file = self.tmp_dir / f"{target.region}_{uuid.uuid4().hex}.fits"
            cmd.extend(
                [
                    "--data-urlencode",
                    f"ID={params['ID']}",
                    "--data-urlencode",
                    f"CIRCLE={params['CIRCLE']}",
                    "--data-urlencode",
                    f"RESPONSE_FORMAT={params['RESPONSE_FORMAT']}",
                    "-o",
                    str(output_file),
                ]
            )
        else:
            cmd.extend(["-o", "/dev/null"])

        cmd.append(target.url)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        finished = time.time()

        if output_file is not None and output_file.exists():
            try:
                output_file.unlink()
            except OSError:
                pass

        stdout_s = stdout.decode("utf-8", errors="replace")
        stderr_s = stderr.decode("utf-8", errors="replace")
        http_code = "000"
        time_total = None
        bytes_downloaded = 0

        marker = "__CURL_META__"
        if marker in stdout_s:
            body, meta = stdout_s.rsplit(marker, 1)
            meta_parts = meta.strip().split()
            if len(meta_parts) >= 3:
                http_code = meta_parts[0]
                try:
                    time_total = float(meta_parts[1])
                except ValueError:
                    time_total = finished - started
                try:
                    bytes_downloaded = int(float(meta_parts[2]))
                except ValueError:
                    bytes_downloaded = 0
            stdout_s = body

        success = proc.returncode == 0 and http_code.startswith(("2", "3"))
        error = None
        if not success:
            error = stderr_s.strip() or f"http_code={http_code}"

        safe_cmd_parts = list(cmd[:-1])
        for i, part in enumerate(safe_cmd_parts):
            if part == "-H" and i + 1 < len(safe_cmd_parts):
                header = safe_cmd_parts[i + 1]
                if header.startswith("Authorization: Bearer "):
                    safe_cmd_parts[i + 1] = "Authorization: Bearer <REDACTED>"

        return {
            "ts_start": started,
            "ts_end": finished,
            "timestamp": utc_now_iso(),
            "duration_s": prefetch_duration_s + (time_total if time_total is not None else (finished - started - prefetch_duration_s)),
            "request_duration_s": time_total if time_total is not None else max(0.0, (finished - started - prefetch_duration_s)),
            "prefetch_duration_s": prefetch_duration_s,
            "http_code": http_code,
            "bytes": bytes_downloaded,
            "curl_rc": proc.returncode,
            "success": success,
            "error": error,
            "stderr": stderr_s.strip(),
            "stdout_sample": stdout_s[:200],
            "cmd": " ".join(shlex.quote(x) for x in safe_cmd_parts) + " <URL>",
        }


def load_targets(config_path: Path) -> List[EndpointTarget]:
    data = json.loads(config_path.read_text())
    targets: List[EndpointTarget] = []
    for function_type, regions in data.items():
        for region, url in regions.items():
            targets.append(EndpointTarget(function_type=function_type, region=region, url=url))
    return targets


def pick_targets(targets: Iterable[EndpointTarget], function_types: List[str], regions: List[str]) -> List[EndpointTarget]:
    out = []
    for t in targets:
        if function_types and t.function_type not in function_types:
            continue
        if regions and t.region not in regions:
            continue
        out.append(t)
    return out


async def run_baseline(
    invoker: CurlInvoker,
    target: EndpointTarget,
    duration_sec: int,
    interval_min: float,
    interval_max: float,
    scenario_name: str,
    sink,
) -> int:
    deadline = time.time() + duration_sec
    req = 0
    while time.time() < deadline:
        rec = await invoker.invoke(target)
        rec.update(
            {
                "scenario": scenario_name,
                "function_type": target.function_type,
                "region": target.region,
                "url": target.url,
                "concurrency": 1,
                "worker_id": 0,
                "request_id": req,
            }
        )
        sink.write(json.dumps(rec) + "\n")
        req += 1
        await asyncio.sleep(random.uniform(interval_min, interval_max))
    return req


async def _worker_loop(
    invoker: CurlInvoker,
    target: EndpointTarget,
    stop_at: float,
    worker_id: int,
    concurrency: int,
    sink,
    scenario: str,
) -> int:
    count = 0
    while time.time() < stop_at:
        rec = await invoker.invoke(target)
        rec.update(
            {
                "scenario": scenario,
                "function_type": target.function_type,
                "region": target.region,
                "url": target.url,
                "concurrency": concurrency,
                "worker_id": worker_id,
                "request_id": count,
            }
        )
        sink.write(json.dumps(rec) + "\n")
        count += 1
    return count


async def run_concurrency(invoker: CurlInvoker, target: EndpointTarget, concurrency: int, duration_sec: int, sink) -> int:
    stop_at = time.time() + duration_sec
    tasks = [
        asyncio.create_task(
            _worker_loop(
                invoker,
                target,
                stop_at,
                worker_id=i,
                concurrency=concurrency,
                sink=sink,
                scenario="concurrency",
            )
        )
        for i in range(concurrency)
    ]
    counts = await asyncio.gather(*tasks)
    return sum(counts)


async def run_cold_warm(
    invoker: CurlInvoker,
    target: EndpointTarget,
    warm_interval_sec: float,
    warm_duration_sec: int,
    idle_minutes: List[int],
    cold_repeats: int,
    do_idle_wait: bool,
    sink,
) -> int:
    total = 0
    warm_deadline = time.time() + warm_duration_sec
    while time.time() < warm_deadline:
        rec = await invoker.invoke(target)
        rec.update(
            {
                "scenario": "cold_warm",
                "phase": "warm",
                "idle_minutes": 0,
                "function_type": target.function_type,
                "region": target.region,
                "url": target.url,
                "concurrency": 1,
                "worker_id": 0,
                "request_id": total,
            }
        )
        sink.write(json.dumps(rec) + "\n")
        total += 1
        await asyncio.sleep(warm_interval_sec)

    for idle in idle_minutes:
        if do_idle_wait:
            await asyncio.sleep(idle * 60)
        for i in range(cold_repeats):
            rec = await invoker.invoke(target)
            rec.update(
                {
                    "scenario": "cold_warm",
                    "phase": "cold",
                    "idle_minutes": idle,
                    "function_type": target.function_type,
                    "region": target.region,
                    "url": target.url,
                    "concurrency": 1,
                    "worker_id": 0,
                    "request_id": i,
                }
            )
            sink.write(json.dumps(rec) + "\n")
            total += 1
    return total


def summarize(records: List[Dict[str, Any]], output_dir: Path) -> Path:
    rows = []
    grouped: Dict[tuple, List[Dict[str, Any]]] = {}
    for r in records:
        key = (
            r.get("scenario", ""),
            r.get("phase", ""),
            r.get("function_type", ""),
            r.get("region", ""),
            int(r.get("concurrency", 1)),
            int(r.get("idle_minutes", 0)),
        )
        grouped.setdefault(key, []).append(r)

    for key, sample in grouped.items():
        durations = [float(x["duration_s"]) for x in sample if x.get("success")]
        success = sum(1 for x in sample if x.get("success"))
        errors = len(sample) - success
        span = 0.0
        if sample:
            span = max(x["ts_end"] for x in sample) - min(x["ts_start"] for x in sample)
        rps = (len(sample) / span) if span > 0 else 0.0

        rows.append(
            {
                "scenario": key[0],
                "phase": key[1],
                "function_type": key[2],
                "region": key[3],
                "concurrency": key[4],
                "idle_minutes": key[5],
                "requests": len(sample),
                "success": success,
                "errors": errors,
                "error_rate": round((errors / len(sample)) if sample else 0.0, 6),
                "rps": round(rps, 4),
                "p50_s": round(percentile(durations, 0.50) or 0.0, 6),
                "p95_s": round(percentile(durations, 0.95) or 0.0, 6),
                "p99_s": round(percentile(durations, 0.99) or 0.0, 6),
                "mean_s": round(statistics.fmean(durations), 6) if durations else 0.0,
            }
        )

    summary_csv = output_dir / "summary.csv"
    with summary_csv.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [
            "scenario", "phase", "function_type", "region", "concurrency", "idle_minutes",
            "requests", "success", "errors", "error_rate", "rps", "p50_s", "p95_s", "p99_s", "mean_s"
        ])
        writer.writeheader()
        if rows:
            writer.writerows(rows)

    md = output_dir / "summary.md"
    with md.open("w") as fh:
        fh.write("# Benchmark summary\n\n")
        if not rows:
            fh.write("No data collected.\n")
        else:
            headers = ["scenario", "phase", "function_type", "region", "concurrency", "idle_minutes", "requests", "errors", "rps", "p50_s", "p95_s", "p99_s"]
            fh.write("| " + " | ".join(headers) + " |\n")
            fh.write("|" + "|".join(["---"] * len(headers)) + "|\n")
            for row in rows:
                fh.write("| " + " | ".join(str(row[h]) for h in headers) + " |\n")

            fh.write("\n## Cold vs warm delta\n\n")
            warm = {}
            cold = {}
            for row in rows:
                key = (row["function_type"], row["region"])
                if row["scenario"] == "cold_warm" and row["phase"] == "warm":
                    warm[key] = row
                if row["scenario"] == "cold_warm" and row["phase"] == "cold":
                    cold.setdefault((key, row["idle_minutes"]), row)
            fh.write("| function_type | region | idle_minutes | delta_p95_s |\n")
            fh.write("|---|---|---:|---:|\n")
            for (key, idle), c in sorted(cold.items()):
                w = warm.get(key)
                if not w:
                    continue
                delta = c["p95_s"] - w["p95_s"]
                fh.write(f"| {key[0]} | {key[1]} | {idle} | {delta:.6f} |\n")

    return summary_csv


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SRCNet FaaS benchmark suite")
    p.add_argument("--config", default="benchmarks/config/endpoints.json")
    p.add_argument("--results-dir", default="benchmarks/results")
    p.add_argument("--tmp-dir", default="/tmp/srcnet-bench")
    p.add_argument("--function-types", default="nohup,cpu_data", help="Comma list")
    p.add_argument("--regions", default="", help="Comma list")
    p.add_argument("--scenarios", default="baseline,concurrency,cold_warm", help="Comma list")

    p.add_argument("--baseline-duration", type=int, default=600)
    p.add_argument("--baseline-interval-min", type=float, default=1.0)
    p.add_argument("--baseline-interval-max", type=float, default=2.0)

    p.add_argument("--concurrency-levels", default="1,10,50")
    p.add_argument("--concurrency-duration", type=int, default=300)

    p.add_argument("--warm-interval", type=float, default=5.0)
    p.add_argument("--warm-duration", type=int, default=300)
    p.add_argument("--idle-minutes", default="15,60")
    p.add_argument("--cold-repeats", type=int, default=20)
    p.add_argument("--skip-idle-wait", action="store_true", help="Do not sleep during cold idle windows")

    p.add_argument("--local-url", default="http://localhost:8080/ska/datasets/soda")
    p.add_argument("--local-source-url", default=LOCAL_SOURCE_URL)
    p.add_argument("--local-id", default="ivo://src.skao.org/datasets/fits?PTF10tce.fits")
    p.add_argument("--local-circle", default="351.986728 8.778684 0.01")
    p.add_argument("--local-response-format", default="application/fits")
    p.add_argument("--local-duration", type=int, default=600)
    p.add_argument("--local-interval-min", type=float, default=1.0)
    p.add_argument("--local-interval-max", type=float, default=2.0)

    return p.parse_args()


async def main_async(args: argparse.Namespace) -> int:
    ska_token = os.getenv("SKA_TOKEN", "")

    function_types_filter = [x for x in args.function_types.split(",") if x]
    regions_filter = [x for x in args.regions.split(",") if x]

    targets = load_targets(Path(args.config))
    selected = pick_targets(
        targets,
        function_types_filter,
        regions_filter,
    )
    scenario_set = {x for x in args.scenarios.split(",") if x}

    local_target = None
    local_requested = ("local" in scenario_set) or ("local" in regions_filter)
    local_type_allowed = (not function_types_filter) or ("cpu_data" in function_types_filter)
    if local_requested and local_type_allowed:
        local_target = EndpointTarget(
            function_type="cpu_data",
            region="local",
            url=args.local_url,
            auth_required=False,
            request_params={
                "ID": args.local_id,
                "CIRCLE": args.local_circle,
                "RESPONSE_FORMAT": args.local_response_format,
            },
            local_source_url=args.local_source_url,
        )

    remote_scenarios = {"baseline", "concurrency", "cold_warm"}
    wants_remote = any(s in scenario_set for s in remote_scenarios)

    if wants_remote and not selected:
        if local_target is None:
            raise SystemExit("No endpoints selected")
    if not wants_remote and not local_target:
        raise SystemExit("No endpoints selected")

    if wants_remote and any(t.auth_required for t in selected) and not ska_token:
        raise SystemExit("SKA_TOKEN is required for non-local endpoints")

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.results_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "raw.jsonl"

    invoker = CurlInvoker(ska_token=ska_token, tmp_dir=Path(args.tmp_dir))

    total_requests = 0

    with raw_path.open("w") as sink:
        run_targets = list(selected)
        if local_target is not None:
            run_targets.append(local_target)

        for target in run_targets:
            run_local_baseline = (target.region == "local" and "local" in scenario_set)
            if "baseline" in scenario_set or run_local_baseline:
                total_requests += await run_baseline(
                    invoker=invoker,
                    target=target,
                    duration_sec=args.local_duration if run_local_baseline else args.baseline_duration,
                    interval_min=args.local_interval_min if run_local_baseline else args.baseline_interval_min,
                    interval_max=args.local_interval_max if run_local_baseline else args.baseline_interval_max,
                    scenario_name="local" if run_local_baseline else "baseline",
                    sink=sink,
                )

            if "concurrency" in scenario_set:
                for c in [int(x) for x in args.concurrency_levels.split(",") if x]:
                    total_requests += await run_concurrency(
                        invoker=invoker,
                        target=target,
                        concurrency=c,
                        duration_sec=args.concurrency_duration,
                        sink=sink,
                    )

            if "cold_warm" in scenario_set:
                total_requests += await run_cold_warm(
                    invoker=invoker,
                    target=target,
                    warm_interval_sec=args.warm_interval,
                    warm_duration_sec=args.warm_duration,
                    idle_minutes=[int(x) for x in args.idle_minutes.split(",") if x],
                    cold_repeats=args.cold_repeats,
                    do_idle_wait=not args.skip_idle_wait,
                    sink=sink,
                )

    records = []
    with raw_path.open() as fh:
        for line in fh:
            if line.strip():
                records.append(json.loads(line))

    summary_csv = summarize(records, out_dir)

    meta = {
        "run_id": run_id,
        "started_at_utc": utc_now_iso(),
        "requests_total": total_requests,
        "targets": [t.__dict__ for t in run_targets],
        "args": vars(args),
        "raw": str(raw_path),
        "summary": str(summary_csv),
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
