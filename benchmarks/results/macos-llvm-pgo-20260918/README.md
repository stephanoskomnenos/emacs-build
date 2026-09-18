# macOS LLVM ordinary PGO build and artifact comparisons

LLVM ordinary PGO was rebuilt using Emacs `9ab48a669651c99ae6fcbf7aba79390f4498db0b`
and LLVM 23.1.1 (O2, ThinLTO). The build, training, dynamic dependency audit,
GUI smoke, packaging and upload all passed in
[run 35355938912](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35355938912).
Download `Emacs-macos-arm64-llvm-pgo` there (49,308,507-byte artifact ZIP).
That run is marked failed because its subsequent comparison step invoked `gh`
after Homebrew removal; the uploaded application was unaffected.

The comparison was rerun without building anything in
[successful run 35358138575](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35358138575).
All three apps were downloaded and checksum-verified, their dynamic dependencies
were audited, and two paired comparisons ran sequentially on one macos-26 runner.
Each comparison uses ten alternating samples per app, one excluded warmup per
app, warm filesystem caches, relocated applications and fixed held-out `-Q` GUI
fixtures. No personal configuration was used.

## Apple PGO vs LLVM PGO

Both apps use ordinary PGO. The Apple app is from run `35262660846` (Apple Clang
21.0.0, Emacs `adfbc0bbd9ae`); source and dependency recipe also differ, so these
numbers compare existing builds rather than isolating the compiler.
[Raw samples and manifests](apple-llvm.json).

| Metric (ms, median) | Apple PGO | LLVM PGO | Time reduction |
| --- | ---: | ---: | ---: |
| json | 21.95 | 22.82 | -4.00% |
| regexp | 5835.88 | 5263.23 | +9.81% |
| window-layout | 56.34 | 55.12 | +2.17% |
| scroll-edit | 40.46 | 37.90 | +6.34% |
| held-out.txt | 6.22 | 6.27 | -0.83% |
| held-out.org | 589.64 | 575.49 | +2.40% |
| held-out.el | 88.70 | 84.50 | +4.73% |
| gui-ready | 335.88 | 303.58 | +9.62% |

## LLVM PGO vs LLVM CSPGO

The CSPGO app is from run `35350830348`. Emacs source, compiler, SDK and dependency
recipe match the rebuilt ordinary PGO app. Training was repeated for the ordinary
PGO rebuild, so this is not reuse of the identical ordinary profile. CS training
also uses the existing neutral-gap variant.
[Raw samples and manifests](llvm-cs.json).

| Metric (ms, median) | LLVM PGO | LLVM CSPGO | Time reduction |
| --- | ---: | ---: | ---: |
| json | 21.84 | 21.48 | +1.63% |
| regexp | 5240.46 | 5245.38 | -0.09% |
| window-layout | 54.57 | 55.68 | -2.03% |
| scroll-edit | 39.34 | 39.14 | +0.52% |
| held-out.txt | 6.21 | 6.31 | -1.53% |
| held-out.org | 580.45 | 583.81 | -0.58% |
| held-out.el | 88.26 | 84.23 | +4.57% |
| gui-ready | 316.17 | 304.55 | +3.68% |

The two LLVM PGO columns belong to separate paired runs and should not be combined
into a single three-way sample set. Hosted-runner timing and training counts vary;
these percentages are observed median differences, not confidence guarantees.
Earlier runner results showed a CSPGO startup slowdown, whereas this run shows a
small speedup. There is no demonstrated consistent broad advantage for CSPGO.

Use LLVM ordinary PGO as the macOS default based on this existing-build comparison,
retain opt-in CSPGO, and avoid further builds solely to chase small timing changes.
The production workflow can use the already verified LLVM tools and dependency
cache; no new training framework or workload is required.
