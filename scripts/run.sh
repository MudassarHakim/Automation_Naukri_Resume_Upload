#!/usr/bin/env bash
set -euo pipefail
VENV="$HOME/.venvs/naukri-job"
source "$VENV/bin/activate"
python "$HOME/naukri_job/naukri_resume_uploader.py" "$@"
