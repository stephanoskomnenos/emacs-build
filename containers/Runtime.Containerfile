FROM docker.io/library/debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 ca-certificates ncurses-base \
    && rm -rf /var/lib/apt/lists/*
