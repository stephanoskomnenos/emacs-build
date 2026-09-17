# Local compiler experiments, 2026-09-18

Keep O2 + ThinLTO + ordinary PGO. Full LTO regressed in both rounds.
The tested CSPGO build gains about 4 ms at startup but regresses on regexp;
further investigation found partially missing CS records, so this is **not a
clean verdict on fully applied CSPGO**. No experimental compiler switches enter
production or Actions.

## Measurements

Same Emacs `82f763756c71`, prebuilt Clang 23, x86-64-v3, CPU 0, warm filesystem
cache, no simultaneous builds. A=ordinary ThinLTO; B=Full LTO or CSPGO.
First round ABBA, second BAAB; each block excludes one warmup and records five
runs. Each comparison therefore has 20 measured runs per variant. Personal
config is used only for startup/file validation; its original hashes remain
unchanged. Interactive validation uses the frozen independent workload. The
shell file uses `sh-mode`, **not tree-sitter**.

| Median ms | Round 1 A / B | Round 2 A / B |
| --- | ---: | ---: |
| Full LTO: config ready | 447.65 / 460.32 | 453.18 / 461.85 |
| Full LTO: regexp | 59.36 / 69.84 | 59.88 / 70.37 |
| CSPGO: config ready | 454.21 / 449.52 | 452.79 / 448.74 |
| CSPGO: regexp | 60.35 / 64.93 | 61.49 / 64.60 |
| CSPGO: allocation/GC | 354.77 / 335.53 | 363.20 / 333.82 |

[Startup/file samples](startup.json), [all interaction samples](interactive.json),
[build metadata, hashes, audits and costs](metadata.json). Full LTO reused the
ordinary profile; this does not test separately trained Full LTO. Both ordinary
and CS training use the same locked corpus, scenarios and weighting targets;
provenance is stored beside these reports. Emacs compile/install took roughly
60 s Thin versus 126 s Full. CS adds about 65 s compilation and 31 s training
before its final build. Full's total cost includes fresh dependencies and is
not a comparable incremental build cost.

## Why the regexp result needs qualification

The regexp workload includes multibyte byte/character position conversion,
match-string allocation, numeric conversion and Lisp evaluation. It is not an
isolated measurement of the C regex matcher.

A separate diagnostic ran the exact observer in a real PTY, repeating its F6
regexp operation 150 times. Software `cpu-clock:u` sampling at 997 Hz found:

| Approximate sampled CPU seconds | Ordinary | CS |
| --- | ---: | ---: |
| Whole sampled process | 8.819 | 9.376 |
| `re_match_2_internal` | 3.143 | 3.176 |
| `buf_bytepos_to_charpos` | 0.469 | 0.775 |
| `eval_sub` | 0.639 | 0.767 |
| `search_buffer` | 0.226 | 0.328 |

These are total event count times self percentages, not direct function timers.
This short A/B sample localizes likely extra work; it does not prove a causal
microarchitectural explanation. WSL exposes software events here, but no
hardware PMU cycles/cache/branch counters. Startup is included in sampling.
The preliminary batch-loading attempt was discarded because it did not
reproduce the normal interactive loader context.

The core matcher's optimized IR is identical after removing metadata and
attribute IDs; resolved attributes and all 655 compared branch weights agree.
Its machine-code size changes by only six bytes, while addresses/layout change.
There is no evidence here that changed branch probabilities *inside that
matcher* explain the regression. Other functions, including position conversion,
have changed IR and code sizes.

Crucially, CS generation names the matcher
`re_match_2_internal.llvm.2414870236557393218`, whereas the final ThinLTO module
uses `.llvm.14539199657944892009`. Replaying the final imported IR through the
ThinLTO optimization pipeline with missing-profile warnings enabled reports
**no profile data for that final name**. The CFG hash, `0x18bbc40491d8efee`, is
identical to the populated CS record. In a diagnostic IR copy, substituting the
old suffix removes the warning without a CFG mismatch. No renamed binary was
built or benchmarked. `set_marker_internal` also has a missing-record warning;
`buf_bytepos_to_charpos` does not in that module replay.

