FROM ubuntu:latest

RUN apt-get update && apt-get install -y \
    procps \
    wget \
    git \
    rsync \
    python3 \
    python3-pip \
    python3-venv \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    && rm -rf /var/lib/apt/lists/*

ENV HOME=/root