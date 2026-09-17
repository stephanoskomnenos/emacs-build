# Configured LSP load experiment

Validation only: a private copy of the user's config runs its installed
`lsp-mode`, with runtime GC settings 16,000,000 / 0.1, plist decoding and no
booster in the container. A deterministic stdio server exercises actual LSP
framing, parsing, diagnostics handlers and retained workspace data. It does
not emulate language analysis, completion, semantic tokens or every LSP path.

Seed 64 files with 256 diagnostics each, then replace diagnostics 1,000 times.
Each diagnostic includes Unicode text and related information. Paced replay
targets 200 notifications/second; saturated replay sends as fast as the pipe
allows. Emacs and the PTY driver use CPU 0, the producer CPU 1. Both variants
run at `/bundle` with networking disabled and identical source/compiler inputs.

The PTY attempts a key every 10 ms, waits for command/redisplay acknowledgement,
and records missed slots rather than silently treating them as successful
input. Both actual-send and scheduled-send latencies are retained. Measurements
include harness overhead and exclude terminal-emulator rendering. GC durations
are `gc-elapsed` deltas observed by `post-gc-hook`; peak RSS includes startup.

[2026-09-17 raw samples](../results/lsp-load-20260917.json): six measured sessions
per variant/mode, ABBA groups of three, one excluded warmup per group. Percentile
entries below are medians of per-session percentiles, not pooled percentiles.

| Metric | No PGO | PGO |
| --- | ---: | ---: |
| Paced input P99, ms | 32.42 | 27.12 |
| Paced GC total, seconds | 2.416 | 2.276 |
| Paced collection count | 90 | 86 |
| Saturated completion, seconds | 4.577 | 4.423 |
| Saturated input P99, ms | 38.21 | 36.85 |
| Saturated GC total, seconds | 2.962 | 2.959 |
| Saturated collection count | 114 | 114 |
| Saturated GC P99, ms | 27.83 | 28.57 |

This workload does not reproduce the earlier 8% overall regression. Saturated
GC total is effectively unchanged, with lower overall completion time. Paced
collection counts differ due to asynchronous batching/input; their GC-total
difference does not isolate collector speed. Roughly 26 ms average collections
still occur. Six sessions and small differences do not prove general speedups.

To repeat, prepare with `python3 scripts/prepare-lsp-benchmark.py ~/.emacs.d`.
In the LLVM container mount the repo at `/work` and a noninstrumented bundle
at `/bundle`, then run `python3 scripts/benchmark-lsp.py --label NAME --mode
paced --runs 3` (or `saturated`). Alternate variants and keep other builds
stopped. Require CPUs 0 and 1. The config copy and all fixtures are under
`build/lsp-load`; original config and training inputs are never changed.
