# Linux ordinary PGO versus CSPGO

Linux defaults to O2 + ThinLTO + repaired CSPGO with balanced-gap CS training.
The measurements below supported that choice; they are historical measurements
of the specified revision, not benchmarks of every subsequent master build.
The Action's `cspgo` switch retains ordinary PGO as an opt-out.

## Conditions

- Emacs `82f763756c71aae1f6361c7ae116a31887f8cc8d`;
  Debian Clang 23.1.2 snapshot `069ef0e7cb36`, x86-64-v3.
- Identical static dependencies; WSL2 / Core Ultra 5 250K Plus, CPU 0,
  warm filesystem caches, no concurrent builds.
- Two alternating-order rounds, 12 measured sessions per variant per round,
  excluding warmups. Values are medians in milliseconds; lower is better.
- Personal configuration was used only for startup validation, never training.
  Interaction fixtures were separate from training inputs.

## Results

Startup comes from the comparison immediately before the regexp test revision.
The other rows come from the subsequent full interaction rerun using the same
binaries. Each cell shows round 1 / round 2.

| Metric | Ordinary PGO | Repaired CSPGO | Balanced CSPGO (adopted) |
| --- | ---: | ---: | ---: |
| Config ready | 445.56 / 444.71 | 437.92 / 439.79 | 439.44 / 435.54 |
| Regexp | 64.15 / 63.42 | 63.47 / 61.05 | 62.12 / 61.35 |
| Allocation/GC | 359.42 / 354.46 | 341.20 / 334.87 | 344.59 / 337.46 |
| Typing | 8.47 / 8.29 | 8.18 / 8.20 | 8.17 / 8.14 |
| JSON | 97.79 / 96.48 | 97.95 / 95.65 | 98.48 / 96.16 |
| Magit | 285.14 / 284.86 | 282.21 / 282.61 | 280.43 / 279.91 |

The adopted variant improved startup by 6.12 / 9.17 ms (1.4% / 2.1%),
regexp by 3.2% / 3.3%, and allocation/GC by 4.1% / 4.8%.
Small differences in other operations and variable process timings do not
establish an overall speedup. The two repaired CS variants are not decisively ranked.

## Interpretation and provenance

The repair keeps CS-generation and final-use prelink flags identical, preventing
ThinLTO's promoted local names from changing and losing matching CS records.
The audit confirmed matching prelink hashes, correct IR/CS headers in all 15 raw
profiles, positive CS counts in the inspected regexp/search/position functions,
and no profiling runtime symbols in the final executable.

The revised regexp item replaces 60 after-gap scans with 30 on each side, keeping
the text, pattern, total scans and expected result unchanged. Earlier single-sided
regressions describe that layout, not regexp performance generally. Training gap
placement was balanced separately; neither validation data nor personal config
entered training. This investigation informed the revision, so it is not a fresh
blind evaluation. No new full LSP stress comparison was performed.

Complete reports, raw samples, hashes and build/acceptance records remain in
[Git history at 6a7f884](https://github.com/stephanoskomnenos/emacs-build/tree/6a7f884/benchmarks/results/compiler-followup-20260918).
That record includes successful production CI run `35312516728` on `1884917`;
the old run itself was subsequently removed during cleanup.
BOLT passed the recorded build/acceptance checks but was not rerun with the
two-sided regexp test, so its overall performance ranking remains unresolved.
