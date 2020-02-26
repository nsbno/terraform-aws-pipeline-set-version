#!/usr/bin/env bash
#
# Copyright (C) 2020 Erlend Ekern <dev@ekern.me>
#
# Distributed under terms of the MIT license.

set -euo pipefail
IFS=$'\n\t'

lambda_file="./main.py"
venv_folder="./.env_$(date +'%s')"

python3.7 -m venv "$venv_folder"
source "$venv_folder/bin/activate"

pip install -r ci_requirements.txt
flake8 "$lambda_file"
black --check "$lambda_file"

rm -rf "$venv_folder"
