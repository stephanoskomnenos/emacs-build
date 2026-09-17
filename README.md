# emacs-build

Emacs master，禁用 native-comp，使用预编译 Clang 23 + ThinLTO + PGO。
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
