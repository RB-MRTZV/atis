# AWS Permissions for Cost Optimization Project

This document outlines the minimum required AWS permissions for the cost optimization data collection and analysis.

## IAM Policy for Cost Optimization Data Collection

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BasicReadOnlyAccess",
            "Effect": "Allow",
            "Action": [
                "ec2:Describe*",
                "s3:ListAllMyBuckets",
                "s3:GetBucketLocation",
                "s3:ListBucket",
                "rds:Describe*",
                "lambda:List*",
                "lambda:Get*",
                "logs:Describe*",
                "efs:Describe*",
                "elasticloadbalancing:Describe*",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CostExplorerAccess",
            "Effect": "Allow",
            "Action": [
                "ce:GetCostAndUsage",
                "ce:GetUsageReport",
                "ce:GetDimensionValues",
                "ce:GetReservationCoverage",
                "ce:GetReservationPurchaseRecommendation",
                "ce:GetReservationUtilization",
                "ce:GetRightsizingRecommendation",
                "ce:GetSavingsPlansUtilization",
                "ce:GetSavingsPlansUtilizationDetails",
                "ce:GetSavingsPlansEstimatedMonthlySavings",
                "ce:GetSavingsPlansEstimatedMonthlyCost",
                "ce:GetSavingsPlansPurchaseRecommendation"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CostOptimizationHubAccess", 
            "Effect": "Allow",
            "Action": [
                "cost-optimization-hub:GetEnrollmentStatus",
                "cost-optimization-hub:ListRecommendations",
                "cost-optimization-hub:GetRecommendation",
                "cost-optimization-hub:ListEnrollmentStatuses"
            ],
            "Resource": "*"
        },
        {
            "Sid": "MacieReadOnlyAccess",
            "Effect": "Allow", 
            "Action": [
                "macie2:GetMacieSession",
                "macie2:ListClassificationJobs",
                "macie2:ListFindings",
                "macie2:GetFindings"
            ],
            "Resource": "*"
        },
        {
            "Sid": "TrustedAdvisorAccess",
            "Effect": "Allow",
            "Action": [
                "support:Describe*"
            ],
            "Resource": "*"
        }
    ]
}
```

## IAM Role for GitLab CI/CD

Create an IAM role with the above policy and add the following trust relationship:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::YOUR-ACCOUNT-ID:root"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "sts:ExternalId": "your-external-id"
                }
            }
        }
    ]
}
```

## Cost Optimization Hub Prerequisites

1. **Enrollment**: Cost Optimization Hub must be enabled in your AWS account
2. **Service-Linked Role**: AWS creates a service-linked role automatically when you enable the service
3. **Data Collection Period**: Allow 24-48 hours after enrollment for initial recommendations

### Enabling Cost Optimization Hub

```bash
# Using AWS CLI
aws cost-optimization-hub get-enrollment-status
aws cost-optimization-hub update-enrollment-status --status Active
```

## Minimum Permissions by Service

### Core Services (Required)
- **EC2**: `ec2:Describe*` - Instance and volume information
- **S3**: `s3:ListAllMyBuckets`, `s3:GetBucketLocation` - Storage analysis
- **RDS**: `rds:Describe*` - Database instance information
- **Lambda**: `lambda:List*`, `lambda:Get*` - Function configuration
- **CloudWatch Logs**: `logs:Describe*` - Log group information

### Cost Analysis (Essential)
- **Cost Explorer**: `ce:GetCostAndUsage` and related - Historical cost data
- **Cost Optimization Hub**: `cost-optimization-hub:*` - AWS recommendations

### Optional Services
- **Macie**: `macie2:GetMacieSession` - Data discovery service costs
- **Trusted Advisor**: `support:Describe*` - Additional optimization insights

## Security Best Practices

1. **Principle of Least Privilege**: Only grant permissions actually needed
2. **Resource-Level Permissions**: Use resource ARNs where possible (not applicable for most cost services)
3. **Conditional Access**: Add IP or time-based conditions if required
4. **Regular Review**: Audit permissions quarterly
5. **Cross-Account Access**: Use assume role pattern for multi-account scenarios

## Testing Permissions

Use the validation job in the GitLab pipeline to test permissions:

```bash
# Run permission validation
python scripts/aws_cost_data_collector.py --profile your-profile --environment dev
```

The script will report any permission issues encountered during data collection.