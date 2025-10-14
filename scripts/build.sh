#! /bin/bash

# Expects to be run from the project root directory.

build_dir=`pwd`

# Assumes there is a virtual environment
python_interpreter="`pwd`/.venv/bin/python3"

ansible_variables="ansible_python_interpreter=\"${python_interpreter}\" working_dir=\"${build_dir}\""

ansible-playbook ansible/main.yml -e "${ansible_variables}"