# AWS Instance Scheduler - Terraform Implementation

This repository contains a Terraform implementation of the AWS Instance Scheduler solution, which helps optimize costs by automatically starting and stopping resources based on custom schedules.

## Overview

The AWS Instance Scheduler is a solution originally provided by AWS as a CloudFormation template. This Terraform implementation provides the same functionality, allowing you to:

* Schedule EC2 instances
* Schedule RDS instances and clusters
* Schedule Neptune clusters
* Schedule DocumentDB clusters
* Schedule Auto Scaling Groups
* Use cross-account, cross-region scheduling
* Create custom schedules with various time zone support
* Automatically tag started/stopped resources
* Monitor savings with a CloudWatch dashboard

## Architecture

The solution uses a hub-and-spoke architecture:
- **Hub account**: Contains the scheduler configuration, logic, and orchestration
- **Spoke accounts**: Where resources are scheduled

## Prerequisites

- Terraform v1.0.0 or later
- AWS CLI configured with appropriate permissions
- S3 bucket with the Instance Scheduler Lambda code (the same one used by the CloudFormation template)

## Directory Structure

```
aws-instance-scheduler/
├── main.tf               # Main deployment file
├── variables.tf          # Input parameters
├── outputs.tf            # Stack outputs
├── locals.tf             # Local values and mappings
├── versions.tf           # Terraform and provider versions
├── data.tf               # Data sources
├── templates/            # Templates for CloudWatch dashboard
└── modules/              # Modular components
    ├── app_registry/     # Service Catalog AppRegistry
    ├── dynamodb/         # DynamoDB tables
    ├── iam/              # IAM roles and policies
    ├── kms/              # KMS key for encryption
    ├── lambda/           # Lambda functions
    ├── sns/              # SNS topic
    └── cloudwatch/       # CloudWatch resources
```

## Deployment Instructions

1. Clone this repository:
   ```bash
   git clone https://github.com/example/aws-instance-scheduler-terraform.git
   cd aws-instance-scheduler-terraform
   ```

2. Initialize Terraform:
   ```bash
   terraform init
   ```

3. Review and customize the variables in `terraform.tfvars` (create this file based on your requirements):
   ```hcl
   namespace           = "prod"
   schedule_ec2        = "Enabled"
   schedule_rds        = "Enabled" 
   default_timezone    = "America/New_York"
   regions             = "us-east-1,us-west-2"
   ```

4. Plan the deployment:
   ```bash
   terraform plan -out=plan.out
   ```

5. Apply the configuration:
   ```bash
   terraform apply plan.out
   ```

## Configuration

### Key Variables

- `tag_name`: Tag key used to identify resources for scheduling (default: "Schedule")
- `scheduler_frequency`: How often the scheduler runs in minutes (1-60)
- `default_timezone`: Default timezone for schedules
- `schedule_ec2`, `schedule_rds`, etc.: Enable/disable scheduling for specific services
- `namespace`: Namespace for resource naming (ensures uniqueness for multiple deployments)
- `principals`: Account IDs or Organization ID for cross-account scheduling
- `regions`: AWS regions for scheduling
- `memory_size`: Lambda memory size for the scheduler functions

### Creating Schedules

After deploying the solution, you can create schedules by:

1. Setting up periods in DynamoDB
2. Creating schedules referencing these periods
3. Tagging resources with the schedule name

## Cross-Account Setup

For cross-account scheduling:

1. Deploy this Terraform configuration in the hub account
2. Note the outputs from Terraform, particularly `scheduler_role_arn`
3. In each spoke account, create IAM roles that can be assumed by the hub account
4. Tag resources in spoke accounts with the schedule name

## Monitoring

The solution includes a CloudWatch dashboard that shows:
- Total instances controlled
- Running vs. stopped instances
- Hours saved by scheduling
- Breakdowns by instance type and schedule

## Clean Up

To remove the deployed resources:

```bash
terraform destroy
```

**Note**: If you've enabled DynamoDB deletion protection (`ddb_deletion_protection = "Enabled"`), you'll need to set it to `"Disabled"` and apply before destroying.

## Security Considerations

- KMS keys are used for encrypting DynamoDB tables and SNS topics
- IAM roles follow the principle of least privilege
- Cross-account access is tightly controlled

## License

This Terraform implementation is licensed under the MIT License.
