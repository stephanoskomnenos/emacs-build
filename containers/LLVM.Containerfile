FROM localhost/emacs-nox-builder:gcc16
# Versioned LLVM 23 packages from the upstream Debian repository (prebuilt).
ARG LLVM_PACKAGE_VERSION=1:23.1.2~++20260910044214+069ef0e7cb36-1~exp1~20260910044225.69
RUN curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key -o /usr/share/keyrings/llvm.asc \
    && echo 'deb [signed-by=/usr/share/keyrings/llvm.asc] https://apt.llvm.org/trixie/ llvm-toolchain-trixie-23 main' > /etc/apt/sources.list.d/llvm.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       clang-23=${LLVM_PACKAGE_VERSION} lld-23=${LLVM_PACKAGE_VERSION} \
       llvm-23=${LLVM_PACKAGE_VERSION} libclang-rt-23-dev=${LLVM_PACKAGE_VERSION} \
    && rm -rf /var/lib/apt/lists/*
