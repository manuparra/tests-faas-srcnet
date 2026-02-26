# Benchmark summary

| scenario | phase | function_type | region | concurrency | idle_minutes | requests | errors | rps | p50_s | p95_s | p99_s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline |  | cpu_data | uk | 1 | 0 | 37 | 0 | 0.3101 | 0.674086 | 2.333714 | 3.356037 |
| baseline |  | cpu_data | spain | 1 | 0 | 44 | 0 | 0.3678 | 0.655346 | 0.845042 | 1.442406 |
| baseline |  | cpu_data | switzerland | 1 | 0 | 43 | 0 | 0.3591 | 0.586326 | 1.931609 | 1.993423 |
| baseline |  | nohup | uk | 1 | 0 | 54 | 0 | 0.4493 | 0.164801 | 0.181592 | 0.196118 |
| baseline |  | nohup | switzerland | 1 | 0 | 54 | 0 | 0.4545 | 0.21611 | 0.231991 | 0.236639 |
| baseline |  | nohup | spain | 1 | 0 | 45 | 0 | 0.3758 | 0.383993 | 1.578492 | 2.281264 |

## Cold vs warm delta

| function_type | region | idle_minutes | delta_p95_s |
|---|---|---:|---:|
