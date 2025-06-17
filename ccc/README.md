# AWS Cost Analyzer

A Python tool to scan AWS resources (EC2, RDS, EKS) and generate detailed cost estimation reports.

## Features

- **Resource Scanning**: Scans EC2 instances, RDS clusters/instances, and EKS nodes in ap-southeast-2 region
- **Environment Tagging**: Groups resources by environment tag
- **EC2 Classification**: Identifies Managed vs Ephemeral instances (based on ConsumerManaged tag)
- **ASG Detection**: Tracks EC2 instances in Auto Scaling Groups
- **Cost Estimation**: Calculates daily and monthly costs based on configurable pricing
- **Multiple Report Formats**: Generates CSV and HTML reports with charts

## Prerequisites

- Python 3.7+
- AWS credentials configured (via AWS CLI, environment variables, or IAM role)
- Required permissions: EC2, RDS, EKS, and Auto Scaling read access

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```bash
python aws_cost_analyzer.py
```

### Advanced Options

```bash
# Specify different region
python aws_cost_analyzer.py --region us-east-1

# Use custom cost configuration
python aws_cost_analyzer.py --config my_pricing.json

# Skip scanning (use existing scan results)
python aws_cost_analyzer.py --skip-scan

# Generate only CSV reports
python aws_cost_analyzer.py --skip-html

# Custom output prefix
python aws_cost_analyzer.py --output-prefix my_report
```

### Two-Stage Process

1. **Stage 1 - Scanning**: Run scanner separately
```bash
python aws_scanner.py
```

2. **Stage 2 - Cost Estimation**: Run estimation on saved results
```bash
python cost_estimator.py
python report_generator.py
```

## Output Files

- `aws_scan_results.json`: Raw scan data
- `cost_estimation_results.json`: Detailed cost calculations
- `cost_report.csv`: Detailed resource costs
- `cost_report_summary.csv`: Summary by service and environment
- `cost_report.html`: Interactive HTML report with charts

## Configuration

Update `cost_config.json` with your instance pricing. Format:

```json
{
  "ec2_pricing": {
    "t3.micro": 0.0104,
    "t3.small": 0.0208
  },
  "rds_pricing": {
    "db.t3.micro": 0.021,
    "db.t3.small": 0.041
  }
}
```

## Resource Detection

- **Environment**: Determined by `environment` tag
- **EC2 Type**: 
  - Ephemeral: `ConsumerManaged` tag = "true"
  - Managed: All others
- **Multi-AZ RDS**: Cost doubled for Multi-AZ deployments
- **EKS Nodes**: Uses EC2 pricing for node instances

## Error Handling

The tool includes authentication checks and will exit gracefully if:
- AWS credentials are not configured
- Required permissions are missing
- Resources are not accessible

## License

MIT