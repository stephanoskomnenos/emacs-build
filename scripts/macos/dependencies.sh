#!/bin/bash
set -euo pipefail
# Recipes from RadioNoiseE/ebuild@5f2e2c6229989d986f1072c7727a586d92bb8523.
# Run only on a disposable GitHub-hosted macOS runner.
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_OS:-}" == macOS ]] || exit 1
project_root=$PWD
build_jobs=${JOBS:-$(sysctl -n hw.logicalcpu)}
mkdir -p "$PWD/build/macos/dependencies"
cd "$PWD/build/macos/dependencies"

echo "::group::Install GNU M4"
(
  curl -fO https://ftp.gnu.org/gnu/m4/m4-1.4.21.tar.xz --retry 3
  tar -Jxf m4-1.4.21.tar.xz && cd m4-1.4.21
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Autoconf"
(
  curl -fO https://ftp.gnu.org/gnu/autoconf/autoconf-2.73.tar.xz --retry 3
  tar -Jxf autoconf-2.73.tar.xz && cd autoconf-2.73
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Automake"
(
  curl -fO https://ftp.gnu.org/gnu/automake/automake-1.19.tar.xz --retry 3
  tar -Jxf automake-1.19.tar.xz && cd automake-1.19
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libtool"
(
  curl -fO https://ftp.gnu.org/gnu/libtool/libtool-2.6.2.tar.xz --retry 3
  tar -Jxf libtool-2.6.2.tar.xz && cd libtool-2.6.2
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Pkgconf"
(
  curl -fLO https://github.com/pkgconf/pkgconf/archive/refs/tags/pkgconf-3.0.7.tar.gz --retry 3
  tar -zxf pkgconf-3.0.7.tar.gz && cd pkgconf-pkgconf-3.0.7
  ./autogen.sh && ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
  sudo ln -s /usr/local/bin/pkgconf /usr/local/bin/pkg-config
)
echo "::endgroup::"

echo "::group::Install GNU Texinfo"
(
  curl -fO https://ftp.gnu.org/gnu/texinfo/texinfo-7.3.tar.xz --retry 3
  tar -Jxf texinfo-7.3.tar.xz && cd texinfo-7.3
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libiconv"
(
  curl -fO https://ftp.gnu.org/gnu/libiconv/libiconv-1.19.tar.gz --retry 3
  tar -zxf libiconv-1.19.tar.gz && cd libiconv-1.19
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libunistring"
(
  curl -fO https://ftp.gnu.org/gnu/libunistring/libunistring-1.4.2.tar.xz --retry 3
  tar -Jxf libunistring-1.4.2.tar.xz && cd libunistring-1.4.2
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Gettext"
(
  curl -fO https://ftp.gnu.org/gnu/gettext/gettext-1.0.tar.xz --retry 3
  tar -Jxf gettext-1.0.tar.xz && cd gettext-1.0
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Ncurses"
(
  curl -fO https://ftp.gnu.org/gnu/ncurses/ncurses-6.6.tar.gz --retry 3
  tar -zxf ncurses-6.6.tar.gz && cd ncurses-6.6
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
  sudo ln -s /usr/local/include/ncursesw/curses.h /usr/local/include/ncurses.h
)
echo "::endgroup::"

echo "::group::Install Zlib"
(
  curl -fLO https://github.com/madler/zlib/releases/download/v1.3.2/zlib-1.3.2.tar.xz --retry 3
  tar -Jxf zlib-1.3.2.tar.xz && cd zlib-1.3.2
  ./configure --static && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libxml2"
(
  curl -fO https://download.gnome.org/sources/libxml2/2.15/libxml2-2.15.4.tar.xz --retry 3
  tar -Jxf libxml2-2.15.4.tar.xz && cd libxml2-2.15.4
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GNU Libgmp"
(
  curl -fO https://ftp.gnu.org/gnu/gmp/gmp-6.3.0.tar.xz --retry 3
  tar -Jxf gmp-6.3.0.tar.xz && cd gmp-6.3.0
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libnettle"
(
  curl -fO https://ftp.gnu.org/gnu/nettle/nettle-4.0.tar.gz --retry 3
  tar -zxf nettle-4.0.tar.gz && cd nettle-4.0
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libidn2"
(
  curl -fO https://ftp.gnu.org/gnu/libidn/libidn2-2.3.8.tar.gz --retry 3
  tar -zxf libidn2-2.3.8.tar.gz && cd libidn2-2.3.8
  ./configure --disable-shared && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install GnuTLS"
(
  curl -fO https://www.gnupg.org/ftp/gcrypt/gnutls/v3.8/gnutls-3.8.13.tar.xz --retry 3
  tar -Jxf gnutls-3.8.13.tar.xz && cd gnutls-3.8.13
  ./configure --disable-shared --with-included-libtasn1 --without-p11-kit && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

echo "::group::Install Libtreesitter"
(
  curl -fLO https://github.com/tree-sitter/tree-sitter/archive/refs/tags/v0.27.0.tar.gz --retry 3
  tar -zxf v0.27.0.tar.gz && cd tree-sitter-0.27.0
  make -j"$build_jobs"
  sudo make install
  sudo find /usr/local/lib -name 'libtree-sitter*.dylib' -delete
)
echo "::endgroup::"

echo "::group::Install GNU Gzip"
(
  curl -fO https://ftp.gnu.org/gnu/gzip/gzip-1.14.tar.xz --retry 3
  tar -Jxf gzip-1.14.tar.xz && cd gzip-1.14
  ./configure && make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"

# SQLite uses the same pinned source as Linux.
echo "::group::Install SQLite"
(
  read -r sqlite_url sqlite_sha < <(python3 -c 'import json, sys; s=json.load(open(sys.argv[1]))["sqlite"]; print(s["url"], s["sha256"])' "$project_root/sources.json")
  curl -fL --retry 3 "$sqlite_url" -o sqlite.tar.gz
  echo "$sqlite_sha  sqlite.tar.gz" | shasum -a 256 -c -
  mkdir sqlite
  tar -xf sqlite.tar.gz --strip-components=1 -C sqlite
  cd sqlite
  CC=/usr/bin/clang CFLAGS='-O2 -g0' ./configure --prefix=/usr/local --disable-shared --enable-static
  make -j"$build_jobs"
  sudo make install
)
echo "::endgroup::"
