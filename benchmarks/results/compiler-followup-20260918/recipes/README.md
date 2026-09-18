# Reproduction

Use a disposable checkout of `107c57a4e0c382e60906b509bcd49f3a9809f0ce`, mounted
at `/work` in the Clang 23 builder. Copy these Python files and `minimal/` into
`/work/research`, apply `experiment.patch`, and fetch the source manifest recorded
in `../build-metadata.json`. Pin Emacs to `82f763756c71`, not today's master.
Keep compiler and build paths fixed: promoted names depend on bitcode identity.

Build ordinary instrumentation with `PGO=generate JOBS=18 python3 scripts/build.py`.
`build-variants.py` trains ordinary PGO and builds ordinary use and original CS
use. Its final source-filename naming attempt intentionally retains the historical
GnuTLS duplicate-symbol failure. `resume-fixed.py` makes the first link-only repair;
`resume-ccfixed.py` makes the complete repair and ordinary-cc control. These scripts
assume the preceding experiment directories; do not run over unrelated profiles.
For the complete repair directly:

1. Preserve ordinary `build/merged.profdata` for every prelink compilation.
2. Run `PGO=cs-generate PROFILE_FILE=/work/build/merged.profdata JOBS=18 python3 research/build-ccfixed.py`.
3. Run `scripts/pgo-train.py <bundle>` in a fresh `build/pgo-training-cs`.
4. Merge ordinary `merged.profdata` and `cs.profdata` with `llvm-profdata-23 merge`.
5. Run `PGO=use PROFILE_FILE=<combined> JOBS=18 python3 research/build-ccfixed.py`.
6. Run `tests/run.py <bundle>` and `audit-final.py`. The audit's recorded paths and
   promoted suffix identify this experiment; regenerate these for a new profile.

The wrappers preserve build-script identity/source paths with distinct stage names.
They are research recipes, not production switches. `reproduce.py` creates the
minimal example; `reproduce-cc1.py` validates corrected flags on it. The superseded
`reproduce-link-only.py` shows why no missing-record warning alone is insufficient.

## BOLT

Build `Containerfile.tools` with prebuilt bolt-23/linux-perf. Use that image only
for BOLT/perf, and the original builder for compilation and wall-time measurement.
`bolt-start.py` instruments the ordinary executable and makes a fresh dump. Its
saved working directory is corrected; the failed original and successful retry
are retained in `../bolt/dump-attempt1.log` and `dump-command.json`.
`bolt-train.py` trains/merges fdata; `bolt-optimize.py` rewrites the original
executable, regenerates its dump and smoke-tests. `accept.py` runs full acceptance.

## Measurement and diagnosis

Prepare a config copy with `benchmark-startup.py --config <config> --prepare-only`.
The personal config is not shipped; reproducing with another config is a new
comparison. Copy `../validation-files/` into `build/validation-files/`.
`measure.py`, `measure-final.py` and `measure-balanced.py` record exact interleaved
orders, CPU affinity and excluded warmups using the existing frozen validation.

`sample-pty.py` collects software CPU samples. `diagnose-original-counts.py` runs
only the frozen regexp workload under instrumentation, with isolated outputs that
must NEVER be training/build inputs. Replay the `opt-23` command in
`../diagnosis/final-audit/audit.json`, adding `-print-before=pgo-instr-use` and
`-filter-print-funcs=buf_bytepos_to_charpos` to map named blocks to source branches.
Use the inspection-only profile to compare validation counters.

The single-record intervention (diagnostic, not a production workaround):

```sh
llvm-profdata-23 merge --no-function=buf_bytepos_to_charpos \
  build/cs-link.profdata -o build/cs-without-bytepos.profdata
llvm-profdata-23 merge build/merged.profdata build/cs-without-bytepos.profdata \
  -o build/cs-without-bytepos-combined.profdata
PGO=use PROFILE_FILE=/work/build/cs-without-bytepos-combined.profdata JOBS=18 \
  python3 research/build-fixed.py
python3 research/measure-ablation.py
```

Exact profiles, IR and raw perf samples survive cleanup in the ignored local
archive listed in `../local-evidence-archive.json`. Validation-only profiles are
separately named. The balance experiment changes only training gap placement;
its separate patch, profile and provenance distinguish it from the original runs.
