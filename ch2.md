# AWS Resource Scheduler for EC2 and Aurora PostgreSQL

I'll create a Markdown-based architecture diagram and update the solution to handle both EC2 instances and Aurora PostgreSQL clusters.

## Architecture Diagram

```
+----------------------------+
| GitLab CI/CD Pipeline      |
| (Manual Trigger START/STOP)|
+-------------+--------------+
              |
              v
+-------------+--------------+
| Configuration File         |
| accounts.json              |
+-------------+--------------+
              |
              v
+-------------+--------------+
|                            |
|   Python Script            |
|   - Process AWS Accounts   |
|   - Find Tagged Resources  |
|   - Start/Stop Resources   |
|   - Generate Report        |
|                            |
+-------------+--------------+
              |
              +------------------------+
              |                        |
              v                        v
+-------------+--------------+  +------+----------------+
| EC2 Management             |  | Aurora PostgreSQL     |
| - Find tagged instances    |  | - Find tagged clusters|
| - Start/Stop instances     |  | - Start/Stop clusters |
+-------------+--------------+  +------+----------------+
              |                        |
              v                        v
+-------------+------------------------+
|          AWS Accounts                |
|  +----------------------------+      |
|  | Account: Production        |      |
|  | - EC2 Instances            |      |
|  | - Aurora PostgreSQL        |      |
|  +----------------------------+      |
|                                      |
|  +----------------------------+      |
|  | Account: Development       |      |
|  | - EC2 Instances            |      |
|  | - Aurora PostgreSQL        |      |
|  +----------------------------+      |
+--------------------------------------+
              |
              v
+-------------+--------------+
| Report Generation          |
| - Success/failure counts   |
| - Cost savings estimation  |
+-------------+--------------+
              |
              v
+-------------+--------------+
| SNS Notification           |
| - Email Summary            |
| - Full Report Attachment   |
+----------------------------+
```

## Implementation Files

### 1. `.gitlab-ci.yml`

```yaml
stages:
  - manage-resources

variables:
  AWS_DEFAULT_REGION: us-east-1
  TAG_KEY: "scheduled:enabled"
  ACTION: "stop"      # Default action is to stop resources
  RESOURCE_TYPES: "ec2,aurora"  # Comma-separated list of resources to manage

manage-aws-resources:
  stage: manage-resources
  image: python:3.9-alpine
  before_script:
    - pip install boto3 awscli
    - aws --version
  script:
    - python aws_resource_scheduler.py
  rules:
    - when: manual
  artifacts:
    paths:
      - report.json
      - report.txt
    expire_in: 1 week
```

### 2. Configuration File (`accounts.json`)

```json
{
  "accounts": [
    {
      "name": "Production",
      "account_id": "123456789012",
      "regions": ["us-east-1", "us-west-2"],
      "role_name": "ResourceSchedulerRole"
    },
    {
      "name": "Development",
      "account_id": "987654321098",
      "regions": ["eu-west-1"],
      "role_name": "ResourceSchedulerRole"
    }
  ],
  "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:resource-scheduler-notifications"
}
```

### 3. Main Python Script (`aws_resource_scheduler.py`)

