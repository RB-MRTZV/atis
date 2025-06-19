# AWS Cost Optimization Project

A comprehensive solution for AWS cost assessment and optimization across development and production environments.

## Project Structure

```
├── aws-cost-optimization-plan.md    # Detailed cost optimization strategies
├── scripts/
│   └── aws_cost_data_collector.py   # Python script for AWS data collection
├── .gitlab-ci.yml                   # GitLab CI/CD pipeline configuration
├── requirements.txt                 # Python dependencies
├── setup.sh                         # Project setup script
├── output/                          # Generated reports and data files
└── CLAUDE.md                        # Development guidance
```

## Quick Start

1. **Setup Environment**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Configure AWS Access**
   ```bash
   aws configure
   # OR set AWS_PROFILE environment variable
   export AWS_PROFILE=your-profile-name
   ```

3. **Run Data Collection**
   ```bash
   source venv/bin/activate
   python scripts/aws_cost_data_collector.py --environment dev --region us-east-1
   ```

## Stage 1: Cost Optimization Planning ✅

Comprehensive strategies developed for:
- **Storage**: S3 lifecycle policies, EBS optimization, EFS intelligent tiering
- **Log Retention**: CloudWatch logs optimization, automated archival
- **Snapshots/Backups**: Lifecycle management, orphaned resource cleanup
- **Network Costs**: Ingress/egress optimization, CDN usage
- **Amazon Macie**: Usage optimization, job scheduling
- **Compute**: Right-sizing, auto-scaling, reserved instances

## Stage 2: Data Gathering ✅

**Python Script Features:**
- Read-only AWS access across all relevant services
- Multi-region support
- Comprehensive data collection for cost analysis
- JSON output for further processing

**Collected Data:**
- S3 buckets and storage classes
- EBS volumes and snapshots
- EFS file systems
- EC2 instances and utilization
- Lambda functions
- RDS instances
- CloudWatch log groups
- Network resources (NAT gateways, load balancers)
- Amazon Macie configuration
- **Cost Explorer analysis** with service costs and trends
- **Cost Optimization Hub recommendations** with AWS-generated savings opportunities

## Stage 3: Analysis and Implementation

**GitLab CI/CD Pipeline:**
- Automated data collection for dev/prod environments
- Multi-region support
- Cost analysis and recommendation generation
- Scheduled runs for ongoing monitoring
- Security validation and permission checks

**Pipeline Stages:**
1. **collect-dev/prod**: Environment-specific data gathering
2. **analyze**: Process collected data and generate recommendations
3. **report**: Create human-readable optimization reports

## Usage Examples

### Manual Data Collection
```bash
# Development environment with Cost Explorer data
python scripts/aws_cost_data_collector.py --environment dev --region us-east-1 --cost-days 30

# Production environment with extended cost analysis
python scripts/aws_cost_data_collector.py --environment prod --region us-west-2 --cost-days 60

# Specific AWS profile
python scripts/aws_cost_data_collector.py --profile my-aws-profile --environment prod
```

### Cost Analysis
```bash
# Run comprehensive cost analysis on collected data
python scripts/cost_analyzer.py

# Analyze specific data file
python scripts/cost_analyzer.py --data-file output/aws_cost_data_dev_123456789_20231201_120000.json

# Custom output location
python scripts/cost_analyzer.py --output output/my_analysis.json
```

### GitLab CI/CD Variables

Set these variables in your GitLab project:

```bash
AWS_ACCESS_KEY_ID=<your-access-key>
AWS_SECRET_ACCESS_KEY=<your-secret-key>
AWS_REGION=us-east-1
ENVIRONMENT=dev  # or prod
```

### Scheduled Monitoring

The pipeline supports scheduled runs for ongoing cost monitoring:
- Weekly data collection
- Monthly comprehensive analysis
- Quarterly optimization reviews

## Security Considerations

- **Read-only access**: All AWS operations are read-only
- **Minimal permissions**: IAM roles with least-privilege access
- **Cost Explorer access**: Requires `ce:GetCostAndUsage` and related permissions
- **Cost Optimization Hub access**: Requires `cost-optimization-hub:*` permissions
- **No credential storage**: Uses GitLab CI/CD variables or AWS profiles
- **Audit trail**: All operations logged for compliance

## Output and Reports

Generated files in `output/` directory:
- `aws_cost_data_*.json`: Raw data collection results with Cost Explorer data
- `cost_analysis_detailed_*.json`: Comprehensive cost analysis with recommendations
- `pipeline_cost_summary.json`: Pipeline execution summary
- `cost_optimization_comprehensive_report.md`: Executive-ready optimization report

## Next Steps

1. **Implement High-Impact Optimizations**: Start with storage lifecycle policies
2. **Set Up Monitoring**: Configure regular pipeline runs
3. **Track Savings**: Monitor cost reductions over time
4. **Expand Scope**: Add additional AWS services as needed

## Additional Stages (Future)

Based on initial assessment, consider these additional stages:
- **Stage 4**: Automated implementation of low-risk optimizations
- **Stage 5**: Cost forecasting and budgeting
- **Stage 6**: Continuous optimization with machine learning

## Support

- Review `aws-cost-optimization-plan.md` for detailed strategies
- Check GitLab CI/CD logs for troubleshooting
- Validate AWS permissions using the pipeline's validation job