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
recorded in `build/pgo-training/provenance.json`. Package preparation, cancellation preflight
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

[Final revalidation](results/diverse-pgo-20260917-cancel-fix.json) follows the
minibuffer cancellation fix. Each comparison has 12 measured samples per
variant in A/B/C/C/B/A order, excluding warm-ups. Master, compiler, dependencies,
CPU and validation inputs are identical; the old profile was rebuilt alongside
the new one. The table uses the repeat with every bundle mounted at `/bundle`.
The config snapshot is used only by noninstrumented validation.

| Median milliseconds | No PGO | Old profile | Diverse profile |
| --- | ---: | ---: | ---: |
| PTY typing burst | 8.61 | 8.07 | 7.47 |
| Minibuffer completion | 1.50 | 1.50 | 1.35 |
| Regexp workload | 76.22 | 65.41 | 60.98 |
| JSON workload | 93.00 | 91.79 | 92.41 |
| Async process/JSON | 80.02 | 79.91 | 81.61 |
| Allocation/GC workload | 333.83 | 351.95 | 360.28 |
| Magit workflow | 273.70 | 270.29 | 265.56 |
| User config ready | 448.94 | 443.06 | 435.75 |
| Open user Elisp | 120.54 | 115.44 | 108.58 |
| Open user Org | 233.37 | 225.67 | 210.56 |

Keep diverse training for the startup, file-opening, input, regexp and Magit
improvements, with a measured tradeoff: allocation/GC is about 8% slower than
no PGO in both final comparisons. All variants perform 98 collections in the
identical-path repeat; most of the difference is GC time. This deliberately
GC-heavy test uses a 400 KB threshold and does not establish the same penalty
for normal editing. Process/JSON varies between runs and has no demonstrated
improvement. These results do not establish universally faster performance.
Weights and training were not tuned against this frozen validation suite.

[Earlier diverse-profile measurements](results/diverse-pgo-20260917.json) are
retained as history; their smaller GC difference does not describe the final
regenerated profile. GC can move between adjacent Magit operations, so the
workflow aggregate is more useful than isolated stage/unstage timings. PTY
round trips include harness overhead and exclude terminal-emulator rendering.

LLVM IR confirms positive profile counts in bytecode, keyboard, process and
Emacs-regexp code. Logs also contain discarded mismatched records when the
same profile is applied to helper-program `main` functions and the separate
gnulib regex implementation; these are not claims of PGO coverage for every
helper. The Emacs regexp implementation has matching positive counts.

## Runtime GC settings sensitivity

[Threshold-only follow-up](results/gc-settings-20260917.json): same validation
sequence and builds, 12 measured samples per combination, fixed CPU and bundle
path. The user's post-startup values are 16,000,000 bytes and 0.1; startup uses
500,000,000 bytes and 0.6. These sessions use `-Q` with the runtime parameters,
not the full personal config. The final explicit collection remains included.

| Threshold | Collections (both) | Total ms, no PGO / PGO | GC ms, no PGO / PGO |
| --- | ---: | ---: | ---: |
| 400,000 bytes | 98 | 347.61 / 371.41 | 325.89 / 352.05 |
| 16,000,000 bytes | 3 | 42.22 / 39.52 | 16.41 / 16.57 |

At 16 MB the overall workload is about 6.4% faster with PGO; the small GC-time
difference does not demonstrate a regression. This does not establish results
for a larger live heap or explain the low-threshold regression's root cause.

The subsequent [configured LSP load experiment](lsp/README.md) uses the complete
config copy and actual `lsp-mode` diagnostics handling under sustained traffic.
It records input tails and per-collection times, not only total throughput.
