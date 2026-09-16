#!/usr/bin/env bash
# Run as container root in a disposable Fedora image, with /work read-only.
set -euo pipefail
cd /work
rpm_file=$(cat build/current-rpm)
system_emacs=$(rpm -q --whatprovides emacs-nox --qf '%{NAME}\n')
rpm -q "$system_emacs" emacs-common emacsclient
dnf --disablerepo='*' install --allowerasing -y "/work/$rpm_file"
for package in "$system_emacs" emacs-common emacsclient; do
    if rpm -q "$package"; then
        echo 'Distribution Emacs was not removed' >&2
        exit 1
    fi
done
rpm -V emacs-nox-portable
test "$(readlink /usr/bin/emacs)" = /opt/emacs-nox-portable/bin/emacs
test "$(readlink /usr/bin/emacsclient)" = /opt/emacs-nox-portable/bin/emacsclient
emacs -Q --batch --eval '(princ emacs-version)'
python3 - <<'PY'
import hashlib, json, pathlib
bundle = pathlib.Path('/opt/emacs-nox-portable')
for name, digest in json.loads((bundle / 'acceptance/bundle-hashes.json').read_text()).items():
    assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == digest, name
print('\nRPM payload matches the tested portable installation')
PY
python3 tests/run.py /opt/emacs-nox-portable --fixtures build/test-fixtures
rpm -V emacs-nox-portable
rpm -e emacs-nox-portable
test ! -e /opt/emacs-nox-portable
test ! -L /usr/bin/emacs
test ! -L /usr/bin/emacsclient
echo 'RPM REPLACE/RUN/REMOVE PASSED'
