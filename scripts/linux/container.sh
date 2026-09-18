#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
image=localhost/emacs-builder:clang23
# Keep host and container paths equivalent, including isolated local experiments.
build_root=$(realpath -m --relative-to="$PWD" "${EMACS_BUILD_ROOT:-build}")
case "$build_root" in .|..|../*) echo 'EMACS_BUILD_ROOT must be a subdirectory of this repository' >&2; exit 2;; esac
dist_root=${EMACS_DIST_ROOT:-dist}
if [[ "$build_root" != build && -z "${EMACS_DIST_ROOT:-}" ]]; then dist_root=$build_root/dist; fi
dist_root=$(realpath -m --relative-to="$PWD" "$dist_root")
case "$dist_root" in .|..|../*) echo 'EMACS_DIST_ROOT must be a subdirectory of this repository' >&2; exit 2;; esac
runtime_env=(-e EMACS_BUILD_ROOT="/work/$build_root" -e EMACS_DIST_ROOT="/work/$dist_root")
command=${1:-build}
if [[ $# -gt 0 ]]; then shift; fi
case "$command" in
  train|test|test-interactive|package|rpm)
    selection=${1:?Specify a stage (generate, cs-generate, use, cs-use, off) or bundle path}
    shift
    case "$selection" in
      generate|cs-generate|use|cs-use|off) bundle=$build_root/bundles/$selection;;
      *) bundle=$(realpath -m --relative-to="$PWD" "$selection");;
    esac
    if [[ ! -f "$bundle/BUILD-INFO.json" ]]; then echo "Missing bundle: $bundle" >&2; exit 2; fi
    bundle=$(realpath --relative-to="$PWD" "$bundle")
    case "$bundle" in ../*) echo 'Bundle must be inside this repository' >&2; exit 2;; esac
    ;;
esac
case "$command" in
  image)
    podman build -t "$image" -f containers/Containerfile .
    ;;
  build)
    profile=merged.profdata
    if [[ "${PGO:-off}" == cs-use ]]; then profile=combined.profdata; fi
    podman run --rm --userns=keep-id --network=none \
      "${runtime_env[@]}" -e JOBS="${JOBS:-$(nproc)}" -e LTO="${LTO:-1}" \
      -e PGO="${PGO:-off}" \
      -e PROFILE_FILE="${PROFILE_FILE:-/work/$build_root/$profile}" \
      -v "$PWD:/work:Z" -w /work "$image" python3 scripts/linux/build.py "$@"
    ;;
  train)
    podman run --rm --userns=keep-id --network=none "${runtime_env[@]}" \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 scripts/pgo-train.py "$bundle" "$@"
    ;;
  test)
    mkdir -p "$build_root/acceptance"
    podman run --rm --userns=keep-id --network=none "${runtime_env[@]}" \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 tests/run.py "$bundle" --prepare --fixtures "$build_root/test-fixtures" 2>&1 | tee "$build_root/acceptance/builder.log"
    podman build -t localhost/emacs-nox-runtime:debian13 -f containers/Runtime.Containerfile .
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD/$bundle:/bundle:ro,Z" -v "$PWD/tests:/tests:ro,Z" \
      -v "$PWD/$build_root/test-fixtures:/fixtures:ro,Z" \
      localhost/emacs-nox-runtime:debian13 \
      python3 /tests/run.py /bundle --fixtures /fixtures 2>&1 | tee "$build_root/acceptance/debian13.log"
    python3 - "$bundle" "$build_root" <<'PY'
import hashlib, json, pathlib, sys
bundle = pathlib.Path(sys.argv[1])
hashes = {str(f.relative_to(bundle)): hashlib.sha256(f.read_bytes()).hexdigest()
          for f in sorted(bundle.rglob('*')) if f.is_file() and not f.is_symlink()}
(pathlib.Path(sys.argv[2]) / 'acceptance/bundle-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
PY
    ;;
  test-interactive)
    podman run --rm --userns=keep-id --network=none "${runtime_env[@]}" \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 scripts/prepare-workload-packages.py "$bundle"
    podman run --rm --userns=keep-id --network=none "${runtime_env[@]}" \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 scripts/linux/benchmark-interactive.py "$bundle" --label ci --runs 1
    ;;
  package)
    podman run --rm --userns=keep-id --network=none "${runtime_env[@]}" \
      -v "$PWD:/work:Z" -w /work "$image" python3 scripts/linux/package.py "$bundle" "$@"
    ;;
  rpm)
    podman build -t localhost/emacs-nox-rpm:fedora44 -f containers/RPM.Containerfile .
    podman run --rm --userns=keep-id --network=none "${runtime_env[@]}" \
      -v "$PWD:/work:Z" -w /work localhost/emacs-nox-rpm:fedora44 python3 scripts/linux/rpm.py "$bundle"
    ;;
  test-rpm)
    podman build -t localhost/emacs-nox-rpm-test:fedora44 -f containers/RPMTest.Containerfile .
    mkdir -p "$build_root/acceptance"
    podman run --rm --network=none "${runtime_env[@]}" -v "$PWD:/work:ro,Z" \
      localhost/emacs-nox-rpm-test:fedora44 bash tests/rpm.sh 2>&1 | tee "$build_root/acceptance/rpm.log"
    ;;
  *) echo 'usage: container.sh image|build|train STAGE [--restart]|test STAGE|test-interactive STAGE|package STAGE [--force]|rpm STAGE|test-rpm' >&2; exit 2 ;;
esac
