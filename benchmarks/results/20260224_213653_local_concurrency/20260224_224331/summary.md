# Benchmark summary

| scenario | phase | function_type | region | concurrency | idle_minutes | requests | errors | rps | p50_s | p95_s | p99_s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| concurrency |  | cpu_data | local | 1 | 0 | 36 | 0 | 0.5911 | 1.57995 | 2.0997 | 2.571574 |
| concurrency |  | cpu_data | local | 5 | 0 | 69 | 0 | 1.1002 | 3.67338 | 8.863667 | 10.238222 |
| concurrency |  | cpu_data | local | 10 | 0 | 77 | 0 | 1.1432 | 7.324282 | 16.230002 | 20.787306 |
| concurrency |  | cpu_data | local | 20 | 0 | 93 | 0 | 1.338 | 12.219081 | 28.556296 | 31.044463 |
| concurrency |  | cpu_data | local | 30 | 0 | 91 | 0 | 1.2643 | 19.124472 | 49.573645 | 65.77829 |
| concurrency |  | cpu_data | local | 50 | 0 | 95 | 0 | 1.1749 | 36.543465 | 73.834205 | 76.79277 |

## Cold vs warm delta

| function_type | region | idle_minutes | delta_p95_s |
|---|---|---:|---:|
