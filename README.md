# emacs-build

构建 Emacs master：O2、ThinLTO，Linux 默认使用 CSPGO、macOS 默认使用普通 PGO，可选 CSPGO，禁用 native-comp。
启用 SQLite、GnuTLS、XML、tree-sitter、zlib、动态模块和线程；基础第三方库静态链接，系统库动态链接。

| 平台 | 版本 | 编译器 | 要求 |
| --- | --- | --- | --- |
| Linux | 终端 nox | Clang 23 | x86-64-v3、glibc ≥ 2.41 |
| macOS | Cocoa `Emacs.app` | Apple Clang | Apple Silicon |

## 下载与安装

从 [Actions](https://github.com/stephanoskomnenos/emacs-build/actions) 的成功构建下载：

- **Linux RPM**：安装 `emacs-nox-rpm-x86-64-v3` 中的 RPM，替换系统 Emacs。
- **Linux 归档**：解压 `emacs-nox-tar-x86-64-v3`，运行 `bin/emacs`，保留完整目录。
- **macOS**：解压 `Emacs-macos-arm64`，将 `Emacs.app` 放入 Applications。

```sh
sudo dnf install --allowerasing ./emacs-nox-*.x86_64.rpm
```

Linux 另启用 D-Bus 客户端支持；没有运行中的总线也可正常编辑。
Linux 的 terminfo、CA 证书，以及两平台的外置模块和 tree-sitter grammar，由系统或用户提供。
源码包和构建报告单独下载，安装无需下载它们。

## 构建

每周一北京时间 **01:23** 自动构建，也支持手动触发；**push 不触发**。
默认通过 Git 锁定 master commit；手动构建可用 `emacs_ref` 指定上游 commit 以复现构建。训练版、最终版和对照版使用同一份源码。
Linux 默认启用 CSPGO；手动取消 `cspgo` 即使用普通 PGO，省去第二轮插桩构建和训练。
macOS 的 `cspgo` 默认关闭；开启后先验证 Apple 工具链支持，再复用 PTY/GUI 负载训练第二轮。
`compare` 才额外构建一个对照版：普通 PGO 对比无 PGO，CSPGO 对比普通 PGO；原始样本在 `macos-build-report`。

Linux 本地构建需要 Podman、Python 3、Git 和 curl：

```sh
python3 scripts/update-master.py
python3 scripts/fetch.py
python3 scripts/fetch.py --tests
python3 scripts/fetch.py --benchmarks
bash scripts/linux/container.sh image
PGO=generate bash scripts/linux/container.sh build
bash scripts/linux/container.sh train generate
PGO=cs-generate bash scripts/linux/container.sh build
bash scripts/linux/container.sh train cs-generate
PGO=cs-use bash scripts/linux/container.sh build
bash scripts/linux/container.sh test cs-use
bash scripts/linux/container.sh package cs-use
bash scripts/linux/container.sh rpm cs-use
bash scripts/linux/container.sh test-rpm
```

本地仅用普通 PGO 时，跳过 `cs-generate` 和第二次 `train`，将 `cs-use` 改为 `use`。
用 `export EMACS_BUILD_ROOT=build/实验名` 隔离本地实验，依赖缓存仍共享，产物写入该目录的 `dist/`。
重新训练加 `--restart`；重建 Emacs 加 `--rebuild`（Mac 如 `python3 scripts/macos/build.py use --rebuild`），均保留依赖缓存。

产物位于 `dist/`。macOS 构建使用一次性的 GitHub runner，沿用 [ebuild](https://github.com/RadioNoiseE/ebuild/tree/5f2e2c6229989d986f1072c7727a586d92bb8523) 的静态依赖配方，另加 SQLite，并检查 `.app` 的动态库和资源路径。
PGO 使用通用编辑、补全、Org、进程、Magit 和 ELPA 负载，macOS 另加 Cocoa 显示操作；个人配置只用于验证。方法与结果见 [benchmarks](benchmarks/README.md)。

## 目录

- `scripts/linux/`、`scripts/macos/`：平台专用构建与测量；`scripts/` 根目录保留共用训练、下载和素材处理。
- `containers/`、`packaging/`：Linux 构建/验证环境与 RPM 配方。
- `tests/`：正确性和安装检查；`benchmarks/`：训练负载与性能验证。
- `benchmarks/results/`：历史测量与调查记录，不代表当前构建设置。
- `.github/workflows/`：两平台自动构建；`sources.json`：Linux 与共享源码锁定；`sources-macos.json` 引用共享项并锁定 Mac 独有依赖；其余清单锁定测试输入。
- `build/`、`cache/`、`dist/`：本地构建文件、缓存和产物，不纳入 Git。