```python
#!/usr/bin/env python3
import boto3
import json
import time
import os
from datetime import datetime
from botocore.exceptions import ClientError

# Load configuration
with open('accounts.json', 'r') as f:
    config = json.load(f)

# Get action from environment variable (default to 'stop')
ACTION = os.environ.get('ACTION', 'stop').lower()
if ACTION not in ['start', 'stop']:
    print(f"Invalid action: {ACTION}. Using 'stop' as default.")
    ACTION = 'stop'

# Get resource types to manage
RESOURCE_TYPES = os.environ.get('RESOURCE_TYPES', 'ec2,aurora').lower().split(',')
print(f"Managing resource types: {', '.join(RESOURCE_TYPES)}")

# Initialize report data
report = {
    "execution_id": f"scheduler-{int(time.time())}",
    "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "action": ACTION,
    "resource_types": RESOURCE_TYPES,
    "accounts_processed": [],
    "total_resources_processed": {
        "ec2": 0,
        "aurora": 0
    },
    "total_errors": {
        "ec2": 0,
        "aurora": 0
    },
    "estimated_hourly_impact": {
        "ec2": 0.0,
        "aurora": 0.0,
        "total": 0.0
    }
}

def assume_role(account_id, role_name):
    """Assume the specified role in the target account"""
    sts_client = boto3.client('sts')
    try:
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"ResourceScheduler-{int(time.time())}"
        )
        return response['Credentials']
    except ClientError as e:
        print(f"Error assuming role in account {account_id}: {e}")
        return None

def get_instance_hourly_cost(instance_type, region):
    """Estimate hourly cost for EC2 instance type (simplified)"""
    pricing = {
        't2.micro': 0.0116,
        't2.small': 0.023,
        't2.medium': 0.0464,
        'm5.large': 0.096,
        # Add more as needed
    }
    return pricing.get(instance_type, 0.10)  # Default to $0.10/hour if unknown

def get_aurora_hourly_cost(instance_type, region):
    """Estimate hourly cost for Aurora PostgreSQL instance (simplified)"""
    pricing = {
        'db.r5.large': 0.29,
        'db.r5.xlarge': 0.58,
        'db.r5.2xlarge': 1.16,
        'db.r5.4xlarge': 2.32,
        'db.r6g.large': 0.25,
        'db.r6g.xlarge': 0.50,
        # Add more as needed
    }
    return pricing.get(instance_type, 0.35)  # Default to $0.35/hour if unknown

def manage_ec2_instances(credentials, region, tag_key, action):
    """Start or stop EC2 instances with the specified tag in the region"""
    if not credentials:
        return {"processed": [], "errors": [], "cost_impact": 0.0}
    
    # Create EC2 client with the assumed role credentials
    ec2 = boto3.client(
        'ec2',
        region_name=region,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    
    results = {"processed": [], "errors": [], "cost_impact": 0.0}
    
    try:
        # Find instances with the specified tag
        response = ec2.describe_instances(
            Filters=[
                {'Name': f'tag-key', 'Values': [tag_key]}
            ]
        )
        
        # Process each instance
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                instance_id = instance['InstanceId']
                instance_state = instance['State']['Name']
                instance_type = instance['InstanceType']
                
                # Determine if we should process this instance
                should_process = False
                
                if action == 'stop' and instance_state == 'running':
                    should_process = True
                elif action == 'start' and instance_state == 'stopped':
                    should_process = True
                
                if should_process:
                    try:
                        # Start or stop the instance
                        if action == 'stop':
                            ec2.stop_instances(InstanceIds=[instance_id])
                        else:  # action == 'start'
                            ec2.start_instances(InstanceIds=[instance_id])
                        
                        # Calculate estimated hourly cost impact
                        hourly_cost = get_instance_hourly_cost(instance_type, region)
                        if action == 'stop':
                            results["cost_impact"] += hourly_cost  # Savings (positive)
                        else:  # action == 'start'
                            results["cost_impact"] -= hourly_cost  # Cost (negative)
                        
                        # Get instance name tag if it exists
                        instance_name = "Unnamed"
                        for tag in instance.get('Tags', []):
                            if tag['Key'] == 'Name':
                                instance_name = tag['Value']
                                break
                        
                        # Add to processed instances list
                        results["processed"].append({
                            "resource_id": instance_id,
                            "resource_name": instance_name,
                            "resource_type": "EC2",
                            "instance_type": instance_type,
                            "previous_state": instance_state,
                            "new_state": "stopping" if action == 'stop' else "starting",
                            "hourly_cost": hourly_cost
                        })
                        
                        print(f"EC2: {action.capitalize()}ed instance {instance_id} ({instance_name})")
                    
                    except ClientError as e:
                        error_message = str(e)
                        results["errors"].append({
                            "resource_id": instance_id,
                            "resource_type": "EC2",
                            "error": error_message
                        })
                        print(f"Error {action}ing EC2 instance {instance_id}: {error_message}")
        
        return results
    
    except ClientError as e:
        print(f"Error querying EC2 instances in region {region}: {e}")
        return results

def manage_aurora_clusters(credentials, region, tag_key, action):
    """Start or stop Aurora PostgreSQL clusters with the specified tag in the region"""
    if not credentials:
        return {"processed": [], "errors": [], "cost_impact": 0.0}
    
    # Create RDS client with the assumed role credentials
    rds = boto3.client(
        'rds',
        region_name=region,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    
    results = {"processed": [], "errors": [], "cost_impact": 0.0}
    
    try:
        # Find Aurora PostgreSQL clusters with the specified tag
        paginator = rds.get_paginator('describe_db_clusters')
        cluster_pages = paginator.paginate()
        
        for page in cluster_pages:
            for cluster in page['DBClusters']:
                # Check if this is an Aurora PostgreSQL cluster
                if not cluster.get('Engine', '').startswith('aurora-postgresql'):
                    continue
                
                # Check if the cluster has the required tag
                has_tag = False
                for tag in rds.list_tags_for_resource(ResourceName=cluster['DBClusterArn'])['TagList']:
                    if tag['Key'] == tag_key:
                        has_tag = True
                        break
                
                if not has_tag:
                    continue
                
                cluster_id = cluster['DBClusterIdentifier']
                cluster_status = cluster['Status']
                
                # Determine if we should process this cluster
                should_process = False
                
                if action == 'stop' and cluster_status.lower() == 'available':
                    should_process = True
                elif action == 'start' and cluster_status.lower() == 'stopped':
                    should_process = True
                
                if should_process:
                    try:
                        # Count the number of instances in the cluster
                        instance_count = len(cluster['DBClusterMembers'])
                        total_hourly_cost = 0
                        
                        # Get the instance types for cost calculation
                        instance_types = []
                        for member in cluster['DBClusterMembers']:
                            instance_response = rds.describe_db_instances(
                                DBInstanceIdentifier=member['DBInstanceIdentifier']
                            )
                            if instance_response['DBInstances']:
                                instance_type = instance_response['DBInstances'][0]['DBInstanceClass']
                                instance_types.append(instance_type)
                                total_hourly_cost += get_aurora_hourly_cost(instance_type, region)
                        
                        # Start or stop the cluster
                        if action == 'stop':
                            rds.stop_db_cluster(DBClusterIdentifier=cluster_id)
                            results["cost_impact"] += total_hourly_cost  # Savings (positive)
                        else:  # action == 'start'
                            rds.start_db_cluster(DBClusterIdentifier=cluster_id)
                            results["cost_impact"] -= total_hourly_cost  # Cost (negative)
                        
                        # Add to processed clusters list
                        results["processed"].append({
                            "resource_id": cluster_id,
                            "resource_name": cluster_id,
                            "resource_type": "Aurora PostgreSQL",
                            "instance_count": instance_count,
                            "instance_types": instance_types,
                            "previous_state": cluster_status,
                            "new_state": "stopping" if action == 'stop' else "starting",
                            "hourly_cost": total_hourly_cost
                        })
                        
                        print(f"Aurora: {action.capitalize()}ed cluster {cluster_id} ({instance_count} instances)")
                    
                    except ClientError as e:
                        error_message = str(e)
                        results["errors"].append({
                            "resource_id": cluster_id,
                            "resource_type": "Aurora PostgreSQL",
                            "error": error_message
                        })
                        print(f"Error {action}ing Aurora cluster {cluster_id}: {error_message}")
        
        return results
    
    except ClientError as e:
        print(f"Error querying Aurora clusters in region {region}: {e}")
        return results

def send_sns_notification(topic_arn, subject, message):
    """Send SNS notification with report"""
    try:
        # Use the default credentials for SNS (not the assumed role)
        sns = boto3.client('sns')
        response = sns.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message
        )
        print(f"SNS notification sent (Message ID: {response['MessageId']})")
        return True
    except ClientError as e:
        print(f"Error sending SNS notification: {e}")
        return False

# Main execution
def main():
    # Process each account
    for account in config['accounts']:
        account_name = account['name']
        account_id = account['account_id']
        role_name = account['role_name']
        
        print(f"\nProcessing account: {account_name} ({account_id})")
        
        # Initialize account report
        account_report = {
            "account_name": account_name,
            "account_id": account_id,
            "regions_processed": [],
            "resources_processed": {
                "ec2": 0,
                "aurora": 0
            },
            "errors": {
                "ec2": 0,
                "aurora": 0
            },
            "cost_impact": {
                "ec2": 0.0,
                "aurora": 0.0,
                "total": 0.0
            }
        }
        
        # Assume role in the account
        credentials = assume_role(account_id, role_name)
        
        if not credentials:
            account_report["errors"]["ec2"] += 1
            account_report["errors"]["aurora"] += 1
            account_report["error_message"] = "Failed to assume role"
            report["accounts_processed"].append(account_report)
            report["total_errors"]["ec2"] += 1
            report["total_errors"]["aurora"] += 1
            continue
        
        # Process each region
        for region in account['regions']:
            print(f"Checking region: {region}")
            
            # Initialize region report
            region_report = {
                "region": region,
                "resources": {
                    "ec2": [],
                    "aurora": []
                },
                "errors": {
                    "ec2": [],
                    "aurora": []
                }
            }
            
            # Get tag key from environment or default
            tag_key = os.environ.get('TAG_KEY', 'scheduled:enabled')
            
            # Manage EC2 instances if needed
            if 'ec2' in RESOURCE_TYPES:
                ec2_results = manage_ec2_instances(credentials, region, tag_key, ACTION)
                region_report["resources"]["ec2"] = ec2_results["processed"]
                region_report["errors"]["ec2"] = ec2_results["errors"]
                account_report["resources_processed"]["ec2"] += len(ec2_results["processed"])
                account_report["errors"]["ec2"] += len(ec2_results["errors"])
                account_report["cost_impact"]["ec2"] += ec2_results["cost_impact"]
            
            # Manage Aurora PostgreSQL clusters if needed
            if 'aurora' in RESOURCE_TYPES:
                aurora_results = manage_aurora_clusters(credentials, region, tag_key, ACTION)
                region_report["resources"]["aurora"] = aurora_results["processed"]
                region_report["errors"]["aurora"] = aurora_results["errors"]
                account_report["resources_processed"]["aurora"] += len(aurora_results["processed"])
                account_report["errors"]["aurora"] += len(aurora_results["errors"])
                account_report["cost_impact"]["aurora"] += aurora_results["cost_impact"]
            
            # Calculate total cost impact for this region
            account_report["cost_impact"]["total"] = (
                account_report["cost_impact"]["ec2"] + 
                account_report["cost_impact"]["aurora"]
            )
            
            # Add region report to account report
            account_report["regions_processed"].append(region_report)
        
        # Update the global report
        report["accounts_processed"].append(account_report)
        report["total_resources_processed"]["ec2"] += account_report["resources_processed"]["ec2"]
        report["total_resources_processed"]["aurora"] += account_report["resources_processed"]["aurora"]
        report["total_errors"]["ec2"] += account_report["errors"]["ec2"]
        report["total_errors"]["aurora"] += account_report["errors"]["aurora"]
        report["estimated_hourly_impact"]["ec2"] += account_report["cost_impact"]["ec2"]
        report["estimated_hourly_impact"]["aurora"] += account_report["cost_impact"]["aurora"]
    
    # Calculate total cost impact
    report["estimated_hourly_impact"]["total"] = (
        report["estimated_hourly_impact"]["ec2"] + 
        report["estimated_hourly_impact"]["aurora"]
    )
    
    # Save detailed JSON report
    with open('report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate text summary for SNS
    if ACTION == 'stop':
        cost_message = (
            f"Estimated hourly savings: ${report['estimated_hourly_impact']['total']:.2f}\n"
            f"  EC2: ${report['estimated_hourly_impact']['ec2']:.2f}\n"
            f"  Aurora: ${report['estimated_hourly_impact']['aurora']:.2f}\n"
            f"Estimated monthly savings: ${report['estimated_hourly_impact']['total'] * 24 * 30:.2f}"
        )
    else:  # action == 'start'
        cost_message = (
            f"Estimated hourly cost: ${abs(report['estimated_hourly_impact']['total']):.2f}\n"
            f"  EC2: ${abs(report['estimated_hourly_impact']['ec2']):.2f}\n"
            f"  Aurora: ${abs(report['estimated_hourly_impact']['aurora']):.2f}\n"
            f"Estimated monthly cost: ${abs(report['estimated_hourly_impact']['total']) * 24 * 30:.2f}"
        )
    
    resource_message = (
        f"EC2 instances: {report['total_resources_processed']['ec2']} ({report['total_errors']['ec2']} errors)\n"
        f"Aurora clusters: {report['total_resources_processed']['aurora']} ({report['total_errors']['aurora']} errors)"
    )
    
    summary = f"""AWS Resource Scheduler Report

Action: {ACTION.upper()} resources
Execution ID: {report['execution_id']}
Time: {report['execution_time']}

Resources Processed:
{resource_message}

Cost Impact:
{cost_message}

See attached JSON report for details.
"""
    
    # Save text report
    with open('report.txt', 'w') as f:
        f.write(summary)
    
    # Send SNS notification
    total_resources = (
        report['total_resources_processed']['ec2'] + 
        report['total_resources_processed']['aurora']
    )
    
    send_sns_notification(
        config['sns_topic_arn'],
        f"AWS Scheduler Report: {total_resources} resources {ACTION}ed",
        summary
    )
    
    print(f"\nExecution complete!")
    print(f"{ACTION.capitalize()}ed resources:")
    print(f"  EC2 instances: {report['total_resources_processed']['ec2']}")
    print(f"  Aurora clusters: {report['total_resources_processed']['aurora']}")
    print(f"Errors: {report['total_errors']['ec2'] + report['total_errors']['aurora']}")
    
    if ACTION == 'stop':
        print(f"Estimated hourly savings: ${report['estimated_hourly_impact']['total']:.2f}")
    else:  # action == 'start'
        print(f"Estimated hourly cost: ${abs(report['estimated_hourly_impact']['total']):.2f}")

if __name__ == "__main__":
    main()
```

