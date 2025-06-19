#!/bin/bash

# AWS Cost Optimization Project Setup Script

echo "Setting up AWS Cost Optimization Project..."

# Create directory structure
mkdir -p scripts
mkdir -p output
mkdir -p docs

# Set executable permissions
chmod +x scripts/aws_cost_data_collector.py

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Configure AWS credentials (aws configure or set AWS_PROFILE)"
echo "2. Run: source venv/bin/activate"
echo "3. Test collection: python scripts/aws_cost_data_collector.py --environment dev"
echo "4. Set up GitLab CI/CD variables for automated runs"