# Independent interaction regression experiment

`validation.json` and the validation sequence are fixed before new training.
No instrumented binary is accepted. Runs use a private HOME, local files and a
local Git repository, never the user's configuration or repository. Magit and
its dependencies are locked in `../sources.json` and byte-compiled once.

The driver sends actual bytes through a PTY. F12 requests acknowledgement over
an independent Unix socket after previous commands and redisplay. Subprocess
checks wait for its output filter and sentinel, not just OS process exit.
Every scenario checks its result; stage/unstage also checks the Git index.
An empty acknowledgement measures harness overhead. Typing burst throughput
and 40 individual stop-and-wait keystrokes are recorded separately.

Measurements include input dispatch, acknowledgement and OS scheduling. They
exclude terminal-emulator rendering and are not pure command execution times.
Package preparation and Git fixture setup occur outside measured intervals.
Run comparisons with builds/training stopped, on a fixed CPU, in alternating
variant order. Exclude each process group's first warm-up; retain raw samples.
Do not choose new training inputs or weights by repeatedly tuning these results.

```sh
# In the LLVM container, after fetching the locked benchmark archives:
python3 scripts/prepare-workload-packages.py /path/to/noninstrumented/bundle
python3 scripts/benchmark-interactive.py /path/to/bundle --label baseline
```

The first pilot exposed per-operation timing shifts. Before any new training,
the observer was extended to record GC count/time, expansion now asserts a
visible diff hunk, and the complete Magit workflow is reported as an aggregate.
Pilot results are not the final comparison. The inputs and action sequence
remain unchanged; `validation-lock.json` fixes the diagnostic version.