## Key Features of This Implementation

1. **Support for Both EC2 and Aurora PostgreSQL Clusters**
   - The script can handle both resource types in the same run
   - Resource types can be enabled/disabled via the `RESOURCE_TYPES` environment variable

2. **Aurora PostgreSQL-Specific Handling**
   - Detects all Aurora PostgreSQL clusters based on the engine type
   - Processes all instances in the cluster with a single command
   - Calculates total cost impact based on all instances in the cluster

3. **Detailed Cost Tracking**
   - Separate cost calculations for EC2 and Aurora resources
   - Estimates based on instance types
   - Aggregates costs across accounts and regions

4. **Comprehensive Error Handling**
   - Account-specific error tracking
   - Separate error counts for each resource type
   - Detailed error messages in the report

5. **Flexible Deployment Options**
   - Use GitLab variables to control behavior without modifying the code
   - Filter resources by different tags if needed
   - Select specific resource types to manage (EC2, Aurora, or both)

## GitLab CI/CD Usage Instructions

To run the pipeline:

1. **In GitLab UI**: Set variables and run manually
   - `ACTION`: Set to `start` or `stop`
   - `RESOURCE_TYPES`: Set to `ec2,aurora` or just one type
   - `TAG_KEY`: Defaults to `scheduled:enabled`

