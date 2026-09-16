FROM docker.io/library/debian:trixie-slim@sha256:abc9cb88a5587630d7f915f47b23b0668fe250fbfc6457aa4d52b534c1bbf73f
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 ca-certificates ncurses-base \
    && rm -rf /var/lib/apt/lists/*
