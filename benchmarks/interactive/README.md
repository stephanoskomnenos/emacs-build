# Training and validation

Training covers 12 real-PTY subscenarios: file opening, Evil-based editing and
completion inputs, Org, asynchronous JSON/compile output, and small/medium
Magit repositories. Outer group weights are unchanged; subscenarios split
execution-count shares equally within each group. Personal configuration
is never used for training.

The editing scenarios load the pinned Evil package in a private `-Q` session.
They balance short/medium/long motion, forward/backward operators, visual
selection, yank/paste, undo/redo, and forward/backward search without making
any one command family dominate the profile.

`pgo-train.py BUNDLE --check-workloads` verifies actions with a non-instrumented
build without producing profiles. `EMACS_TRAIN_SOURCE` selects the Emacs source;
`EMACS_BUILD_ROOT` optionally selects a separate output directory.

Terminal sessions use Pexpect. Emacs emits completion messages through the
terminal; no separate acknowledgement socket is needed.

Held-out validation inputs and external dependency metadata are pinned by
`validation-lock.json`; validation scripts are versioned by Git.
The regexp item splits 60 scans equally between gap positions at the beginning
and end of the same text. Use the same validation lock and driver for both variants.

Validation rejects instrumented builds and uses a private HOME. When the
workload package set contains Evil, held-out editing actions also exercise its
normal, insert, visual, operator, undo/redo and search paths. PTY actions
check results after command execution and redisplay; process and Magit checks
also verify asynchronous output and Git state. Timings include acknowledgement
and scheduling, but exclude terminal-emulator rendering. Typing bursts and
individual stop-and-wait keystrokes are measured separately.

Measure with builds/training stopped, on a fixed CPU, in alternating variant
order. Exclude warm-ups and retain raw samples. Do not tune training inputs or
weights repeatedly against these held-out results.

```sh
python3 scripts/prepare-workload-packages.py /path/to/bundle
python3 scripts/linux/benchmark-interactive.py /path/to/bundle --label baseline
```
