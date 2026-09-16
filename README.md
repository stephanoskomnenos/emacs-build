# emacs-nox-build

Emacs 31.1，禁用 native-comp，使用预编译 GCC 15.3。
基础第三方库静态链接，glibc 动态链接；要求 x86-64-v3、glibc ≥ 2.41。
terminfo、CA 证书、外置模块及 tree-sitter grammar 由系统或用户提供。

## 构建

需要 Podman、Python 3、curl，以及支持 x86-64-v3 的 Linux 主机。

```sh
python3 scripts/fetch.py
python3 scripts/fetch.py --tests
python3 scripts/fetch.py --toolchain  # 仅为源码包下载 GCC，不编译
bash scripts/container.sh image
bash scripts/container.sh build
bash scripts/container.sh test
bash scripts/container.sh package
bash scripts/container.sh rpm
bash scripts/container.sh test-rpm
```

产物在 `dist/`：便携包、源码包、RPM 和 SHA256 校验文件。
默认 `JOBS=6`、`LTO=0`；重新打包可用 `package --force`。
GitHub Actions 自动执行同一流程并上传产物，也支持手动触发。

## 安装

RPM 提供标准 `emacs` / `emacsclient` 命令，替换 Fedora 自带 Emacs：

```sh
sudo dnf install --allowerasing ./dist/emacs-nox-portable-31.1-1.v3.x86_64.rpm
emacs -nw
```

便携包解压后运行 `bin/emacs`，保留完整目录即可搬移。
