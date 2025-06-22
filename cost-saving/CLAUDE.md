# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS Cost Optimization Assessment and Implementation project with three main stages:
1. **Brief Solutions Planning** - Cost saving strategies for storage, log retention, snapshots/backups, ingress/egress, Macie, and compute utilization
2. **Data Gathering** - Python scripts with read-only AWS access via GitLab pipelines to collect service information
3. **Analysis and Implementation** - Assessment and execution of cost optimization recommendations

The project targets both dev and prod environments.

## Architecture

- **Documentation**: Markdown files for cost optimization strategies and implementation plans
- **Data Collection**: Python scripts using AWS SDK with read-only permissions
- **CI/CD**: GitLab pipelines for automated data gathering across AWS accounts
- **Environment Scope**: Separate assessments for development and production environments

## AWS Services Focus Areas

Key services and areas for cost optimization assessment:
- Storage services (S3, EBS, EFS)
- CloudWatch logs and retention policies
- EC2/RDS snapshots and backup strategies
- Network traffic (ingress/egress costs)
- Amazon Macie usage and configuration
- EC2/compute resource utilization monitoring

## Development Commands

**Setup:**
```bash
# Initial setup
chmod +x setup.sh && ./setup.sh
source venv/bin/activate
```

**Data Collection:**
```bash
# Recommended: Use wrapper script (auto-detects boto3 issues and falls back to CLI)
./collect_cost_data.sh --environment <dev|prod> --region <region> --cost-days <30|60>

# Direct script usage:
# boto3 version (original)
python3 scripts/aws_cost_data_collector.py --environment <dev|prod> --region <region> --cost-days <30|60>

# CLI-based version (use when boto3 version issues occur)
python3 scripts/aws_cost_data_collector_cli.py --environment <dev|prod> --region <region> --cost-days <30|60>

# Examples:
./collect_cost_data.sh --environment dev --cost-days 30
./collect_cost_data.sh --profile prod-profile --environment prod --cost-days 60
./collect_cost_data.sh --use-cli --environment dev  # Force CLI version
```

**Cost Analysis:**
```bash
# Run comprehensive cost analysis on collected data
python scripts/cost_analyzer.py

# Analyze specific data file
python scripts/cost_analyzer.py --data-file output/aws_cost_data_*.json
```

**Pipeline Validation:**
```bash
# Validate GitLab CI/CD configuration
gitlab-ci-local --preview
```

## Security Requirements

- All AWS access must be read-only
- Use IAM roles with minimal required permissions
- **Required AWS permissions:**
  - Standard read-only permissions for EC2, S3, RDS, Lambda, etc.
  - Cost Explorer: `ce:GetCostAndUsage`, `ce:GetRightsizingRecommendation`, `ce:GetReservationPurchaseRecommendation`
  - Cost Optimization Hub: `cost-optimization-hub:ListRecommendations`, `cost-optimization-hub:GetRecommendation`, `cost-optimization-hub:GetEnrollmentStatus`
- Never commit AWS credentials or sensitive account information
- Ensure all scripts follow AWS security best practices

## Cost Optimization Hub Integration

The project now integrates with AWS Cost Optimization Hub to leverage AWS-generated recommendations:
- Automated collection of Hub recommendations during data gathering
- Integration of Hub insights into cost analysis reports
- Priority-based categorization of AWS recommendations
- Implementation guidance based on effort level and rollback capability