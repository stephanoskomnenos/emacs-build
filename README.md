# emacs-build

构建 Emacs master：O2、ThinLTO、PGO，禁用 native-comp。
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
每次通过 Git 锁定 master commit，训练版、最终版和对照版使用同一份源码。
macOS 手动勾选 `compare` 才额外构建无 PGO 对照版；使用固定测试配置，原始性能样本在 `macos-build-report`。

Linux 本地构建需要 Podman、Python 3、Git 和 curl：

```sh
python3 scripts/update-master.py
python3 scripts/fetch.py
python3 scripts/fetch.py --tests
python3 scripts/fetch.py --benchmarks
python3 scripts/fetch.py --toolchain
bash scripts/container.sh image
PGO=generate bash scripts/container.sh build
bash scripts/container.sh train
PGO=use bash scripts/container.sh build
bash scripts/container.sh test
bash scripts/container.sh package
bash scripts/container.sh rpm
bash scripts/container.sh test-rpm
```

产物位于 `dist/`。macOS 构建使用一次性的 GitHub runner，沿用 [ebuild](https://github.com/RadioNoiseE/ebuild/tree/5f2e2c6229989d986f1072c7727a586d92bb8523) 的静态依赖配方，另加 SQLite，并检查 `.app` 的动态库和资源路径。
PGO 使用通用编辑、补全、Org、进程、Magit 和 ELPA 负载，macOS 另加 Cocoa 显示操作；个人配置只用于验证。方法与结果见 [benchmarks](benchmarks/README.md)。
