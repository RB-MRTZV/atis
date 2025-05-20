# EC2 Instance Scheduler: Tag-Based Manual Shutdown Pipeline

Based on your revised requirements, I'll design a GitLab CI/CD pipeline with Python scripts to stop EC2 instances with a specific tag across multiple AWS accounts and regions.
<antArtifact None>
import React from 'react';
import { Server, GitBranch, Terminal, Send, FileText, Settings } from 'lucide-react';

const ArchitectureDiagram = () => {
  // Component styles
  const boxStyle = "rounded-lg border-2 border-gray-300 p-3 shadow-md flex flex-col items-center justify-center text-center";
  const arrowStyle = "border-t-2 border-gray-400";
  const labelStyle = "px-2 py-1 bg-gray-100 text-xs rounded absolute";
  const awsOrange = "#FF9900";
  const awsBlue = "#232F3E";
  const gitlabColor = "#FC6D26";
  
  return (
    <div className="w-full h-full flex flex-col items-center p-4">
      <h2 className="text-xl font-bold mb-6">EC2 Instance Scheduler - GitLab Pipeline Architecture</h2>
      
      <div className="relative w-full h-full max-w-4xl">
        {/* GitLab Pipeline */}
        <div className="absolute left-4 top-4 w-64 h-32 bg-white rounded-lg border-2 border-gray-300 shadow-md flex flex-col items-center justify-center">
          <GitBranch size={28} color={gitlabColor} className="mb-2" />
          <div className="text-sm font-semibold">GitLab CI/CD Pipeline</div>
          <div className="text-xs mt-1">Manual Trigger</div>
        </div>
        
        {/* Configuration File */}
        <div className="absolute left-4 top-48 w-64 h-28 bg-white rounded-lg border-2 border-gray-300 shadow-md flex flex-col items-center justify-center">
          <Settings size={24} className="mb-2" />
          <div className="text-sm font-semibold">Configuration</div>
          <div className="text-xs mt-1">AWS Accounts/Regions/Tags</div>
        </div>
        
        {/* Python Script */}
        <div className="absolute left-1/2 top-1/3 transform -translate-x-1/2 w-72 h-40 bg-white rounded-lg border-2 border-gray-300 shadow-md flex flex-col items-center justify-center">
          <Terminal size={28} className="mb-2" />
          <div className="text-sm font-semibold">Python Script</div>
          <div className="text-xs mt-1">Process AWS Accounts</div>
          <div className="text-xs">Find & Stop Tagged Instances</div>
          <div className="text-xs">Generate Report</div>
        </div>
        
        {/* AWS Environment */}
        <div className="absolute right-4 top-4 w-64 h-80 bg-blue-50 rounded-lg border-2 border-gray-300 shadow-md p-3">
          <div className="text-sm font-semibold text-center mb-3">Multiple AWS Accounts</div>
          
          {/* Account 1 */}
          <div className="mb-3 bg-white rounded p-2 shadow-sm">
            <div className="text-xs font-semibold mb-1">Account: Production</div>
            <div className="text-xs">Region: us-east-1</div>
            <div className="flex items-center mt-2">
              <Server size={14} className="mr-1" color={awsOrange} />
              <div className="text-xs">EC2 with scheduled:enabled</div>
            </div>
          </div>
          
          {/* Account 2 */}
          <div className="mb-3 bg-white rounded p-2 shadow-sm">
            <div className="text-xs font-semibold mb-1">Account: Staging</div>
            <div className="text-xs">Region: eu-west-1</div>
            <div className="flex items-center mt-2">
              <Server size={14} className="mr-1" color={awsOrange} />
              <div className="text-xs">EC2 with scheduled:enabled</div>
            </div>
          </div>
          
          {/* Account 3 */}
          <div className="bg-white rounded p-2 shadow-sm">
            <div className="text-xs font-semibold mb-1">Account: Development</div>
            <div className="text-xs">Region: ap-southeast-2</div>
            <div className="flex items-center mt-2">
              <Server size={14} className="mr-1" color={awsOrange} />
              <div className="text-xs">EC2 with scheduled:enabled</div>
            </div>
          </div>
        </div>
        
        {/* Reports */}
        <div className="absolute left-4 bottom-24 w-64 h-32 bg-white rounded-lg border-2 border-gray-300 shadow-md flex flex-col items-center justify-center">
          <FileText size={24} className="mb-2" />
          <div className="text-sm font-semibold">Detailed Report</div>
          <div className="text-xs mt-1">Instances stopped</div>
          <div className="text-xs">Errors/Failures</div>
          <div className="text-xs">Cost estimation</div>
        </div>
        
        {/* SNS Notification */}
        <div className="absolute right-4 bottom-24 w-64 h-32 bg-white rounded-lg border-2 border-gray-300 shadow-md flex flex-col items-center justify-center">
          <Send size={24} className="mb-2" color={awsOrange} />
          <div className="text-sm font-semibold">SNS Notification</div>
          <div className="text-xs mt-1">Existing SNS Topic</div>
          <div className="text-xs">Report Summary</div>
        </div>
        
        {/* Arrows */}
        {/* GitLab to Configuration */}
        <div className="absolute left-36 top-40 w-0 h-6 border-l-2 border-gray-400"></div>
        
        {/* Configuration to Python */}
        <div className="absolute left-72 top-62 w-32 h-0 border-t-2 border-gray-400"></div>
        <div className="absolute left-100 top-56 text-xs bg-gray-100 px-2 py-0.5 rounded">Read Config</div>
        
        {/* Python to AWS */}
        <div className="absolute right-72 top-28 w-32 h-0 border-t-2 border-gray-400"></div>
        <div className="absolute right-100 top-22 text-xs bg-gray-100 px-2 py-0.5 rounded">AWS CLI</div>
        
        {/* Python to Report */}
        <div className="absolute left-72 bottom-40 w-32 h-0 border-t-2 border-gray-400"></div>
        <div className="absolute left-100 bottom-46 text-xs bg-gray-100 px-2 py-0.5 rounded">Generate</div>
        
        {/* Report to SNS */}
        <div className="absolute left-72 bottom-40 w-180 h-0 border-t-2 border-gray-400"></div>
        <div className="absolute left-180 bottom-46 text-xs bg-gray-100 px-2 py-0.5 rounded">Send via SNS</div>
      </div>
      
      <div className="mt-8 w-full max-w-4xl text-sm border-t-2 border-gray-200 pt-4">
        <h3 className="font-bold mb-2">Process Flow:</h3>
        <ol className="list-decimal pl-5 space-y-1">
          <li>Pipeline is manually triggered in GitLab</li>
          <li>Python script reads account configuration file</li>
          <li>For each account & region, script authenticates and identifies tagged EC2 instances</li>
          <li>Matching instances are stopped and details are logged</li>
          <li>Detailed report is generated with success/failure information</li>
          <li>Report is sent via existing SNS topic</li>
        </ol>
      </div>
    </div>
  );
};

