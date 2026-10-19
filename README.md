# emacs-build

构建 Emacs master：O2、ThinLTO，默认使用 CSPGO，可切换普通 PGO，禁用 native-comp。
启用 SQLite、GnuTLS、XML、tree-sitter、zlib、动态模块和线程；基础第三方库静态链接，系统库动态链接。

| 平台 | 版本 | 编译器 | 要求 |
| --- | --- | --- | --- |
| Linux | 终端 nox | Clang 23 | x86_64-v3、glibc ≥ 2.41 |
| macOS | Cocoa `Emacs.app` | LLVM Clang 23 | Apple Silicon |

## 安装与更新

安装 [GitHub CLI](https://cli.github.com/)，执行一次 `gh auth login`。退出 Emacs 后在本地运行：

```sh
./update.sh       # 自动选择平台和安装方式
./update.sh rpm   # Linux：指定 RPM
./update.sh tar   # Linux：指定归档
```

脚本下载主分支最新成功构建并校验 SHA-256，不保留旧版：

- **macOS**：替换 `/Applications/Emacs.app`，执行 `xattr -dr com.apple.quarantine`；首参可指定其他绝对路径下的 `Emacs.app`。
- **Linux**：有 `dnf` 时默认通过 `dnf install --allowerasing` 安装 RPM、替换系统 Emacs，普通用户调用 `sudo`；否则使用归档。
- **归档安装**：需要 `zstd`，安装到 `~/.local/opt/emacs-nox`，在 `~/.local/bin` 创建命令链接；该目录需在 `PATH` 中。

也可从 [Actions](https://github.com/stephanoskomnenos/emacs-build/actions) 手动下载产物。外置模块和 tree-sitter grammar 需自行提供；Linux 还需系统 terminfo 和 CA 证书。

## 构建

每周一北京时间 **01:23** 自动构建，也支持手动触发；**push 不触发**。
完整命令、依赖安装和验证步骤见 [Linux workflow](.github/workflows/build.yml) 和 [macOS workflow](.github/workflows/build-macos.yml)。手动构建参数：

- `emacs_ref`：上游分支、标签或 commit，默认 `master`。
- `cspgo`：默认开启，关闭后使用普通 PGO。
- `compare`：仅 macOS，额外构建无 PGO 版并对比，默认关闭。

macOS 静态依赖配方基于 [ebuild](https://github.com/RadioNoiseE/ebuild/tree/5f2e2c6229989d986f1072c7727a586d92bb8523)。训练方法见 [benchmarks](benchmarks/README.md)，性能数据见[同机对比](benchmarks/results/macos-llvm-pgo-20260918/README.md)。
