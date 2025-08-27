#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate update_agent

python -m src.main --limit 5 