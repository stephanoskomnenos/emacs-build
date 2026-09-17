#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
image=localhost/emacs-builder:clang23
case "${1:-build}" in
  image)
    podman build -t "$image" -f containers/Containerfile .
    ;;
  build)
    podman run --rm --userns=keep-id --network=none \
      -e JOBS="${JOBS:-$(nproc)}" -e LTO="${LTO:-1}" \
      -e PGO="${PGO:-off}" \
      -e PROFILE_FILE="${PROFILE_FILE:-/work/build/merged.profdata}" \
      -v "$PWD:/work:Z" -w /work "$image" python3 scripts/build.py
    ;;
  train)
    bundle=$(cat build/current-bundle)
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 scripts/pgo-train.py "$bundle"
    ;;
  test)
    bundle=$(cat build/current-bundle)
    mkdir -p build/acceptance
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 tests/run.py "$bundle" --prepare 2>&1 | tee build/acceptance/builder.log
    podman build -t localhost/emacs-nox-runtime:debian13 -f containers/Runtime.Containerfile .
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD/$bundle:/bundle:ro,Z" -v "$PWD/tests:/tests:ro,Z" \
      -v "$PWD/build/test-fixtures:/fixtures:ro,Z" \
      localhost/emacs-nox-runtime:debian13 \
      python3 /tests/run.py /bundle --fixtures /fixtures 2>&1 | tee build/acceptance/debian13.log
    python3 - "$bundle" <<'PY'
import hashlib, json, pathlib, sys
bundle = pathlib.Path(sys.argv[1])
hashes = {str(f.relative_to(bundle)): hashlib.sha256(f.read_bytes()).hexdigest()
          for f in sorted(bundle.rglob('*')) if f.is_file() and not f.is_symlink()}
pathlib.Path('build/acceptance/bundle-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
PY
    ;;
  test-interactive)
    bundle=$(cat build/current-bundle)
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 scripts/prepare-workload-packages.py "$bundle"
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD:/work:Z" -w /work "$image" \
      python3 scripts/benchmark-interactive.py "$bundle" --label ci --runs 1
    ;;
  package)
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD:/work:Z" -w /work "$image" python3 scripts/package.py "${@:2}"
    ;;
  rpm)
    podman build -t localhost/emacs-nox-rpm:fedora44 -f containers/RPM.Containerfile .
    podman run --rm --userns=keep-id --network=none \
      -v "$PWD:/work:Z" -w /work localhost/emacs-nox-rpm:fedora44 python3 scripts/rpm.py
    ;;
  test-rpm)
    podman build -t localhost/emacs-nox-rpm-test:fedora44 -f containers/RPMTest.Containerfile .
    mkdir -p build/acceptance
    podman run --rm --network=none -v "$PWD:/work:ro,Z" \
      localhost/emacs-nox-rpm-test:fedora44 bash tests/rpm.sh 2>&1 | tee build/acceptance/rpm.log
    ;;
  *) echo 'usage: bash scripts/container.sh [image|build|train|test|test-interactive|package [--force]|rpm|test-rpm]' >&2; exit 2 ;;
esac
