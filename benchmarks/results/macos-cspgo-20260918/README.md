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

## Required evidence

A new Mac run is needed to validate the runtime-symbol repair. Completion requires a passing Objective-C ThinLTO CS probe, both
actual Emacs training passes, stable selected C/Objective-C prelink objects,
Cocoa smoke checks, system-only dynamic-link/resource audit, packaged app and
an alternating ordinary-PGO/CSPGO GUI comparison. No macOS performance conclusion
has been established yet. Comparison uses fixed held-out GUI fixtures, not a
personal configuration.
