# CSPGO repair and Linux BOLT experiment

After the revised comparison and explicit user approval to deploy a worthwhile
result, Linux adopts O2 + ThinLTO + repaired CSPGO with balanced-gap CS training.
macOS remains on ordinary PGO. BOLT was actually instrumented,
trained, optimized and tested; this report supersedes the earlier feasibility-only
assessment. CSPGO's matching problem is fixed. The final two-sided regexp comparison below
changes the interpretation of the earlier single-sided measurements. The experiments were local. The subsequent production update adds the CS stage
and a manually triggered Linux Action; pushes still do not trigger workflows.

## Final validation correction: modify the existing regexp item

At the user's request, the existing regexp item now does 30 scans with the gap
before the text and 30 with the gap after it, instead of 60 on one side. Same
text, pattern, total scan count and expected sum (86,649,000), and no new test item.
Two insert/delete pairs set the gap without changing file content. The revised
observer hash is `7dea3bdf02ce43bc1e33abae5f03faecc9d374bc87aab67ea37ad097c04b60fa`.
Old observations below are retained with their old observer hash, not silently
pooled with the revised test.

All three existing executables were rerun through the existing full interaction
sequence, two alternating Latin-order rounds, 12 measured sessions per variant
per round plus warmups. No rebuild or retraining. Startup was not rerun because
this change only affects the regexp item; its immediately preceding comparison
remains applicable. [Revised raw measurements](revised-interactive-validation.json):

| Round / variant | Regexp | Allocation/GC | Typing | JSON | Magit |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / ordinary | 64.15 | 359.42 | 8.47 | 97.79 | 285.14 |
| 1 / cs-cc-fixed | 63.47 | 341.20 | 8.18 | 97.95 | 282.21 |
| 1 / cs-balanced | 62.12 | 344.59 | 8.17 | 98.48 | 280.43 |
| 2 / ordinary | 63.42 | 354.46 | 8.29 | 96.48 | 284.86 |
| 2 / cs-cc-fixed | 61.05 | 334.87 | 8.20 | 95.65 | 282.61 |
| 2 / cs-balanced | 61.35 | 337.46 | 8.14 | 96.16 | 279.91 |

The balanced-CS build is **3.2% and 3.3% faster** than ordinary PGO in this revised
regexp test. Original-distribution repaired CS is **1.1% and 3.7% faster**.
Both retain allocation/GC gains; small timings elsewhere and process/JSON (which
varies substantially) do not support precise overall claims. The earlier claim
that the regexp regression ruled out CSPGO was too strong: it measured one side
of the gap, whose layout favored ordinary PGO. The isolated layout finding still
holds, but it describes a tradeoff, not an overall ranking.

Combining the revised interaction results with the preceding startup measurements,
CSPGO now looks favorable for the measured mix. There is no usage-weighted overall
speedup estimate, and no guarantee about unmeasured workloads. The two CS training
variants are not decisively ranked. These local results subsequently justified the user-authorized Linux production
update; they do not establish a universal advantage for either optimization. No new macOS or full LSP stress comparison was performed.

## Production validation

The integrated Linux recipe passed a fresh local ordinary-generate/train,
CS-generate/train, CS-use build, existing builder and clean Debian 13 acceptance,
and binary/source packaging. The source package includes ordinary, CS and combined
profiles with both provenance records. Final runtime symbols were checked absent.
[Exact build metadata, logs and profile/package hashes](production/verification.json).
MacOS flags and its ordinary training behavior remain unchanged.

## Method and measurements

Base repository commit `107c57a4e0c382e60906b509bcd49f3a9809f0ce`; Emacs
`82f763756c71aae1f6361c7ae116a31887f8cc8d`, Debian Clang 23.1.2 snapshot,
O2, ThinLTO, x86-64-v3, identical static dependencies. Every variant emits
relocations so BOLT uses exactly the ordinary-PGO comparison executable.
Builds use 18 jobs; timings run serially, pinned to CPU 0, with warm filesystem
caches on WSL2/Core Ultra 5 250K Plus. No builds run during measurements.

