#!/bin/bash
set -euo pipefail
# Recipes from RadioNoiseE/ebuild@5f2e2c6229989d986f1072c7727a586d92bb8523.
# Run only on a disposable GitHub-hosted macOS runner.
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_OS:-}" == macOS ]] || exit 1
project_root=$(cd "$(dirname "$0")/../.." && pwd)
python3 "$project_root/scripts/fetch.py" --macos
build_jobs=${JOBS:-$(sysctl -n hw.logicalcpu)}
mkdir -p "$project_root/build/macos/dependencies"
cd "$project_root/build/macos/dependencies"

unpack() {
  local archive
  archive=$(python3 - "$project_root" "$1" <<'PYTHON'
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'scripts'))
from sources import load_sources
spec = load_sources('macos')[sys.argv[2]]
print(root / 'cache/sources' / (sys.argv[2] + '-' + spec['version'] + '.tar'))
PYTHON
  )
  # Only this recipe's disposable extraction is replaced on retry.
  rm -rf -- "$1"
  mkdir "$1"
  tar -xf "$archive" --strip-components=1 -C "$1"
  cd "$1"
}

echo "::group::Install GNU M4"
(
  unpack m4
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Autoconf"
(
  unpack autoconf
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Automake"
(
  unpack automake
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libtool"
(
  unpack libtool
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Pkgconf"
(
  unpack pkgconf
  ./autogen.sh && ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
  sudo ln -sf /usr/local/bin/pkgconf /usr/local/bin/pkg-config
)
echo "::endgroup::"

echo "::group::Install GNU Texinfo"
(
  unpack texinfo
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libiconv"
(
  unpack libiconv
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libunistring"
(
  unpack libunistring
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Gettext"
(
  unpack gettext
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Ncurses"
(
  unpack ncurses
  ./configure --prefix=/usr/local --disable-shared --disable-widec --enable-overwrite && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Zlib"
(
  unpack zlib
  ./configure --static && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libxml2"
(
  unpack libxml2
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libgmp"
(
  unpack gmp
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libnettle"
(
  unpack nettle
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libidn2"
(
  unpack libidn2
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GnuTLS"
(
  unpack gnutls
  ./configure --disable-shared --with-included-libtasn1 --without-p11-kit && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libtreesitter"
(
  unpack tree-sitter
  make -j"$build_jobs"
  sudo make install
  sudo find /usr/local/lib -name 'libtree-sitter*.dylib' -delete
)
echo "::endgroup::"

echo "::group::Install GNU Gzip"
(
  unpack gzip
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

# SQLite uses the same pinned source as Linux.
echo "::group::Install SQLite"
(
  unpack sqlite
  CC=/usr/bin/clang CFLAGS='-O2 -g0' ./configure --prefix=/usr/local --disable-shared --enable-static
  make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"
