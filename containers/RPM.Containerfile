FROM registry.fedoraproject.org/fedora:44@sha256:9f7fd6627530115141f46c696178f45def9a0308035c868ace6c3868194e2eed
RUN dnf install -y rpm-build python3 zstd diffutils coreutils findutils \
    ncurses-base ca-certificates && dnf clean all
WORKDIR /work