2. **Via GitLab CLI**:
   ```bash
   # To stop both EC2 instances and Aurora clusters
   gitlab-ci-pipeline-trigger --project=your-project-path --token=your-token --ref=main --variable ACTION=stop --variable RESOURCE_TYPES=ec2,aurora
   
   # To start only Aurora clusters
   gitlab-ci-pipeline-trigger --project=your-project-path --token=your-token --ref=main --variable ACTION=start --variable RESOURCE_TYPES=aurora
   ```

## Considerations for Production Use

1. **IAM Role Permissions**:
   - Ensure the assume role has the necessary permissions:
     - `ec2:DescribeInstances`, `ec2:StartInstances`, `ec2:StopInstances`
     - `rds:DescribeDBClusters`, `rds:DescribeDBInstances`, `rds:ListTagsForResource`
     - `rds:StartDBCluster`, `rds:StopDBCluster`

2. **Cost Estimation**:
   - For more accurate cost data, consider integrating with the AWS Price List API
   - Or maintain a more comprehensive pricing table

3. **Error Handling**:
   - The script continues processing even when errors occur
   - Consider adding retry logic for transient errors

4. **Schedule Coordination**:
   - If starting resources, ensure dependencies start in the correct order
   - For example, start databases before application servers

5. **Monitoring**:
   - Store historical reports for trend analysis
   - Consider adding CloudWatch metrics for long-term tracking

This implementation provides a robust solution for managing both EC2 instances and Aurora PostgreSQL clusters based on tags, with detailed reporting of actions taken and cost impacts.​​​​​​​​​​​​​​​​