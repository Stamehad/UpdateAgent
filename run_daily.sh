#!/bin/zsh
set -euo pipefail

# Always run from the repo root
cd "$(dirname "$0")"

# Activate conda env when running manually (safe no-op if conda not on PATH)
if command -v conda >/dev/null 2>&1; then
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate update_agent
fi

# Allow overriding the config without editing the file
CONFIG="${CONFIG:-config.yml}"

# Visible markers so you see something even when there are no new items
echo "[update_agent] START $(date +'%F %T')"
python -m src.main --config "$CONFIG"
ec=$?
echo "[update_agent] END   $(date +'%F %T') exit=$ec"
exit $ec