# AWS Cost Analysis - Focus on Environment Expenses

Let's focus on finding the expenses per environment first. Here's a streamlined Python script that uses the specified profile and focuses only on the Sydney region for now:

```python
import boto3
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict

# Define the regions and profile
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
                # Get node groups
                node_groups = eks_client.list_nodegroups(clusterName=cluster_name)['nodegroups']
                
                for ng_name in node_groups:
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
    
    # Get costs by service and environment tag
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

def get_cost_by_instance_type(session, account_id, start_date, end_date):
    """Get cost data by instance type from AWS Cost Explorer"""
    ce_client = session.client('ce')
    
    # Get costs by instance type
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
                'Key': 'INSTANCE_TYPE'
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
            instance_type = group['Keys'][0]
            environment = group['Keys'][1].replace('asx_environment$', '') if '$' in group['Keys'][1] else 'untagged'
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            unit = group['Metrics']['UnblendedCost']['Unit']
            
            cost_data.append({
                'InstanceType': instance_type,
                'Environment': environment,
                'Amount': amount,
                'Unit': unit,
                'Period': result['TimePeriod']['Start']
            })
    
    return cost_data

def calculate_savings_potential(all_resources, cost_data):
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

def main():
    # Create boto3 session with the specified profile
    print("Creating AWS session with profile: profile_n")
    session = create_session()
    
    # Get account ID
    account_id = get_account_id(session)
    print(f"AWS Account ID: {account_id}")
    
    # Get resources
    print("\nFetching EC2 instances...")
    ec2_instances = get_ec2_instances(session)
    print(f"Found {len(ec2_instances)} EC2 instances")
    
    print("\nFetching EKS nodes...")
    eks_nodes = get_eks_nodes(session)
    print(f"Found {len(eks_nodes)} EKS nodes")
    
    print("\nFetching RDS instances...")
    rds_instances = get_rds_instances(session)
    print(f"Found {len(rds_instances)} RDS instances")
    
    all_resources = ec2_instances + eks_nodes + rds_instances
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(all_resources)
    
    # Print resource counts
    print("\nResource Counts by Environment:")
    if not df.empty:
        env_counts = df.groupby(['Environment', 'ResourceType']).size().unstack(fill_value=0)
        print(env_counts)
    else:
        print("No resources found")
    
    # Instance type distribution
    print("\nInstance Type Distribution:")
    if not df.empty:
        type_dist = df.groupby(['ResourceType', 'Type']).size().reset_index(name='Count')
        print(type_dist)
    else:
        print("No resources found")
    
    # Get cost data for the last month
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print(f"\nFetching cost data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")
    
    cost_data = get_cost_data(
        session,
        account_id,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    # Print cost data by service and environment
    print("\nCost Data by Service and Environment:")
    cost_df = pd.DataFrame(cost_data)
    
    if not cost_df.empty:
        service_env_cost = cost_df.pivot_table(
            index='Environment', 
            columns='Service', 
            values='Amount', 
            aggfunc='sum',
            fill_value=0
        )
        print(service_env_cost)
        
        # Print total cost by environment
        print("\nTotal Cost by Environment:")
        total_by_env = cost_df.groupby('Environment')['Amount'].sum().reset_index()
        for _, row in total_by_env.iterrows():
            print(f"  {row['Environment']}: ${row['Amount']:.2f}")
    else:
        print("No cost data found")
    
    # Get cost data by instance type
    print("\nFetching cost data by instance type...")
    instance_cost_data = get_cost_by_instance_type(
        session,
        account_id,
        start_date.strftime('%Y-%m-%d'),
        end_date.strftime('%Y-%m-%d')
    )
    
    # Print cost data by instance type and environment
    print("\nCost Data by Instance Type and Environment:")
    instance_cost_df = pd.DataFrame(instance_cost_data)
    
    if not instance_cost_df.empty:
        instance_env_cost = instance_cost_df.pivot_table(
            index='Environment', 
            columns='InstanceType', 
            values='Amount', 
            aggfunc='sum',
            fill_value=0
        )
        print(instance_env_cost)
    else:
        print("No instance type cost data found")
    
    # Calculate potential savings
    print("\nCalculating potential savings...")
    savings = calculate_savings_potential(all_resources, cost_data)
    
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

if __name__ == "__main__":
    main()
```

## Script Overview

This script focuses solely on analyzing your AWS resources and costs by environment, without implementing a scheduler or visualizations. Here's what it does:

1. **Resource Inventory**:
   - Lists all EC2 instances, EKS nodes, and RDS instances in Sydney (ap-southeast-2) region
   - Groups them by environment using the "asx_environment" tag

2. **Cost Analysis**:
   - Uses the AWS Cost Explorer API to get cost data for the last 30 days
   - Provides cost breakdown by:
     - Service and environment
     - Instance type and environment
   - Calculates total cost by environment

3. **Savings Calculation**:
   - Estimates potential savings from implementing an 8 AM to 11 PM weekday schedule
   - Shows savings by environment and total potential savings

## Running the Script

To run this script, you need:
1. The AWS profile "profile_n" configured with appropriate permissions
2. Python with boto3 and pandas libraries installed

```bash
# Install required packages
pip install boto3 pandas

# Run the script
python aws_cost_analysis.py
```

The script will output results to the console, showing you a detailed breakdown of resources and costs per environment, helping you understand where potential savings can be achieved.

Would you like me to refine any specific part of this analysis or add any particular features?​​​​​​​​​​​​​​​​