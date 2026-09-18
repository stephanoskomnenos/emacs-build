# macOS: ebuild, Apple PGO and LLVM CSPGO

Three existing arm64 artifacts were measured on the same macos-26 runner.
One excluded warmup and 12 measured sessions per build; all six order permutations
repeated twice. Warm-cache Cocoa windows, `-Q`, shared held-out fixtures, no personal
configuration. No rebuilding or training was performed. [Raw samples and artifact identities](comparison.json).

## Results

Values are median milliseconds; lower is better. Percentages in parentheses are
normalized elapsed time with ebuild = 100%, not speedup percentages.

| Operation | ebuild | Apple PGO | LLVM CSPGO |
| --- | ---: | ---: | ---: |
| GUI ready | 551.03 (100.0%) | 528.89 (96.0%) | 570.77 (103.6%) |
| Open Elisp | 114.77 (100.0%) | 102.91 (89.7%) | 104.84 (91.3%) |
| Open Org | 866.16 (100.0%) | 823.06 (95.0%) | 837.36 (96.7%) |
| Open text | 8.90 (100.0%) | 11.25 (126.4%) | 10.36 (116.4%) |
| Scroll/edit | 69.40 (100.0%) | 59.31 (85.4%) | 55.53 (80.0%) |
| Window layout | 86.94 (100.0%) | 88.01 (101.2%) | 81.55 (93.8%) |
| JSON | 34.91 (100.0%) | 28.28 (81.0%) | 27.02 (77.4%) |
| Regexp | 7538.97 (100.0%) | 7124.61 (94.5%) | 5873.89 (77.9%) |

LLVM CSPGO reduced regexp, JSON and scroll/edit median time by about 20–23%
against ebuild. Text opening took 1.46 ms longer. Apple PGO had the lowest startup,
Elisp-opening and Org-opening medians in this run. These are whole-build comparisons;
compiler, PGO, dependency and configuration effects are not isolated.

## Startup variability

The startup medians reverse the earlier comparison: Apple PGO 528.89 ms, ebuild
551.03 ms, LLVM CSPGO 570.77 ms. Individual samples varied substantially:

| Build | Minimum (ms) | Maximum (ms) |
| --- | ---: | ---: |
| ebuild | 338.64 | 1363.68 |
| apple-pgo | 402.04 | 756.17 |
| llvm-cspgo | 421.19 | 727.63 |

This run does not establish a stable startup ranking. The earlier two paired
comparisons measured Apple PGO / LLVM PGO at 335.88 / 303.58 ms, and LLVM PGO /
CSPGO at 316.17 / 304.55 ms. Those were separate pairs, not repeated direct
Apple-PGO/CSPGO trials. Do not pool timings across runners.

## Provenance

- ebuild: `RadioNoiseE/ebuild` run `35302781912`, artifact `Emacs-32.0.50`,
  recipe `5f2e2c6229989d986f1072c7727a586d92bb8523`; Emacs `adfbc0bbd9aebc7a24fb2728bf3aff85205ebe9f`.
  Apple Clang, O2, `-flto`, no PGO, no SQLite, explicit small Japanese dictionary.
- Apple PGO: this repository run `35262660846`, artifact `Emacs-macos-arm64`;
  Emacs `adfbc0bbd9aebc7a24fb2728bf3aff85205ebe9f`, Apple Clang 21, O2, ThinLTO, SQLite.
- LLVM CSPGO: run `35350830348`, artifact `Emacs-macos-arm64`;
  Emacs `9ab48a669651c99ae6fcbf7aba79390f4498db0b`, LLVM 23.1.1, O2, ThinLTO, SQLite.
- Our two apps do not embed `emacs-repository-version`; their source revisions
  above come from the [previous build metadata](../macos-llvm-pgo-20260918/README.md).
  The raw report preserves the runtime-reported null values rather than replacing them.
- Comparison run `35364889882`, temporary experiment commit `a92802d`.
  The completed temporary run and branch were removed after saving these results.
  Archive SHA-256 values, runtime features/configure flags and dynamic libraries
  are recorded in the raw report. The shared GUI workload was unchanged from `612fdc9`.
