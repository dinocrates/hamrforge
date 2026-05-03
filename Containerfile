FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="hamrforge-cpp-runner"
LABEL org.opencontainers.image.description="Minimal C++ grading runner image for HamrForge"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 hamrforge \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin hamrforge

WORKDIR /workspace

USER 1000:1000
