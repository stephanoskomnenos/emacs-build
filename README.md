# emacs-build

Emacs master，禁用 native-comp，使用 O2 + ThinLTO + PGO。
Linux 为 nox；macOS 为 Cocoa `Emacs.app`。

Linux 使用预编译 Clang 23。
基础第三方库静态链接，glibc 动态链接；要求 x86-64-v3、glibc ≥ 2.41。
terminfo、CA 证书、外置模块及 tree-sitter grammar 由系统或用户提供。

## 构建

需要 Podman、Python 3、curl，以及支持 x86-64-v3 的 Linux 主机。

```sh
python3 scripts/update-master.py  # 更新到当前 master；复现已有快照时跳过
python3 scripts/fetch.py
python3 scripts/fetch.py --tests
python3 scripts/fetch.py --benchmarks
python3 scripts/fetch.py --toolchain  # 仅为源码包下载 GCC，不编译
bash scripts/container.sh image
PGO=generate bash scripts/container.sh build
bash scripts/container.sh train
PGO=use bash scripts/container.sh build
bash scripts/container.sh test
bash scripts/container.sh package
bash scripts/container.sh rpm
bash scripts/container.sh test-rpm
```

产物在 `dist/`：便携包、源码包、RPM 和 SHA256 校验文件。
每次用通用终端操作、Magit 和 ELPA benchmark 重新训练，不使用个人配置。
Clang 来自 apt.llvm.org 的 23 分支快照；训练方法与对照结果见 [benchmarks](benchmarks/README.md)。
默认 `JOBS=6`、`LTO=1`；重新打包可用 `package --force`。
GitHub Actions 仅每周一北京时间 01:23 定时构建 master，或手动触发；push 不触发构建。
每次锁定 commit 和源码校验值；RPM、二进制包、源码包分别下载，安装只需 RPM。

## 安装

RPM 提供标准 `emacs` / `emacsclient` 命令，替换 Fedora 自带 Emacs：

```sh
sudo dnf install --allowerasing ./dist/emacs-nox-*.x86_64.rpm
emacs -nw
```

便携包解压后运行 `bin/emacs`，保留完整目录即可搬移。

## macOS

Actions 的 `Build macOS Emacs` 使用 Apple Clang 和同一 Xcode 的 llvm-profdata，
构建 Apple Silicon GUI 版。依赖配方来自 [ebuild](https://github.com/RadioNoiseE/ebuild/tree/5f2e2c6229989d986f1072c7727a586d92bb8523)，
保留静态链接处理；系统库和 Framework 动态链接，逐个检查 app 内的 Mach-O。
移除 Homebrew 只发生在一次性的 CI runner 上。

下载 `Emacs-macos-arm64`，解压得到 `Emacs.app`。每周和手动构建均重新训练；
手动勾选 `compare` 才额外构建无 PGO 对照版，交替测量 GUI 就绪、打开文件、滚动、布局、regexp 和 JSON。
对照版不上传，原始样本与链接检查在 `macos-build-report`。
训练使用通用 PTY、Magit、ELPA 和 Cocoa 显示操作，不使用个人配置。
GUI 键盘宏不等于 macOS 原生键盘事件；CI 对比采用固定测试配置，不能代表个人配置的启动时间。
