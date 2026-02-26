#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path


def read_csv(path: Path):
    with path.open() as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows):
    fields = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)

    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    p = argparse.ArgumentParser(description="Merge multiple node summaries")
    p.add_argument("--input", action="append", required=True, help="node_name=path/to/summary.csv")
    p.add_argument("--output", default="benchmarks/results/multi_node_summary.csv")
    args = p.parse_args()

    merged = []
    for item in args.input:
        if "=" not in item:
            raise SystemExit(f"Invalid --input value: {item}")
        node, path = item.split("=", 1)
        rows = read_csv(Path(path))
        for r in rows:
            r["client_node"] = node
            merged.append(r)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out, merged)
    print(f"Merged summary written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