export default ArchitectureDiagram;
</antArtifact>


## Solution Design: Tag-Based EC2 Scheduler

Based on your requirements, I've designed a GitLab CI/CD pipeline approach that stops EC2 instances with the "scheduled:enabled" tag across multiple AWS accounts and regions.

### Key Components

1. **GitLab CI/CD Pipeline**: Manually triggered to execute the instance shutdown process
2. **Configuration File**: Contains AWS accounts, regions, and tag criteria 
3. **Python Script**: Core logic to process accounts and manage instances
4. **AWS CLI**: Used to interact with EC2 instances across accounts
5. **SNS Notification**: Delivers detailed execution report

### Implementation Details

#### 1. `.gitlab-ci.yml` File

```yaml
stages:
  - stop-instances

variables:
  # Set default values for environment variables
  AWS_DEFAULT_REGION: us-east-1
  TAG_KEY: "scheduled:enabled"

stop-ec2-instances:
  stage: stop-instances
  image: python:3.9-alpine
  before_script:
    - pip install boto3 awscli
    - aws --version
  script:
    - python ec2_scheduler.py
  rules:
    - when: manual
  artifacts:
    paths:
      - report.json
      - report.txt
    expire_in: 1 week
```

#### 2. Configuration File (`accounts.json`)

```json
{
  "accounts": [
    {
      "name": "Production",
      "account_id": "123456789012",
      "regions": ["us-east-1", "us-west-2"],
      "role_name": "EC2SchedulerRole"
    },
    {
      "name": "Development",
      "account_id": "987654321098",
      "regions": ["eu-west-1"],
      "role_name": "EC2SchedulerRole"
    }
  ],
  "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:instance-scheduler-notifications"
}
```

