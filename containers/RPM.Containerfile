FROM registry.fedoraproject.org/fedora:44
RUN dnf install -y rpm-build python3 zstd diffutils coreutils findutils \
    ncurses-base ca-certificates && dnf clean all
WORKDIR /work
