# Training and validation

Training covers 12 real-PTY subscenarios: file opening, varied editing and
completion inputs, Org, asynchronous JSON/compile output, and small/medium
Magit repositories. Outer group weights are unchanged; subscenarios split
execution-count shares equally within each group. Personal configuration
is never used for training.

`pgo-train.py BUNDLE --check-workloads` verifies actions with a non-instrumented
build without producing profiles. `EMACS_TRAIN_SOURCE` selects the Emacs source;
`EMACS_BUILD_ROOT` optionally selects a separate output directory.

Terminal sessions use Pexpect. Emacs emits completion messages through the
terminal; no separate acknowledgement socket is needed.

Held-out validation inputs and scripts are pinned by `validation-lock.json`.
The regexp item now splits its existing 60 scans equally between gap positions
at the beginning and end of the same text. It retains the same matches and total
scan count; earlier reports used only one gap position, so their regexp timings
are not directly comparable. The observer hash records this revision.

The Pexpect migration changes timing overhead: use the same driver for both
variants and do not compare absolute timings with the older socket-based reports.
Validation rejects instrumented builds and uses a private HOME. PTY actions
check results after command execution and redisplay; process and Magit checks
also verify asynchronous output and Git state. Timings include acknowledgement
and scheduling, but exclude terminal-emulator rendering. Typing bursts and
individual stop-and-wait keystrokes are measured separately.

Measure with builds/training stopped, on a fixed CPU, in alternating variant
order. Exclude warm-ups and retain raw samples. Do not tune training inputs or
weights repeatedly against these held-out results.

```sh
python3 scripts/prepare-workload-packages.py /path/to/bundle
python3 scripts/benchmark-interactive.py /path/to/bundle --label baseline
```
