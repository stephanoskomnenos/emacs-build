# PGO experiment

Training never loads the user's configuration or held-out validation inputs.
Six separate real-PTY scenarios cover source-file opening/fontification,
keyboard editing and search, minibuffer completion, Org interaction, asynchronous
JSON/compilation output, and Magit status/diff/stage/unstage/history. They use a
private HOME, locked Emacs files and a generated local Git repository. Magit and
its dependencies are pinned in `sources.json` and byte-compiled for the sessions.

The supplementary suite is GNU ELPA's [elisp-benchmarks](https://elpa.gnu.org/packages/elisp-benchmarks.html),
locked in `sources.json`. Selected cases cover byte compilation, SMIE,
fontification, ASCII/non-ASCII scrolling, pcase, lists, closures, and packing.
Its [scrolling benchmark](https://github.com/emacs-straight/elisp-benchmarks/blob/3d917d38d778f9577a2467c74f3b6b820b7926c4/benchmarks/elb-scroll.el)
explicitly notes the limits of batch redisplay; real terminal sessions complement it.

Each scenario and the supplementary suite produce separate profiles. Integer
weights target equal 12.5% execution-count shares for the six scenarios and 25%
for the suite. This initial choice controls domination by individual scenarios;
it is neither a wall-time ratio nor evidence of optimal weights. Both sides can
be scaled, with actual shares, counters, input/script hashes and assertions
recorded in `build/pgo-training/provenance.json`. Package preparation profiles
and build-bootstrap profiles are excluded from the merge.

The [independent interaction suite](interactive/README.md) is frozen before new
training. It tests real input, minibuffer, processes/JSON, regexp, allocation/GC,
and a different Magit repository/operation sequence. Its functional assertions
also run in CI; CI does not impose timing thresholds on shared runners.

Validation uses a separate copy of the user's config and installed packages;
absolutely linked package files are relocated inside that copy. It checks init
and Elpaca failures, measures readiness and file display, discards a warm-up,
and keeps repeated samples. The PTY answers device-attribute/Kitty keyboard
queries to avoid artificial terminal timeouts. Filesystem caches are warm;
measurements do not include the rendering latency of a real terminal emulator.
Instrumented binaries are rejected by the validation runner.

```sh
bash scripts/container.sh llvm-image
python3 scripts/fetch.py --benchmarks
TOOLCHAIN=llvm bash scripts/container.sh build
TOOLCHAIN=llvm PGO=generate bash scripts/container.sh build
bash scripts/container.sh train
TOOLCHAIN=llvm PGO=use bash scripts/container.sh build
```

## Initial profile result (2026-09-17, before diverse training)

Same Emacs master `82f763756c71`, Clang 23 snapshot, O2, ThinLTO and x86-64-v3.
Ten measured runs per variant, grouped baseline/PGO/PGO/baseline, fixed CPU 0
on Core Ultra 5 250K Plus. Each group excludes one warm-up.

| Median milliseconds | Without PGO | PGO |
| --- | ---: | ---: |
| User config ready | 450.9 | 438.0 |
| Open Elisp | 119.2 | 107.8 |
| Open Org | 234.1 | 213.1 |
| Open Bash (tree-sitter) | 48.2 | 46.9 |
| Open large text | 38.1 | 35.4 |

[Raw measurements and build metadata](results/llvm-pgo-20260917.json).
This supports enabling PGO for this workload; the small startup difference is
not a statistical significance claim or a comparison against GCC.
The user's configuration and files are neither training inputs nor shipped.
The source archive includes the exact profile and its provenance. To reuse it,
skip the instrumented build and training and run `PGO=use ... build`.

## Diverse profile comparison (2026-09-17)

[Raw three-way results](results/diverse-pgo-20260917.json), 12 measured samples
per variant in A/B/C/C/B/A order. All variants use the same master, Clang,
dependencies and build paths; the old profile was rebuilt in this environment.
The separate config snapshot is used only by the noninstrumented validation.

| Median milliseconds | No PGO | Old profile | Diverse profile |
| --- | ---: | ---: | ---: |
| PTY typing burst | 8.85 | 8.26 | 7.63 |
| Minibuffer completion | 5.11 | 5.20 | 4.94 |
| Regexp workload | 75.71 | 64.14 | 59.97 |
| JSON workload | 99.05 | 97.94 | 98.28 |
| Async process/JSON | 58.57 | 53.75 | 57.86 |
| Allocation/GC workload | 341.90 | 356.89 | 346.01 |
| Magit workflow | 289.81 | 280.39 | 275.98 |
| User config ready | 458.94 | 453.79 | 445.59 |
| Open user Elisp | 124.27 | 120.21 | 113.29 |
| Open user Org | 241.58 | 237.78 | 219.15 |

Select the diverse profile: input, regexp, Magit and user-config workloads
improve in this run, while the allocation/GC difference from no PGO is about
1.2%. Small differences and process scheduling variation are not proof of a
speedup or regression. GC can move between adjacent Magit operations, so the
workflow aggregate is more useful than an isolated stage/unstage timing.

LLVM IR confirms positive profile counts in bytecode, keyboard, process and
Emacs-regexp code. Logs also contain discarded mismatched records when the
same profile is applied to helper-program `main` functions and the separate
gnulib regex implementation; these are not claims of PGO coverage for every
helper. The Emacs regexp implementation has matching positive counts.