Initial comparison: four variants, four Williams-order blocks per round, two
rounds, three measured sessions plus one excluded warmup per block (12 samples
per variant/round). Final comparison: three variants, ABC/BCA/CAB then
CBA/ACB/BAC, four measured sessions plus one warmup per block (12/variant/round).
Startup uses a fixed copy of the personal config; interaction uses the frozen
independent validation suite. Neither is training input. Generated file fixtures
are saved here; absolute file-opening times are not comparable to older runs.

[Raw startup samples](startup-benchmark.json), [raw interaction samples and
checkpoints](interactive-validation.json), [deduplicated build metadata](build-metadata.json),
[all metric medians](medians.json), and [execution orders and acceptance](provenance/).
Reported values below are medians in milliseconds, not significance estimates.

### Initial comparison

| Round / variant | Config ready | Regexp | Allocation/GC | JSON | Magit workflow |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / ordinary | 453.29 | 62.21 | 363.80 | 98.06 | 294.54 |
| 1 / cs-original | 450.02 | 65.02 | 347.32 | 99.31 | 297.41 |
| 1 / cs-link-fixed | 443.29 | 63.99 | 345.26 | 97.36 | 291.99 |
| 1 / bolt-optimized | 449.68 | 64.65 | 355.85 | 98.33 | 296.82 |
| 2 / ordinary | 455.20 | 61.25 | 352.61 | 96.77 | 286.89 |
| 2 / cs-original | 441.83 | 64.17 | 338.12 | 97.27 | 288.72 |
| 2 / cs-link-fixed | 443.60 | 62.55 | 334.58 | 96.12 | 286.21 |
| 2 / bolt-optimized | 447.53 | 64.04 | 354.90 | 96.16 | 291.21 |

### Final comparison

| Round / variant | Config ready | Regexp | Allocation/GC | JSON | Magit workflow |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / ordinary | 450.14 | 61.34 | 358.99 | 97.38 | 296.50 |
| 1 / ordinary-cc-control | 458.58 | 62.10 | 357.93 | 98.85 | 293.43 |
| 1 / cs-cc-fixed | 444.07 | 63.53 | 336.41 | 99.80 | 292.03 |
| 2 / ordinary | 460.68 | 64.52 | 380.14 | 103.43 | 309.95 |
| 2 / ordinary-cc-control | 452.62 | 61.97 | 355.93 | 96.63 | 290.85 |
| 2 / cs-cc-fixed | 445.17 | 65.32 | 348.00 | 100.68 | 297.62 |

`cs-original` has incomplete CS matching. `cs-link-fixed` matches the profile,
but its raw-profile header defect described below makes that recipe unsuitable.
`cs-cc-fixed` fixes both. `ordinary-cc-control` uses the same CS-ready prelink
objects as `cs-cc-fixed`, but only the ordinary profile at final link.

The final comparison still shows faster startup and allocation/GC and slower
regexp with CS. Round-two host drift is visible across several ordinary metrics;
small gains elsewhere are not reliable. The ordinary-cc control also differs
from the original ordinary executable, so compiler preparation itself can affect
layout. No claim is made that every changed timing comes solely from CS counts.

BOLT saves roughly 4–8 ms of startup in the initial rounds but regresses regexp
about 4–5% in both. Allocation/GC is not consistently better. These single-sided regexp results do not establish that ordinary PGO is
generally faster. BOLT was not rerun under the later two-sided regexp revision;
its overall ranking remains unresolved. No permanent BOLT pipeline was added.

## What was wrong with CSPGO, and the working repair

