# macOS performance comparison — 2026-09-18

Two paired comparisons on one macos-26 runner, ten alternating samples per build
with one excluded warmup. Warm caches, relocated Cocoa applications, fixed `-Q`
fixtures; no personal configuration. Values are median milliseconds.

| Metric | Apple PGO | LLVM PGO (pair 1 / pair 2) | LLVM CSPGO |
| --- | ---: | ---: | ---: |
| gui-ready | 335.88 | 303.58 / 316.17 | 304.55 |
| held-out.el | 88.70 | 84.50 / 88.26 | 84.23 |
| held-out.org | 589.64 | 575.49 / 580.45 | 583.81 |
| held-out.txt | 6.22 | 6.27 / 6.21 | 6.31 |
| scroll-edit | 40.46 | 37.90 / 39.34 | 39.14 |
| window-layout | 56.34 | 55.12 / 54.57 | 55.68 |
| json | 21.95 | 22.82 / 21.84 | 21.48 |
| regexp | 5835.88 | 5263.23 / 5240.46 | 5245.38 |

The two LLVM PGO columns are separate paired runs, not a single three-way sample.

- [Apple PGO / LLVM PGO samples](apple-llvm.json): Apple Clang 21.0.0 versus LLVM
  23.1.1; Emacs revisions, GUI training and dependency recipes also differ.
  This compares the two builds, not the isolated effect of the compiler.
- [LLVM PGO / CSPGO samples](llvm-cs.json): same Emacs revision, LLVM 23.1.1, SDK
  and dependency recipe. Ordinary PGO was retrained; CS also uses the existing
  neutral-gap training. Small differences should not be treated as stable gains.

Full build metadata is included in each JSON file. Production builds use LLVM
and enable CSPGO by default, with an ordinary-PGO opt-out.
