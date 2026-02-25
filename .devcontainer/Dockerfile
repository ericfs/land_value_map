FROM mcr.microsoft.com/devcontainers/python:3.11-bookworm

# Install GDAL and other geospatial dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    build-essential \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set up GDAL environment variables
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Install Ansible
RUN pip3 install --no-cache-dir ansible

# Optional: Install Python dependencies globally or in a venv later
# In the devcontainer, we often just use the system python or a venv
