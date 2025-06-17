# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the AWS Cost Analyzer

```bash
# Full analysis with default settings (ap-southeast-2 region)
python aws_cost_analyzer.py

# Analyze specific region with account name
python aws_cost_analyzer.py --region us-east-1 --account-name "Production Account"

# Generate only the manifest file for multi-account dashboard
python aws_cost_analyzer.py --generate-manifest-only

# Generate standalone dashboard (no web server needed)
python aws_cost_analyzer.py --generate-standalone-dashboard

# Alternative: Generate standalone dashboard separately
python generate_standalone_dashboard.py

# Run with verbose logging
python aws_cost_analyzer.py -v

### Updating AWS Pricing Data

```bash
# Fetch current AWS pricing from AWS Price List API
python fetch_aws_pricing.py --region ap-southeast-2 --verbose

# Or for a different region
python fetch_aws_pricing.py --region us-east-1 --verbose
```

### Two-Stage Process (for manual control)

```bash
# Stage 1: Scan AWS resources
python aws_scanner.py

# Stage 2: Estimate costs and generate reports
python cost_estimator.py
python report_generator.py
```

### Testing and Development

```bash
# Install dependencies
pip install -r requirements.txt

# View multi-account dashboard locally (original method)
python -m http.server 8080
# Then navigate to http://localhost:8080/dashboard.html

# Or open the standalone dashboard directly (no web server needed)
# Just double-click dashboard_standalone.html or open it in your browser
```

## High-Level Architecture

The AWS Cost Analyzer is a modular Python application that scans AWS resources across multiple accounts and generates cost analysis reports.

### Core Components

1. **aws_cost_analyzer.py** - Main orchestrator that coordinates the entire workflow:
   - Initializes AWS session and validates credentials
   - Calls scanner, estimator, and report generator in sequence
   - Manages multi-account data aggregation

2. **aws_scanner.py** - AWS resource discovery module:
   - Scans EC2 instances (including Auto Scaling Group membership)
   - Scans RDS clusters and standalone instances
   - Scans EKS clusters and node groups
   - Outputs structured JSON with all discovered resources

3. **cost_estimator.py** - Cost calculation engine:
   - Loads pricing from cost_config.json
   - Calculates hourly, daily, and monthly costs
   - Handles special cases (Multi-AZ RDS, EKS node pricing)
   - Aggregates costs by service and environment

4. **report_generator.py** - Report generation module:
   - Creates CSV reports (detailed and summary)
   - Generates interactive HTML reports with Chart.js
   - Produces JSON data files for multi-account dashboard
   - Includes cost savings calculator functionality

### Data Flow

```
AWS API → Scanner → JSON scan results → Cost Estimator → JSON cost data → Report Generator → Multiple outputs
                                                                                            ├── HTML reports
                                                                                            ├── CSV exports
                                                                                            └── JSON data files
```

### Multi-Account Architecture

- Each account analysis produces files with account ID suffix
- JSON data files are stored in reports/data/ directory
- dashboard.html aggregates all account data via manifest.json
- Manifest is automatically updated after each analysis

### Key Design Patterns

- **Environment Tagging**: Resources are grouped by 'environment' tag
- **Resource Classification**: EC2 instances marked with 'ConsumerManaged=true' are flagged as ephemeral
- **Cost Configuration**: Pricing data is externalized in cost_config.json
- **Modular Design**: Each component can run independently for debugging/testing