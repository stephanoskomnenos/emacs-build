# PGO experiment

Training never loads the user's configuration. It uses a fresh HOME, a small
configuration made only of built-in libraries, and files from the locked Emacs
source: `src/buffer.c`, `lisp/files.el`, `etc/ORG-NEWS`, and `etc/NEWS`.
Eight terminal sessions open, fontify, search, edit, scroll, and complete names.

The supplementary suite is GNU ELPA's [elisp-benchmarks](https://elpa.gnu.org/packages/elisp-benchmarks.html),
locked in `sources.json`. Selected cases cover byte compilation, SMIE,
fontification, ASCII/non-ASCII scrolling, pcase, lists, closures, and packing.
Its [scrolling benchmark](https://github.com/emacs-straight/elisp-benchmarks/blob/3d917d38d778f9577a2467c74f3b6b820b7926c4/benchmarks/elb-scroll.el)
explicitly notes the limits of batch redisplay; real terminal sessions complement it.

Interactive and suite profiles are merged separately, then weighted to target
75% interactive and 25% suite execution counts. This is an explicit workload
choice, not evidence of optimal weighting. Counts, weights, input hashes, and
compiler/source details are recorded in `build/pgo-training/provenance.json`.

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

## Local result (2026-09-17)

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
