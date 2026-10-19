#!/bin/bash
set -euo pipefail

repo=stephanoskomnenos/emacs-build
checksum=(sha256sum -c)

case "$(uname -s)/$(uname -m)" in
  Darwin/arm64)
    mode=macos
    workflow=build-macos.yml
    artifact=Emacs-macos-arm64
    target=${1:-/Applications/Emacs.app}
    checksum=(shasum -a 256 -c)
    if [[ "$target" != /*/Emacs.app || -L "$target" ]]; then
      echo '安装路径必须是绝对路径，且以 /Emacs.app 结尾，不能是符号链接。' >&2
      exit 1
    fi
    ;;
  Linux/x86_64)
    workflow=build.yml
    mode=tar
    command -v dnf >/dev/null && mode=rpm
    mode=${1:-$mode}
    case "$mode" in
      rpm) artifact=emacs-nox-rpm-x86-64-v3 ;;
      tar) artifact=emacs-nox-tar-x86-64-v3 ;;
      *) echo '用法：./update.sh [rpm|tar]' >&2; exit 1 ;;
    esac
    target=$HOME/.local/opt/emacs-nox
    if [[ -L "$target" && "$mode" == tar ]]; then
      echo "安装目录不能是符号链接：${target}" >&2
      exit 1
    fi
    ;;
  *) echo '仅支持 Apple Silicon macOS 和 x86_64 Linux。' >&2; exit 1 ;;
esac

run=$(gh run list --repo "$repo" --workflow "$workflow" --branch main \
  --status success --limit 1 --json databaseId --jq '.[0].databaseId // empty')
if [[ -z "$run" ]]; then
  echo '没有找到成功的构建。' >&2
  exit 1
fi

if [[ "$mode" == rpm ]]; then
  work=$(mktemp -d)
else
  mkdir -p "$(dirname "$target")"
  work=$(mktemp -d "$(dirname "$target")/.emacs-update.XXXXXX")
fi
trap '/bin/rm -rf "$work"' EXIT
gh run download "$run" --repo "$repo" --name "$artifact" --dir "$work"
(
  cd "$work"
  "${checksum[@]}" ./*.sha256
)

case "$mode" in
  macos)
    tar -xJf "$work/Emacs-macos-arm64.tar.xz" -C "$work"
    bundle=$work/Emacs.app
    "$bundle/Contents/MacOS/Emacs" --batch -Q --eval '(kill-emacs 0)'
    ;;
  tar)
    bundle=$work/bundle
    mkdir "$bundle"
    zstd -dc "$work"/*.tar.zst | tar -xf - --strip-components=1 -C "$bundle"
    "$bundle/bin/emacs" --batch -Q --eval '(kill-emacs 0)'
    ;;
esac

if pgrep -x 'Emacs|emacs|emacs-.*' >/dev/null; then
  echo '请先退出 Emacs（包括后台 daemon），再运行更新脚本。' >&2
  exit 1
fi

case "$mode" in
  rpm)
    if [[ "$EUID" == 0 ]]; then
      dnf install --allowerasing -y "$work"/emacs-nox-*.x86_64.rpm
    else
      sudo dnf install --allowerasing -y "$work"/emacs-nox-*.x86_64.rpm
    fi
    ;;
  macos|tar)
    /bin/rm -rf "$target"
    mv "$bundle" "$target"
    if [[ "$mode" == macos ]]; then
      xattr -dr com.apple.quarantine "$target"
    else
      mkdir -p "$HOME/.local/bin"
      ln -sfn "$target/bin/emacs" "$HOME/.local/bin/emacs"
      ln -sfn "$target/bin/emacsclient" "$HOME/.local/bin/emacsclient"
    fi
    ;;
esac
echo "已更新 Emacs（构建 ${run}）。"