Thus a `CSProfileSummary` alone is insufficient evidence of full CS coverage.
The reported regression is real for the tested binaries, but neither its exact
cause nor the performance of a corrected CSPGO pipeline is established. The
name mismatch explains missing CS coverage, **not by itself the slowdown**.
Keep ordinary PGO; a future CSPGO experiment must first fix and verify promoted
internal-name stability across generation and use.

## Reproduction

Apply [experiment.patch](experiment.patch) to repository commit `09735b4` in a
separate worktree. It records the exact experimental changes, including a
post-build Full LTO inspection typo: replace `emacs*.preopt.bc` with
`temacs*.preopt.bc`. The original run fixed that check in memory and finalized
the already compiled binary. Build with the pinned container and `JOBS=18`.

1. `LTO_MODE=thin PGO=generate python3 scripts/build.py`, then train its bundle
   with `scripts/pgo-train.py`; preserve `build/merged.profdata`.
2. Build `PGO=use PROFILE_FILE=/work/build/merged.profdata` with each LTO mode.
3. Build thin `PGO=cs-generate` with the ordinary profile; run the same training
   script on that bundle. Merge ordinary and `build/cs.profdata` using
   `llvm-profdata-23 merge` into `build/combined.profdata`; build thin `PGO=use`
   with this combined profile. Never run personal config on instrumented builds.
4. Run existing `scripts/benchmark-startup.py` and
   `scripts/benchmark-interactive.py` with `--runs 5 --cpu 0 --label LABEL` in
   the recorded block order. Use absolute `/work/...` bundle paths, the fixed
   config copy and file set. Private config contents are intentionally omitted;
   hashes are recorded, so exact personal-config results require that snapshot.

[Diagnostic PTY driver](regexp/sample-pty.py) records the separate perf sample;
raw checkpoint timings and textual perf reports are included. Replay command:

```sh
opt-23 -passes='thinlto<O2>' -pgo-kind=pgo-instr-use-pipeline \
  -cspgo-kind=cspgo-instr-use-pipeline -profile-file=build/combined.profdata \
  -pgo-warn-missing-function -disable-output \
  build/26b26a7cfa49/emacs-build-llvm-use-aeb5b6d17ace/src/regex-emacs.o.3.import.bc
```

Warnings, profile counters, symbol sizes and IR comparison summaries are in
`regexp/`. LLVM's [name selection](https://github.com/llvm/llvm-project/blob/main/llvm/lib/Transforms/Instrumentation/PGOInstrumentation.cpp)
and [profile lookup](https://github.com/llvm/llvm-project/blob/main/llvm/lib/ProfileData/InstrProfReader.cpp)
corroborate the replay. These links track upstream; the replay itself uses the
same prebuilt LLVM as the measured binaries.

## BOLT feasibility

Linux x86-64 ELF is the appropriate first candidate: retain symbols and emit
relocations at link, then collect a BOLT profile. Hardware sampling is unavailable
on this host; BOLT instrumentation is the alternative. This is a proposed
experiment, not a measured benefit. See the [BOLT guide](https://github.com/llvm/llvm-project/blob/main/bolt/README.md).

macOS is **not categorically unsupported**: LLVM has a
[Mach-O rewriter](https://github.com/llvm/llvm-project/blob/main/bolt/lib/Rewrite/MachORewriteInstance.cpp).
Its noninstrumenting path keeps function addresses and offers a smaller pass
pipeline, so ELF capabilities cannot be assumed. Apple Silicon runtime,
instrumentation-section preparation and signing remain unvalidated here.
No macOS BOLT Action was launched.

Emacs [portable dump](https://github.com/emacs-mirror/emacs/blob/82f763756c71aae1f6361c7ae116a31887f8cc8d/src/pdumper.c)
stores executable-relative relocations and a fingerprint. A rewritten executable
must not simply reuse the pre-rewrite dump. A future trial should regenerate
and validate the dump with the rewritten executable before packaging; that is
a prerequisite, not proof of compatibility. BOLT therefore remains a separate,
bounded Linux feasibility experiment rather than a production build option.