#### 3. Python Script (`ec2_scheduler.py`)

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

# Initialize report data
report = {
    "execution_id": f"scheduler-{int(time.time())}",
    "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "accounts_processed": [],
    "total_instances_stopped": 0,
    "total_errors": 0,
    "estimated_hourly_savings": 0.0
}

def assume_role(account_id, role_name):
    """Assume the specified role in the target account"""
    sts_client = boto3.client('sts')
    try:
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"EC2Scheduler-{int(time.time())}"
        )
        return response['Credentials']
    except ClientError as e:
        print(f"Error assuming role in account {account_id}: {e}")
        return None

def get_instance_hourly_cost(instance_type, region):
    """Estimate hourly cost for instance type (simplified)"""
    # This is a simplified cost estimation
    # In a production environment, you could use the AWS Price List API
    pricing = {
        't2.micro': 0.0116,
        't2.small': 0.023,
        't2.medium': 0.0464,
        'm5.large': 0.096,
        # Add more as needed
    }
    return pricing.get(instance_type, 0.10)  # Default to $0.10/hour if unknown

def stop_tagged_instances(credentials, region, tag_key):
    """Stop instances with the specified tag in the region"""
    if not credentials:
        return {"stopped": [], "errors": [], "savings": 0.0}
    
    # Create EC2 client with the assumed role credentials
    ec2 = boto3.client(
        'ec2',
        region_name=region,
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )
    
    results = {"stopped": [], "errors": [], "savings": 0.0}
    
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
                
                # Only stop instances that are running
                if instance_state == 'running':
                    try:
                        # Stop the instance
                        ec2.stop_instances(InstanceIds=[instance_id])
                        
                        # Calculate estimated hourly savings
                        hourly_cost = get_instance_hourly_cost(instance_type, region)
                        results["savings"] += hourly_cost
                        
                        # Get instance name tag if it exists
                        instance_name = "Unnamed"
                        for tag in instance.get('Tags', []):
                            if tag['Key'] == 'Name':
                                instance_name = tag['Value']
                                break
                        
                        # Add to stopped instances list
                        results["stopped"].append({
                            "instance_id": instance_id,
                            "instance_name": instance_name,
                            "instance_type": instance_type,
                            "hourly_cost": hourly_cost
                        })
                        
                        print(f"Stopped instance {instance_id} ({instance_name})")
                    
                    except ClientError as e:
                        error_message = str(e)
                        results["errors"].append({
                            "instance_id": instance_id,
                            "error": error_message
                        })
                        print(f"Error stopping instance {instance_id}: {error_message}")
        
        return results
    
    except ClientError as e:
        print(f"Error querying instances in region {region}: {e}")
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
            "instances_stopped": 0,
            "errors": 0,
            "hourly_savings": 0.0
        }
        
        # Assume role in the account
        credentials = assume_role(account_id, role_name)
        
        if not credentials:
            account_report["errors"] += 1
            account_report["error_message"] = "Failed to assume role"
            report["accounts_processed"].append(account_report)
            report["total_errors"] += 1
            continue
        
        # Process each region
        for region in account['regions']:
            print(f"Checking region: {region}")
            
            # Initialize region report
            region_report = {
                "region": region,
                "instances": [],
                "errors": []
            }
            
            # Get tag key from environment or default
            tag_key = os.environ.get('TAG_KEY', 'scheduled:enabled')
            
            # Stop instances with the tag
            results = stop_tagged_instances(credentials, region, tag_key)
            
            # Update region report
            region_report["instances"] = results["stopped"]
            region_report["errors"] = results["errors"]
            
            # Update account report
            account_report["regions_processed"].append(region_report)
            account_report["instances_stopped"] += len(results["stopped"])
            account_report["errors"] += len(results["errors"])
            account_report["hourly_savings"] += results["savings"]
        
        # Update the global report
        report["accounts_processed"].append(account_report)
        report["total_instances_stopped"] += account_report["instances_stopped"]
        report["total_errors"] += account_report["errors"]
        report["estimated_hourly_savings"] += account_report["hourly_savings"]
    
    # Save detailed JSON report
    with open('report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate text summary for SNS
    summary = f"""EC2 Instance Scheduler Report

Execution ID: {report['execution_id']}
Time: {report['execution_time']}

Summary:
- Accounts processed: {len(report['accounts_processed'])}
- Total instances stopped: {report['total_instances_stopped']}
- Total errors: {report['total_errors']}
- Estimated hourly savings: ${report['estimated_hourly_savings']:.2f}
- Estimated monthly savings: ${report['estimated_hourly_savings'] * 24 * 30:.2f}

See attached JSON report for details.
"""
    
    # Save text report
    with open('report.txt', 'w') as f:
        f.write(summary)
    
    # Send SNS notification
    send_sns_notification(
        config['sns_topic_arn'],
        f"EC2 Scheduler Report: {report['total_instances_stopped']} instances stopped",
        summary
    )
    
    print(f"\nExecution complete!")
    print(f"Stopped {report['total_instances_stopped']} instances")
    print(f"Encountered {report['total_errors']} errors")
    print(f"Estimated hourly savings: ${report['estimated_hourly_savings']:.2f}")

if __name__ == "__main__":
    main()
```

## Suggestions to Make This Approach More Robust

1. **Implement a Restoration Process**:
   - Create a companion pipeline to start instances that were previously stopped
   - Store instance state history to track which instances were auto-stopped

2. **Enhanced Error Handling**:
   - Add retry logic for AWS API calls
   - Implement circuit breakers to prevent cascading failures across accounts

3. **Improved Security**:
   - Store AWS account details in GitLab CI/CD variables or a secrets manager
   - Use least-privilege IAM roles with specific permissions

4. **Advanced Reporting**:
   - Integrate with a database to track historical data
   - Create trend analysis of cost savings over time

5. **Tag-Based Exclusions**:
   - Add support for "scheduled:exclude" tag to prevent stopping critical instances
   - Implement tag-based scheduling windows (e.g., stop only during weekends)

6. **Pre-Execution Checks**:
   - Verify IAM permissions before attempting to stop instances
   - Add a "dry-run" mode that reports what would be stopped without taking action

7. **Notification Enhancements**:
   - Add support for multiple notification channels (Slack, Email, etc.)
   - Create different notification levels based on importance

8. **Regional Isolation**:
   - Add error isolation to prevent failures in one region from affecting others
   - Process regions in parallel for faster execution

9. **Cost Estimation Improvements**:
   - Use the AWS Price List API for accurate pricing data
   - Consider instance utilization metrics for more accurate savings estimation

10. **Comprehensive Logging**:
    - Add detailed logging for each step of the process
    - Store logs in a centralized location for audit and troubleshooting

Would you like me to provide more details on any of these components or suggestions?​​​​​​​​​​​​​​​​