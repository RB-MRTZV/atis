# AWS Cost Analyzer - Multi-Account Setup

This guide explains how to use the AWS Cost Analyzer across multiple AWS accounts with centralized reporting.

## System Overview

The multi-account system consists of:

- **Per-Account Reports**: Individual HTML reports for each account
- **Centralized Dashboard**: Single HTML dashboard aggregating all accounts
- **JSON Data Files**: Account data stored in `reports/data/` directory
- **CSV Exports**: Account-specific CSV files in `reports/csv/` directory

## Directory Structure

```
aws-cost-analyzer/
├── reports/
│   ├── data/                    # JSON data files per account
│   │   ├── 123456789012.json    # Account data
│   │   ├── 987654321098.json    # Account data
│   │   └── manifest.json        # Index of all accounts
│   ├── csv/                     # CSV exports per account
│   │   ├── cost_report_123456789012.csv
│   │   └── cost_report_123456789012_summary.csv
│   ├── cost_report_123456789012.html  # Individual account reports
│   └── cost_report_987654321098.html
├── dashboard.html               # Multi-account dashboard
├── aws_cost_analyzer.py         # Main analysis script
├── generate_manifest.py         # Manifest generator
└── ...
```

## Usage

### 1. Analyze Individual Accounts

Run the analyzer for each AWS account you want to analyze:

```bash
# Account 1 - Production
python aws_cost_analyzer.py --account-name "Production Account" --region ap-southeast-2

# Account 2 - Development  
python aws_cost_analyzer.py --account-name "Development Account" --region us-east-1

# Account 3 - Staging
python aws_cost_analyzer.py --account-name "Staging Account" --region eu-west-1
```

**Parameters:**
- `--account-name`: Friendly name for the account (optional but recommended)
- `--region`: AWS region to analyze (default: ap-southeast-2)
- `--verbose`: Enable detailed logging

### 2. View Multi-Account Dashboard

Open `dashboard.html` in your web browser to view the centralized dashboard.

**Dashboard Features:**
- **Account Selection**: View all accounts aggregated or individual accounts
- **Service Filtering**: Filter by EC2, RDS, EKS, or all services
- **Environment Filtering**: Filter by environment (prod, dev, staging, etc.)
- **Cost Thresholds**: Set minimum cost filters
- **Interactive Charts**: Cost distribution by account and service
- **Sortable Tables**: Click column headers to sort data
- **CSV Export**: Export filtered data to CSV

### 3. Update Manifest (Optional)

If you add/remove account data files manually, regenerate the manifest:

```bash
python aws_cost_analyzer.py --generate-manifest-only
```

## Multi-Account Workflow

### For Organizations with Multiple AWS Accounts

1. **Setup**: Configure AWS credentials for each account
2. **Scan**: Run the analyzer for each account:
   ```bash
   # Switch to Account 1 credentials
   export AWS_PROFILE=production
   python aws_cost_analyzer.py --account-name "Production"
   
   # Switch to Account 2 credentials  
   export AWS_PROFILE=development
   python aws_cost_analyzer.py --account-name "Development"
   ```
3. **View**: Open `dashboard.html` to see aggregated results

### For AWS Organizations

Use AWS Organizations to assume roles across accounts:

```bash
# Production account
aws sts assume-role --role-arn arn:aws:iam::123456789012:role/CostAnalysisRole --role-session-name cost-analysis
python aws_cost_analyzer.py --account-name "Production"

# Development account
aws sts assume-role --role-arn arn:aws:iam::987654321098:role/CostAnalysisRole --role-session-name cost-analysis  
python aws_cost_analyzer.py --account-name "Development"
```

## Dashboard Features

### Account Management
- **All Accounts View**: Aggregated cost analysis across all accounts
- **Individual Account View**: Focus on specific account
- **Account Comparison**: Side-by-side cost comparisons

### Filtering & Analysis
- **Service-Based Analysis**: Compare EC2 vs RDS vs EKS costs across accounts
- **Environment-Based Analysis**: Compare prod vs dev vs staging costs
- **Cost Threshold Filtering**: Focus on high-cost resources
- **Real-time Filtering**: Instant updates without page reload

### Data Export
- **Filtered CSV Export**: Export only the data you're viewing
- **Account-Specific Data**: Individual account CSV files
- **Cross-Account Reporting**: Aggregated data export

### Interactive Features
- **Sortable Tables**: Click any column header to sort
- **Visual Charts**: Interactive donut and bar charts
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Live Calculations**: Real-time cost aggregations

## File Naming Convention

All generated files use the AWS account ID for uniqueness:

- **JSON Data**: `reports/data/{account_id}.json`
- **HTML Reports**: `reports/cost_report_{account_id}.html`
- **CSV Reports**: `reports/csv/cost_report_{account_id}.csv`
- **Scan Results**: `aws_scan_results_{account_id}.json`
- **Cost Estimates**: `cost_estimation_results_{account_id}.json`

## Cost Savings Calculator

The dashboard includes a multi-account cost savings calculator:

- **Account Scope**: Apply savings to all accounts or specific accounts
- **Service Scope**: Calculate savings for specific services across accounts
- **Environment Scope**: Target specific environments across all accounts
- **Combined Scopes**: Mix and match for precise targeting

## Troubleshooting

### No Data in Dashboard
1. Ensure you've run the analyzer for at least one account
2. Check that JSON files exist in `reports/data/` directory
3. Regenerate manifest: `python aws_cost_analyzer.py --generate-manifest-only`

### Missing Account Data
1. Verify AWS credentials are configured correctly
2. Check account has necessary permissions (EC2, RDS, EKS read access)
3. Ensure the account ID is correct in generated files

### Dashboard Not Loading
1. Use a local web server: `python -m http.server 8080`
2. Access via `http://localhost:8080/dashboard.html`
3. Check browser console for JavaScript errors

## Best Practices

1. **Regular Updates**: Run analysis weekly or monthly for accurate trending
2. **Account Names**: Use descriptive account names for better reporting
3. **Consistent Regions**: Analyze the same regions across accounts
4. **Archive Data**: Keep historical data for cost trend analysis
5. **Access Control**: Secure the reports directory if containing sensitive data

## Next Steps

- Set up automated scheduling (cron jobs) for regular analysis
- Integrate with CI/CD pipelines for cost monitoring
- Create custom alerts based on cost thresholds
- Build trend analysis by comparing historical data