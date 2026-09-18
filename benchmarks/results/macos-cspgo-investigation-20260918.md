# macOS CSPGO investigation

CSPGO is feasible on Darwin; this investigation does not yet prove that the
installed Apple toolchain applies it correctly or that Emacs becomes faster.
The last successful macOS build used Xcode 26.6, Apple Clang 21.0.0
(`clang-2100.1.1.101`) and its matching llvm-profdata. This local host has no Xcode.

LLVM [PR 195020](https://github.com/llvm/llvm-project/pull/195020), merged
2026-05-04, fixed three problems in the system-linker/libLTO path: forwarding CS
options, enabling CS instrumentation, and supplying ThinLTO PGO options.
Consequently, accepting `-fcs-profile-generate` alone is insufficient evidence.
The upstream change does not establish whether Apple's fork has backported it.
The [Darwin driver tests](https://github.com/llvm/llvm-project/blob/main/clang/test/Driver/cspgo-lto.c)
cover system ld and LLD; [Mach-O LLD](https://github.com/llvm/llvm-project/blob/main/lld/MachO/Options.td)
has explicit CS generation/profile-path options.

Recommended first step: a small C/Objective-C ordinary-PGO → CS-generate → CS-use
probe using the actual runner's paired Apple tools. Verify positive CS records,
IR/CS raw flags, matching local names and actual final-link profile application,
not merely successful compilation. Do this before building dependencies/Emacs.
If Apple's path fails, consider a matched prebuilt LLVM clang/ld64.lld/profdata
set; manually forwarding linker options cannot repair missing libLTO behavior.

Repository changes needed after that probe:

- `scripts/macos/build.py`: add CS stages, keep CS-generation/final C and Objective-C
  prelink flags identical, and use one source path. Existing per-stage source
  directories would undermine the stable-bitcode repair used on Linux.
- Reuse shared PTY training and existing Cocoa GUI training. Separate CS corpus,
  GUI session output and provenance directories so the second pass neither reads
  the wrong corpus nor collides with the first pass's output directories.
- The shared trainer currently verifies GUI counts without `--showcs`; use the
  correct profile view for a CS GUI pass.
- Reuse the GUI comparison runner for ordinary PGO versus CSPGO. Its present
  `off/use` validation is hard-coded. Build that extra ordinary-PGO baseline only
  when comparison is requested; do not build an additional no-PGO variant too.
- Preserve ebuild static dependency recipes and system-only dynamic-link audit.
  CSPGO itself does not require adding dynamically linked third-party libraries.

No macOS build flags or workflow were changed by this investigation. This investigation did not modify or restart the existing Linux Action.
