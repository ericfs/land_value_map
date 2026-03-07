FROM ubuntu:latest AS tippecanoe-builder

RUN apt-get update && apt-get install -y \
    build-essential \
    libsqlite3-dev \
    zlib1g-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone https://github.com/mapbox/tippecanoe.git && \
    cd tippecanoe && \
    make -j$(nproc)

FROM ubuntu:latest

RUN apt-get update && apt-get install -y \
    procps \
    wget \
    git \
    rsync \
    python3 \
    python3-pip \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Install tippecanoe from builder stage
COPY --from=tippecanoe-builder /build/tippecanoe/tippecanoe* /usr/local/bin/

# Install Python dependencies and Ansible globally (no venv needed in container)
RUN pip3 install --break-system-packages \
    ansible \
    geopandas \
    fiona \
    pyogc \
    contextily

RUN rm -rf /usr/share/nginx/html/*

ENV HOME=/root