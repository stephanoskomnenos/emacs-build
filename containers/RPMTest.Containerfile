FROM registry.fedoraproject.org/fedora:44
# Start with distribution Emacs installed to exercise the replacement transaction.
RUN dnf install -y python3 emacs-nox coreutils ca-certificates ncurses-base \
    && dnf clean all
WORKDIR /work
