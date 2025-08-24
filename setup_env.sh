#!/bin/bash
set -e

# Choose a name for the conda environment
ENV_NAME="updat_agent"

# Create new environment with Python 3.11
conda create -y -n $ENV_NAME python=3.11

# Activate it
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate $ENV_NAME

# Install required packages
pip install feedparser trafilatura beautifulsoup4 PyYAML python-dateutil

echo "Environment '$ENV_NAME' created and dependencies installed."
echo "Activate it anytime with: conda activate $ENV_NAME"