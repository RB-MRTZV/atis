# AWS Cost Analysis Solution for Sydney Region

I'll update the solution to focus only on the Sydney region (ap-southeast-2) and use the specified AWS profile "profile_n" for authentication.

```python
import boto3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

# Define the regions we want to analyze
REGIONS = ['ap-southeast-2']  # Sydney region
PROFILE_NAME = 'profile_n'    # AWS profile to use

def create_session():
    """Create a boto3 session with the specified profile"""
    return boto3.Session(profile_name=PROFILE_NAME)

def get_account_id(session):
    """Get AWS account ID"""
    sts_client = session.client('sts')
    return sts_client.get_caller_identity()['Account']

def get_ec2_instances(session):
    """Get all EC2 instances in the specified regions"""
    instances = []
    
    for region in REGIONS:
        ec2_client = session.client('ec2', region_name=region)
        paginator = ec2_client.get_paginator('describe_instances')
        
        for page in paginator.paginate():
            for reservation in page['Reservations']:
                for instance in reservation['Instances']:
                    # Only include running instances
                    if instance['State']['Name'] == 'running':
                        environment = 'unknown'
                        
                        # Check for environment tag
                        if 'Tags' in instance:
                            for tag in instance['Tags']:
                                if tag['Key'] == 'asx_environment':
                                    environment = tag['Value']
                                    break
                        
                        instances.append({
                            'ResourceId': instance['InstanceId'],
                            'Region': region,
                            'Type': instance['InstanceType'],
                            'Environment': environment,
                            'ResourceType': 'EC2'
                        })
    
    return instances

def get_eks_nodes(session):
    """Get all EKS nodes in the specified regions"""
    nodes = []
    
    for region in REGIONS:
        eks_client = session.client('eks', region_name=region)
        ec2_client = session.client('ec2', region_name=region)
        
        # List EKS clusters
        try:
            clusters = eks_client.list_clusters()['clusters']
            
            for cluster_name in clusters:
                # Get cluster details
                cluster = eks_client.describe_cluster(name=cluster_name)['cluster']
                
                # Get node groups
                node_groups = eks_client.list_nodegroups(clusterName=cluster_name)['nodegroups']
                
                for ng_name in node_groups:
                    ng = eks_client.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng_name)['nodegroup']
                    
                    # Find EC2 instances associated with this node group
                    response = ec2_client.describe_instances(
                        Filters=[
                            {
                                'Name': 'tag:eks:cluster-name',
                                'Values': [cluster_name]
                            },
                            {
                                'Name': 'tag:eks:nodegroup-name',
                                'Values': [ng_name]
                            },
                            {
                                'Name': 'instance-state-name',
                                'Values': ['running']
                            }
                        ]
                    )
                    
                    for reservation in response['Reservations']:
                        for instance in reservation['Instances']:
                            environment = 'unknown'
                            
                            # Check for environment tag
                            if 'Tags' in instance:
                                for tag in instance['Tags']:
                                    if tag['Key'] == 'asx_environment':
                                        environment = tag['Value']
                                        break
                            
                            nodes.append({
                                'ResourceId': instance['InstanceId'],
                                'Region': region,
                                'Type': instance['InstanceType'],
                                'Environment': environment,
                                'ResourceType': 'EKS',
                                'ClusterName': cluster_name,
                                'NodeGroupName': ng_name
                            })
        except Exception as e:
            print(f"Error fetching EKS clusters in region {region}: {e}")
    
    return nodes

def get_rds_instances(session):
    """Get all RDS instances in the specified regions"""
    rds_instances = []
    
    for region in REGIONS:
        rds_client = session.client('rds', region_name=region)
        
        try:
            paginator = rds_client.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    # Only include available instances
                    if instance['DBInstanceStatus'] == 'available':
                        environment = 'unknown'
                        
                        # Check for environment tag
                        if 'TagList' in instance:
                            for tag in instance['TagList']:
                                if tag['Key'] == 'asx_environment':
                                    environment = tag['Value']
                                    break
                        
                        rds_instances.append({
                            'ResourceId': instance['DBInstanceIdentifier'],
                            'Region': region,
                            'Type': instance['DBInstanceClass'],
                            'Environment': environment,
                            'ResourceType': 'RDS',
                            'Engine': instance['Engine']
                        })
        except Exception as e:
            print(f"Error fetching RDS instances in region {region}: {e}")
    
    return rds_instances

def get_cost_data(session, account_id, start_date, end_date):
    """Get cost data from AWS Cost Explorer"""
    ce_client = session.client('ce')
    
    # Get costs by service
    response = ce_client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {
                'Type': 'DIMENSION',
                'Key': 'SERVICE'
            },
            {
                'Type': 'TAG',
                'Key': 'asx_environment'
            }
        ],
        Filter={
            'And': [
                {
                    'Dimensions': {
                        'Key': 'REGION',
                        'Values': REGIONS
                    }
                }
            ]
        }
    )
    
    cost_data = []
    
    for result in response['ResultsByTime']:
        for group in result['Groups']:
            service = group['Keys'][0]
            environment = group['Keys'][1].replace('asx_environment$', '') if '$' in group['Keys'][1] else 'untagged'
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            unit = group['Metrics']['UnblendedCost']['Unit']
            
            cost_data.append({
                'Service': service,
                'Environment': environment,
                'Amount': amount,
                'Unit': unit,
                'Period': result['TimePeriod']['Start']
            })
    
    return cost_data

def calculate_savings(all_resources, cost_data):
    """Calculate potential savings from scheduling resources"""
    # Calculate how many hours would be saved per week
    # Workday: 8 AM to 11 PM = 15 hours per day, 5 days = 75 hours
    # Full week: 24 hours * 7 days = 168 hours
    # Savings ratio: (168 - 75) / 168 = 0.5536 or about 55.36%
    
    savings_ratio = (168 - 75) / 168
    
    # Group resources by environment and type
    env_resources = defaultdict(lambda: defaultdict(int))
    
    for resource in all_resources:
        env = resource['Environment']
        res_type = resource['ResourceType']
        env_resources[env][res_type] += 1
    
    # Extract costs for EC2, EKS, and RDS
    service_map = {
        'EC2': 'Amazon Elastic Compute Cloud - Compute',
        'EKS': 'Amazon Elastic Container Service for Kubernetes',
        'RDS': 'Amazon Relational Database Service'
    }
    
    savings_by_env = {}
    
    for env in env_resources:
        env_costs = {
            'EC2': 0,
            'EKS': 0,
            'RDS': 0
        }
        
        # Find costs for this environment
        for item in cost_data:
            if item['Environment'] == env:
                for res_type, service_name in service_map.items():
                    if service_name in item['Service']:
                        env_costs[res_type] += item['Amount']
        
        # Calculate potential savings
        total_savings = 0
        for res_type in ['EC2', 'EKS', 'RDS']:
            if res_type != 'RDS':  # Assuming we don't want to stop RDS instances
                total_savings += env_costs[res_type] * savings_ratio
        
        savings_by_env[env] = {
            'current_cost': sum(env_costs.values()),
            'potential_savings': total_savings,
            'resource_counts': dict(env_resources[env])
        }
    
    return savings_by_env

def get_resource_family_distribution(all_resources):
    """Get distribution of instance family types"""
    family_distribution = defaultdict(lambda: defaultdict(int))
    
    for resource in all_resources:
        res_type = resource['ResourceType']
        instance_type = resource['Type']
        
        # Extract family from instance type (e.g., 't3' from 't3.medium')
        if res_type in ['EC2', 'EKS']:
            family = instance_type.split('.')[0]
        else:  # RDS
            family = instance_type
        
        family_distribution[res_type][family] += 1
    
    return family_distribution

def create_instance_scheduling_script():
    """Create a script for scheduling instances"""
    script = """#!/usr/bin/env python3
import boto3
import argparse
from datetime import datetime

def create_session(profile_name):
    return boto3.Session(profile_name=profile_name)

def start_instances(session, region, environment):
    ec2_client = session.client('ec2', region_name=region)
    
    # Find all stopped instances with the specified environment tag
    response = ec2_client.describe_instances(
        Filters=[
            {
                'Name': 'tag:asx_environment',
                'Values': [environment]
            },
            {
                'Name': 'instance-state-name',
                'Values': ['stopped']
            }
        ]
    )
    
    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_ids.append(instance['InstanceId'])
    
    if instance_ids:
        ec2_client.start_instances(InstanceIds=instance_ids)
        print(f"Started {len(instance_ids)} instances in {environment} environment")
    else:
        print(f"No stopped instances found in {environment} environment")

def stop_instances(session, region, environment):
    ec2_client = session.client('ec2', region_name=region)
    
    # Find all running instances with the specified environment tag
    response = ec2_client.describe_instances(
        Filters=[
            {
                'Name': 'tag:asx_environment',
                'Values': [environment]
            },
            {
                'Name': 'instance-state-name',
                'Values': ['running']
            }
        ]
    )
    
    instance_ids = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            # Check if instance has a 'NoScheduling' tag
            has_no_scheduling = False
            if 'Tags' in instance:
                for tag in instance['Tags']:
                    if tag['Key'] == 'NoScheduling' and tag['Value'].lower() == 'true':
                        has_no_scheduling = True
                        break
            
            if not has_no_scheduling:
                instance_ids.append(instance['InstanceId'])
    
    if instance_ids:
        ec2_client.stop_instances(InstanceIds=instance_ids)
        print(f"Stopped {len(instance_ids)} instances in {environment} environment")
    else:
        print(f"No running instances found in {environment} environment to stop")

def main():
    parser = argparse.ArgumentParser(description='Start or stop instances based on environment tag')
    parser.add_argument('--action', choices=['start', 'stop'], required=True, help='Action to perform')
    parser.add_argument('--region', default='ap-southeast-2', help='AWS region')
    parser.add_argument('--environment', required=True, help='Environment tag value')
    parser.add_argument('--profile', default='profile_n', help='AWS profile name')
    
    args = parser.parse_args()
    
    session = create_session(args.profile)
    
    if args.action == 'start':
        start_instances(session, args.region, args.environment)
    else:
        stop_instances(session, args.region, args.environment)

if __name__ == "__main__":
    main()
"""
    return script

def main():
    # Create boto3 session with the specified profile
    session = create_session()
    
    # Get account ID
    account_id = get_account_id(session)
    print(f"AWS Account ID: {account_id}")
    
    # Get resources
    ec2_instances = get_ec2_instances(session)
    eks_nodes = get_eks_nodes(session)
    rds_instances = get_rds_instances(session)
    
    all_resources = ec2_instances + eks_nodes + rds_instances
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(all_resources)
    
    # Print resource counts
    print("\nResource Counts by Environment:")
    env_counts = df.groupby(['Environment', 'ResourceType']).size().unstack(fill_value=0)
    print(env_counts)
    
    # Instance type distribution
    print("\nInstance Type Distribution:")
    type_dist = df.groupby(['ResourceType', 'Type']).size().reset_index(name='Count')
    print(type_dist)
    
    # Get instance family distribution
    family_dist = get_resource_family_distribution(all_resources)
    print("\nInstance Family Distribution:")
    for res_type, families in family_dist.items():
        print(f"\n{res_type}:")
        for family, count in families.items():
            print(f"  {family}: {count}")
    
    # Get cost data for the last month
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    cost_data = get_cost_data(
        session,
        account_id,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    # Calculate potential savings
    savings = calculate_savings(all_resources, cost_data)
    
    # Print savings analysis
    print("\nPotential Savings Analysis:")
    total_current_cost = 0
    total_potential_savings = 0
    
    for env, data in savings.items():
        print(f"\nEnvironment: {env}")
        print(f"  Current Monthly Cost: ${data['current_cost']:.2f}")
        print(f"  Potential Monthly Savings: ${data['potential_savings']:.2f}")
        print(f"  Savings Percentage: {(data['potential_savings'] / data['current_cost'] * 100) if data['current_cost'] > 0 else 0:.2f}%")
        print(f"  Resource Counts: {data['resource_counts']}")
        
        total_current_cost += data['current_cost']
        total_potential_savings += data['potential_savings']
    
    print(f"\nTotal Current Monthly Cost: ${total_current_cost:.2f}")
    print(f"Total Potential Monthly Savings: ${total_potential_savings:.2f}")
    print(f"Overall Savings Percentage: {(total_potential_savings / total_current_cost * 100) if total_current_cost > 0 else 0:.2f}%")
    
    # Create visualizations
    create_visualizations(df, savings)
    
    # Generate instance scheduling script
    scheduling_script = create_instance_scheduling_script()
    with open('schedule_instances.py', 'w') as f:
        f.write(scheduling_script)
    
    print("\nCreated instance scheduling script: schedule_instances.py")
    print("Usage examples:")
    print("  python schedule_instances.py --action stop --environment dev")
    print("  python schedule_instances.py --action start --environment dev")

def create_visualizations(df, savings):
    """Create visualizations for the analysis"""
    # Resource count by environment and type
    plt.figure(figsize=(12, 6))
    env_type_counts = df.groupby(['Environment', 'ResourceType']).size().unstack(fill_value=0)
    env_type_counts.plot(kind='bar', stacked=True)
    plt.title('Resource Count by Environment and Type')
    plt.xlabel('Environment')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig('resource_count_by_env.png')
    
    # Cost and savings by environment
    plt.figure(figsize=(12, 6))
    envs = list(savings.keys())
    current_costs = [savings[env]['current_cost'] for env in envs]
    potential_savings = [savings[env]['potential_savings'] for env in envs]
    
    x = range(len(envs))
    width = 0.35
    
    plt.bar(x, current_costs, width, label='Current Cost')
    plt.bar([i + width for i in x], potential_savings, width, label='Potential Savings')
    
    plt.xlabel('Environment')
    plt.ylabel('Cost ($)')
    plt.title('Current Cost vs Potential Savings by Environment')
    plt.xticks([i + width/2 for i in x], envs)
    plt.legend()
    plt.tight_layout()
    plt.savefig('cost_savings_by_env.png')
    
    # Instance family distribution
    plt.figure(figsize=(14, 8))
    family_data = df[df['ResourceType'] != 'RDS'].copy()
    family_data['Family'] = family_data['Type'].apply(lambda x: x.split('.')[0])
    family_counts = family_data.groupby(['Environment', 'Family']).size().unstack(fill_value=0)
    family_counts.plot(kind='bar', stacked=True)
    plt.title('EC2/EKS Instance Family Distribution by Environment')
    plt.xlabel('Environment')
    plt.ylabel('Count')
    plt.tight_layout()
    plt.savefig('instance_family_by_env.png')

if __name__ == "__main__":
    main()
```

