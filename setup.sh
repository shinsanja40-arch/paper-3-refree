#!/bin/bash

# Create directory structure for GitHub repository

echo "Creating directory structure..."

# Main directories
mkdir -p paper
mkdir -p data/{gpt_simulation,sonnet_simulation}/{round_logs,raw_data}
mkdir -p src/{personas,protocols,utils}
mkdir -p experiments/{configs,scripts}
mkdir -p notebooks
mkdir -p docs
mkdir -p tests

# Create __init__.py files for Python packages
touch src/__init__.py
touch src/personas/__init__.py
touch src/protocols/__init__.py
touch src/utils/__init__.py

echo "Directory structure created successfully!"
echo ""
echo "Structure:"
tree -L 2

echo ""
echo "Next steps:"
echo "1. Copy your paper PDF to paper/"
echo "2. Add simulation logs to data/"
echo "3. Implement source code in src/"
echo "4. Run experiments and analysis"