ThinLTO promotes internal functions with a `.llvm.<module hash>` suffix.
Putting different profile flags into prelink compilation changed that hash
between CS generation and final use. The CS CFG hash could match while the
function name did not; the profile was then missed. LLVM's implementation is in
[FunctionImportUtils.cpp](https://github.com/llvm/llvm-project/blob/main/llvm/lib/Transforms/Utils/FunctionImportUtils.cpp)
and [ModuleSummaryIndex.h](https://github.com/llvm/llvm-project/blob/main/llvm/include/llvm/IR/ModuleSummaryIndex.h).

Trying `-use-source-filename-for-promoted-locals` failed: distinct GnuTLS source
files with identical basenames (`kx.c`, `ecc.c`) produced duplicate symbols.
That flag is not a safe fix for this dependency set.

The first link-only-CS recipe kept ordinary-PGO prelink objects identical and
fixed matching. However, skipping frontend CS setup left the main process's
raw profile at version `0xb` (frontend type). Two helper-process profiles had the
proper IR/CS flags, causing the merged profile to work by accident. A standalone
main-process profile did not work. Thus absence of warnings alone was inadequate.

The final recipe keeps these CFLAGS identical in generation and final use:

```text
-fprofile-use=/work/build/merged.profdata
-Xclang -fprofile-instrument=csllvm
```

Only the link differs: CS generation uses the ordinary profile plus
`-fcs-profile-generate`; final use uses the merged ordinary+CS profile without
that driver flag. This preserves CS-ready bitcode and the raw-version flags
without linking the profiling runtime into the final executable.

[Final audit](diagnosis/final-audit/audit.json) proves identical prelink hashes
for marker, regexp, search, eval, bytecode and allocation objects across CS
generation/final/control; all 15 training raw files have version
`0x30000000000000b`. Replayed CS instrumentation-use for the promoted matcher,
`search_buffer` and `buf_bytepos_to_charpos` has positive counts and no missing
record or CFG warnings. Final/control executables lack profile runtime symbols.
Existing helper/gnulib warnings are retained separately; this is not a claim of
perfect coverage for every helper or third-party function.

## Why regexp still regressed

This is a workload-distribution mismatch, not an invalid regexp test.
Software CPU sampling of 150 real-PTY regexp operations moved
`buf_bytepos_to_charpos` from 4.90% of 8.816 CPU seconds to 7.80% of 9.330 seconds.
The matcher itself did not gain CPU time. Every timed regexp operation still
performs six collections and produces the same result.

The gap-aware forward scanning branch sees about 81% before-gap / 19% after-gap
in training, versus virtually 100% after-gap in an isolated diagnostic run of the
frozen regexp workload. The diagnostic profile is never used for a binary build.
Named-block IR counts are saved in [gap evidence](diagnosis/gap/); block indices
must be mapped using LLVM's MST names, not source block order.

Ordinary PGO leaves the after-gap load on the straight path. CS instead favors
the before-gap path, with the after-gap load reached by a conditional jump and a
jump back into the loop. The fully repaired binary retains this arrangement
(addresses `0x28c3b0`–`0x28c3de` in the saved disassembly); its training ratio is
also about 81/19. [Perf reports and annotations](diagnosis/perf/) support the
same hotspot, with no hardware branch-miss counters available on this host.

Removing ONLY the CS record for `buf_bytepos_to_charpos` from the link-only
profile, retaining its ordinary record and all other CS records, improved regexp
from 64.195 to 62.072 ms and 65.688 to 62.583 ms in two ABBA/BAAB rounds (10 samples
per variant/round). This intervention strongly implicates this function's CS
optimization. It also changes the global profile summary/layout, so it is not a
machine-code-only proof of the exact cycle cost. The filtered profile is a
diagnostic intervention, not a proposed production workaround.

## BOLT execution and dump compatibility

Prebuilt `bolt-23` was installed in a temporary tools image. Instrumentation
used the ordinary executable with `--emit-relocs`. The old portable dump was
removed before invoking each rewritten executable, then regenerated using
`-batch --no-build-details -l loadup --temacs=pdump` from the original build's
`src` directory with explicit runtime-data paths. The initial wrong working
directory failed to find `../etc/DOC`; both failure and corrected commands are
saved under [bolt/](bolt/).

Training reused the 12 generic PTY scenarios and locked ELPA selection once,
excluding preparation/dump/smoke profiles. The 13 fdata files were summed with
`merge-fdata`; unlike LLVM training, this experiment does NOT execution-count
normalize group weights. No user config or validation profile was used.

Optimization used `ext-tsp`, `cdsort`, `split-functions`, `split-all-cold`,
`split-eh` and `dyno-stats`. The optimized executable received another fresh dump.
Existing acceptance passed: relocation, PTY, daemon/client, runtime data,
external module/grammar, vterm, SQLite and other compiled features. BOLT warns
about seven relocation-analysis failures and some crypto/GMP assembly that it
cannot optimize; no claim is made that all linked code was optimized.
Its estimated taken-branch reduction is not a measured runtime speedup.

## One neutral balance experiment

The user requested balancing existing training rather than adding scenarios.
Group-level counters localized most before-gap scans to file browsing and Org;
keyboard editing was already close to balanced. The sole candidate moves the gap
to the middle of the file using an insert/delete before existing file/Org actions.
No new scenario, group weight, compiler setting or validation input was added.
The [11-line patch](recipes/gap-balance.patch) affects training only. This changes
aggregate forward-scan counts from about **81:19 to 53:47** before/after gap.
We did not tune further to force an exact ratio or reverse the preference.

Only CS training was regenerated; the ordinary profile used for prelink compilation
and final merging stays identical. This isolates the extra CS stage; it does not
test retraining the whole ordinary-PGO pipeline. Generation/final prelink hashes
still match and all 15 raw headers have proper IR/CS flags. Existing full acceptance
passes. Same two-round Latin orders and 12 measured samples/variant/round:

| Round / variant | Ready | Regexp | Allocation/GC | JSON | Magit |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / ordinary | 445.56 | 61.26 | 354.10 | 96.23 | 280.98 |
| 1 / cs-cc-fixed | 437.92 | 62.06 | 336.81 | 96.65 | 277.82 |
| 1 / cs-balanced | 439.44 | 63.65 | 340.45 | 96.57 | 279.90 |
| 2 / ordinary | 444.71 | 61.10 | 354.29 | 97.10 | 283.52 |
| 2 / cs-cc-fixed | 439.79 | 62.91 | 335.16 | 96.18 | 279.67 |
| 2 / cs-balanced | 435.54 | 62.34 | 338.47 | 97.61 | 284.28 |

Regexp remains 3.9% and 2.0% slower than ordinary PGO. Against the old CS profile,
one round is slower and one faster, so there is no stable restoration. Startup is
about 6–9 ms faster than ordinary PGO. Allocation/GC remains better than ordinary
PGO but slightly worse than old CS in both rounds. Small other differences are
not evidence of universal regressions or improvements.

The [balanced disassembly](diagnosis/balanced-audit/bytepos-disassembly.txt) still
has the same after-gap detour (`0x26d9b0`–`0x26d9e4`). Balancing execution counts
alone does not force neutral machine-code layout: a binary still has one fallthrough
path, and compiler decisions also depend on surrounding blocks. Thus the identified
path/layout mechanism remains consistent with this unsuccessful repair attempt.
No additional claim about branch mispredictions is made.

At this stage both changes remained experimental. The revised validation above
later supported their Linux adoption; retaining the default before that correction
was not proof that ordinary PGO was better. The frozen test inputs never enter training, but this hypothesis was
motivated by their earlier results, so this is not a fresh blind final evaluation.
The build initially exhausted the `/tmp` memory filesystem; the checkout was moved
to disk and the failed object directory rebuilt before any timings. The container
path stayed `/work`. [Separate exact-profile archive](local-balanced-archive.json)
and [training provenance](provenance/pgo-training-cs-balanced/provenance.json) preserve
the candidate independently of the original profiles.

## Reproduction and retained evidence

The [recipe notes](recipes/README.md) describe the experimental build patch,
repair, training, ablation and BOLT commands. These are local research recipes,
not supported production switches. Build/training costs and source/profile/script
hashes are saved in provenance. The corrected CS stage adds roughly 67 seconds
of building plus 25 seconds of training before the final roughly 61-second build
with warm dependency caches on this host; CI costs can differ substantially.

[Binary/dump hashes](binary-hashes.json) identify tested artifacts. Exact raw and
merged profiles, relevant IR and raw perf recordings are retained in the ignored
local archive identified by [local-evidence-archive.json](local-evidence-archive.json),
so they survive temporary-build cleanup without adding generated binaries to Git.
Personal configuration is not included. Performance evidence is local Linux only;
no inference about macOS CSPGO/BOLT performance follows from these results.