## Key Improvements and Features

1. **Focus on Sydney Region (ap-southeast-2)**:
   - Limited all resource queries to only the Sydney region
   - Added region filtering in the Cost Explorer queries

2. **AWS Profile Authentication**:
   - Added boto3 session creation using 'profile_n' profile
   - All AWS clients now use this session for authentication

3. **Enhanced Analysis**:
   - Added instance family distribution analysis
   - Better visualization of instance families by environment

4. **Implementation Script**:
   - Created a complete scheduling script for starting/stopping instances
   - Added support for excluding instances from scheduling with a 'NoScheduling' tag
   - Script accepts parameters for different environments

## Scheduling Implementation

The solution includes a fully functional instance scheduling script that can be used with AWS CloudWatch Events/EventBridge to automate the scheduling:

1. **Schedule Rules**:
   - Create a rule to run the script with `--action stop` at 11 PM Monday-Friday
   - Create a rule to run the script with `--action start` at 8 AM Monday-Friday

2. **Sample CloudWatch Events rule (in CloudFormation)**:

```yaml
StopInstancesRule:
  Type: AWS::Events::Rule
  Properties:
    Description: "Stop instances at 11 PM on weekdays"
    ScheduleExpression: "cron(0 23 ? * MON-FRI *)"
    State: ENABLED
    Targets:
      - Arn: !GetAtt SchedulingLambdaFunction.Arn
        Id: "StopInstancesTarget"
        Input: !Sub '{"action": "stop", "region": "ap-southeast-2", "environment": "dev"}'
```

## Cost Optimization Recommendations

Based on the analysis, you'll be able to:

1. Identify which environments would benefit most from scheduling
2. See the distribution of instance families to help with:
   - Reserved Instance planning
   - Savings Plans optimization
   - Instance family consolidation (standardizing on fewer families)

The savings percentage is calculated based on the actual runtime reduction:
- With scheduling: 15 hours/day × 5 days = 75 hours/week
- Without scheduling: 24 hours/day × 7 days = 168 hours/week
- Potential savings: ~55.36% of compute costs

Would you like me to enhance any particular aspect of this solution or add additional features?​​​​​​​​​​​​​​​​