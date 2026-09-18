# Configured LSP validation

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

To repeat, prepare with `python3 scripts/linux/prepare-lsp-benchmark.py ~/.emacs.d`.
In the LLVM container mount the repo at `/work` and a noninstrumented bundle
at `/bundle`, then run `python3 scripts/linux/benchmark-lsp.py --label NAME --mode
paced --runs 3` (or `saturated`). Alternate variants and keep other builds
stopped. Require CPUs 0 and 1. The config copy and all fixtures are under
`build/lsp-load`; original config and training inputs are never changed.

Earlier measurements are available in Git history.
