# macOS CSPGO validation

Emacs source: `9ab48a669651c99ae6fcbf7aba79390f4498db0b`.
Settings: O2, ThinLTO, Cocoa, no native compilation; existing static dependency
recipes remain built with Apple Clang. Ordinary PGO and CSPGO comparison builds
use the same pinned LLVM 23.1.1 compiler, Mach-O LLD and llvm-profdata.

## Diagnosed failures

- [35343386370](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35343386370),
  build commit `1151070`: the Xcode 26.6 Apple toolchain ran the CS probe but
  produced no CS raw profile. This establishes failure of the tested configuration;
  it does not establish that every Apple Clang configuration lacks CSPGO support.
- [35345694067](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35345694067),
  build commit `d848ed9`: official LLVM 23.1.1 ran ordinary PGO successfully, but
  CS linking failed. An absolute `-fuse-ld=/.../ld64.lld` selected the executable
  without identifying the linker kind as LLD. The Darwin driver passed Apple's
  `-mllvm -cs-profile-generate` / `-cs-profile-path=...` options, which LLD rejected.
- Fix `e21de15`: use `-fuse-ld=lld --ld-path=/.../ld64.lld`. A local LLVM 23 Darwin
  driver test (`--target=arm64-apple-macos26 -###`) verified that both CS generation
  and use now forward LLD's native `--cs-profile-*` options. This driver test does
  not substitute for a successful macOS link and run.

- [35346511626](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35346511626):
  CS options now reached LLD correctly, but linking failed on the profile filename
  symbol. The prelink CS flags omitted the filename definition; additionally,
  late archive extraction can follow ThinLTO removal of that variable.
  `linker-check.py` reproduces the latter failure with a minimal Mach-O archive,
  both with public `-fcs-profile-generate` and with explicit frontend CS flags.
  Both link successfully when `-u ___llvm_profile_runtime` loads the runtime
  before ThinLTO. The repair supplies a common prelink bootstrap filename and
  this generation-only linker flag. The reproducer models symbol dependencies;
  actual compiler-rt execution still requires the Mac Action.

## Completed validation

[Run 35350830348](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35350830348),
build commit `121cf91534ca6e95d47572799c228f4fa71e717b`, succeeded. Both Emacs
training passes, final CSPGO build, selected C/Objective-C prelink equality checks,
GUI smoke, dependency/resource audit, matched baseline and comparison passed.
The previous `etags` failure is resolved by selecting matching LLVM archive tools.

- [Toolchain report](toolchain.json): actual Objective-C execution produced
  positive CS counts; final probe link consumed CS metadata.
- [Ordinary](ordinary-provenance.json) and [CS](cs-provenance.json) training
  records: same Emacs source/toolchain, positive counts for all groups, GUI about
  20%, ELPA about 20%, six PTY groups about 10% each. CS training uses the existing
  neutral gap placement, so this compares the project's two recipes rather than
  isolating only a compiler flag.
- [Link audit](link-audit.json): all six bundled executables reference only macOS
  system libraries/frameworks; no Homebrew or external LLVM runtime dependency.
- Artifact `Emacs-macos-arm64`: 49,322,135 bytes (artifact ZIP), uploaded successfully;
  artifact SHA-256 `86f0e847fedffb8344cd7957cb9e83e7e36749d3cf9df60634eb5b933408d482`.
  App packaging also generated the archive checksum. The large app was not
  downloaded locally; inspection used the runner's app audit and upload metadata.
- Ordinary training took 62 seconds and CS training 52 seconds. The extra CS
  build plus training took about 5m39s; final-build times vary.

## Performance

[Raw comparison](comparison.json): 10 samples per variant, alternating order,
one excluded warmup per variant, warm filesystem caches, relocated Cocoa apps,
`-Q` and fixed held-out fixtures. Startup ends after first redisplay, before smoke
checks. This does not measure the user's personal configuration or cold startup.

| Metric (ms, median) | Ordinary PGO | CSPGO | Time reduction |
| --- | ---: | ---: | ---: |
| gui-ready | 504.45 | 581.75 | -15.32% |
| held-out.el | 117.08 | 110.29 | +5.80% |
| held-out.org | 887.94 | 874.09 | +1.56% |
| held-out.txt | 8.97 | 10.37 | -15.52% |
| scroll-edit | 86.10 | 83.61 | +2.89% |
| window-layout | 99.48 | 101.67 | -2.20% |
| json | 36.27 | 34.97 | +3.58% |
| regexp | 7281.32 | 7068.61 | +2.92% |

CSPGO is operational but this run does not justify enabling it by default.
Startup was 77.3 ms slower at the median; Elisp opening and several operation
medians improved. Timing was noisy: ordinary startup ranged 389–968 ms and CS
startup 463–795 ms; regexp ranged 5.56–8.07 s and 6.65–7.89 s respectively.
These are observations from one hosted runner, not stable effect-size estimates.
Keep macOS CSPGO opt-in. No additional CI run was spent chasing a better result.

Both ordinary and CS builds report the same seven discarded-profile warnings
while building helper programs: gnulib `regex.c:rpl_re_search_2` and six helper
`main` functions. They are not CS-only regressions, and the main Emacs build has
no such warning in these logs. The build is therefore not entirely warning-free;
this result does not claim every helper function receives applicable profile data.

Linux's already successful [run 35343383567](https://github.com/stephanoskomnenos/emacs-build/actions/runs/35343383567)
was reused; these macOS-only changes did not trigger another Linux build.
