#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def load_rows(summary_csv: Path):
    with summary_csv.open() as fh:
        return list(csv.DictReader(fh))


def to_float(v: str) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def to_int(v: str) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def plot_concurrency_vs_p95(rows, out_dir: Path):
    import matplotlib.pyplot as plt

    by_key = {}
    for r in rows:
        if r.get("scenario") != "concurrency":
            continue
        key = (r.get("function_type", ""), r.get("region", ""))
        by_key.setdefault(key, []).append(r)

    for (function_type, region), sample in by_key.items():
        sample.sort(key=lambda x: to_int(x.get("concurrency", "0")))
        x = [to_int(s["concurrency"]) for s in sample]
        y = [to_float(s["p95_s"]) for s in sample]

        plt.figure(figsize=(7, 4))
        plt.plot(x, y, marker="o")
        plt.title(f"Concurrency vs P95 - {function_type}/{region}")
        plt.xlabel("Concurrency")
        plt.ylabel("P95 latency (s)")
        plt.grid(True, alpha=0.3)
        out = out_dir / f"concurrency_vs_p95_{function_type}_{region}.png"
        plt.tight_layout()
        plt.savefig(out, dpi=150)
        plt.close()


def plot_rps_vs_errors(rows, out_dir: Path):
    import matplotlib.pyplot as plt

    by_key = {}
    for r in rows:
        key = (r.get("function_type", ""), r.get("region", ""), r.get("scenario", ""))
        by_key.setdefault(key, []).append(r)

    for (function_type, region, scenario), sample in by_key.items():
        sample.sort(key=lambda x: to_float(x.get("rps", "0")))
        x = [to_float(s["rps"]) for s in sample]
        y = [100 * to_float(s["error_rate"]) for s in sample]

        plt.figure(figsize=(7, 4))
        plt.plot(x, y, marker="o")
        plt.title(f"Req/s vs errors - {function_type}/{region}/{scenario}")
        plt.xlabel("Req/s")
        plt.ylabel("Error rate (%)")
        plt.grid(True, alpha=0.3)
        out = out_dir / f"rps_vs_errors_{function_type}_{region}_{scenario}.png"
        plt.tight_layout()
        plt.savefig(out, dpi=150)
        plt.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Plot benchmark outputs")
    p.add_argument("summary_csv", help="Path to summary.csv")
    p.add_argument("--output-dir", default="benchmarks/plots")
    args = p.parse_args()

    summary_csv = Path(args.summary_csv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(summary_csv)
    if not rows:
        raise SystemExit("No rows in summary CSV")

    plot_concurrency_vs_p95(rows, out_dir)
    plot_rps_vs_errors(rows, out_dir)

    print(f"Plots written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
