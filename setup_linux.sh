#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
printf '\nExecute: .venv/bin/python -m flask --app app create-admin\n'
printf 'Depois: .venv/bin/python run.py\n'
