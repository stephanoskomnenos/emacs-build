# PGO training and performance validation

Both platforms use LLVM Clang, O2, ThinLTO and CSPGO by default. Disable the
Action's `cspgo` switch for ordinary PGO. macOS includes Cocoa GUI training.
Build commands are in the [project README](../README.md#构建).

Cocoa training opens files, scrolls, edits, splits windows and changes text size;
it also exercises search/completion candidates, Org structure, asynchronous
JSON/compilation output and Magit status/diff/history using the shared training
fixtures. Lisp and keyboard macros drive these operations in a visible window;
OS mouse/keyboard injection and native dialogs are not simulated. Real minibuffer
input remains covered by PTY training.

## Training

Training uses a private HOME and pinned inputs from [sources.json](sources.json),
never the user's configuration or validation fixtures. Twelve real-PTY
subscenarios cover files, editing/search, minibuffer completion, Org, asynchronous
JSON/compilation output and Magit. GNU ELPA's `elisp-benchmarks` supplements these
with byte compilation, SMIE, fontification, scrolling and Lisp operations.

The six PTY groups each target 12.5% of execution counts; ELPA targets 25%.
These are workload choices, not wall-time proportions or proven optimal weights.
macOS allocates 10% to each PTY group, 20% to ELPA and 20% to GUI. Actual weights, source/script
hashes and assertions are recorded in each training pass's `provenance.json`.
Package preparation and build-bootstrap profiles are excluded.

CSPGO reuses the training driver and workloads for a second pass, with neutral
middle-of-file gap placement in file/Org training. The ordinary profile feeds
prelink compilation; the combined ordinary/CS profile feeds the final link.
Dependencies and packaging are shared between ordinary PGO and CSPGO.

## Validation

- [Terminal interaction](interactive/README.md): input, minibuffer, regexp,
  JSON/processes, allocation/GC and Magit using independent fixtures.
- `scripts/linux/benchmark-startup.py`: startup and file display with a private copy
  of the user's configuration; instrumented builds are rejected.
- [Configured LSP load](lsp/README.md): diagnostics replay and input/GC latency.
- `scripts/macos/gui.py compare`: Cocoa startup and operations with fixed test
  configuration. The macOS Action's `compare` switch adds one baseline: no-PGO
  for ordinary PGO, ordinary PGO for CSPGO.

Compare variants with identical source, fixtures and measurement conditions;
alternate order, exclude warm-ups and retain raw samples. Stop concurrent builds
before local timing. Measurements use warm filesystem caches; terminal timings
include driver/scheduling overhead and exclude terminal-emulator rendering.
Performance comparisons are optional, with no timing thresholds in routine CI.
Correctness checks live in [tests/](../tests/).

## Results

The [Linux CSPGO summary](results/linux-cspgo-20260918.md) records the measurements
behind the default and links to the complete evidence in Git history.
The [macOS three-way artifact comparison](results/macos-ebuild-20260918/README.md)
compares ebuild, Apple PGO and LLVM CSPGO, including startup variability.
The [earlier paired macOS comparisons](results/macos-llvm-pgo-20260918/README.md)
include raw samples and build metadata. Other historical experiments remain in Git history.
