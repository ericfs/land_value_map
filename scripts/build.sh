#! /bin/bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Expects to be run from the project root directory.

set -euo pipefail

build_dir=$(pwd)

# Detect if running inside a container
in_container() {
  [ -f /.dockerenv ] || [ -f /run/.containerenv ] || grep -qsm1 'docker\|lxc\|containerd' /proc/1/cgroup 2>/dev/null
}

if in_container; then
  # Running inside the dev container — execute the workflow directly.
  ansible-playbook ansible/main.yml -e "working_dir=\"${build_dir}\""
else
  # Running outside — build and run the dev container image.
  echo "Not inside a container. Building and running the dev container..."

  docker build -f .devcontainer/Dockerfile -t land-value-map-build .
  docker run --rm \
    -p 8080:80 \
    -v "${build_dir}:/workspaces/land_value_map" \
    -w /workspaces/land_value_map \
    land-value-map-build \
    bash scripts/build.sh
fi
