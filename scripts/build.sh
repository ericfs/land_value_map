#! /bin/bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Expects to be run from the project root directory.

build_dir=`pwd`
venv_dir="${build_dir}/.venv"
# Create virtual environment if it doesn't exist
if [ ! -d "${venv_dir}" ]; then
  python3 -m venv ${venv_dir}
fi

source "${venv_dir}/bin/activate"

python_interpreter="${venv_dir}/bin/python3"

# Install Ansible
"${venv_dir}/bin/pip3" install ansible

ansible_variables="ansible_python_interpreter=\"${python_interpreter}\" working_dir=\"${build_dir}\""

ansible-playbook ansible/main.yml -e "${ansible_variables}"