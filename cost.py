# AWS Cost Analysis Solution

I'll create a Python solution to analyze your AWS resources and costs, with a focus on calculating potential savings by scheduling resources to run only during business hours (8 AM to 11 PM, Monday-Friday).

Let's start with a script that will:
1. Identify all EC2 instances, EKS nodes, and RDS databases across your environments
2. Analyze costs using the Cost Explorer API
3. Calculate potential savings from implementing scheduling

Here's how we can approach this:

```python
import boto3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

def get_account_id():
    """Get AWS account ID"""
    sts_client = boto3.client('sts')
    return sts_client.get_caller_identity()['Account']

def get_regions():
    """Get list of all AWS regions"""
    ec2_client = boto3.client('ec2')
    regions = [region['RegionName'] for region in ec2_client.describe_regions()['Regions']]
    return regions

def get_ec2_instances(regions):
    """Get all EC2 instances across all regions"""
    instances = []
    
    for region in regions:
        ec2_client = boto3.client('ec2', region_name=region)
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

def get_eks_nodes(regions):
    """Get all EKS nodes across all regions"""
    nodes = []
    
    for region in regions:
        eks_client = boto3.client('eks', region_name=region)
        ec2_client = boto3.client('ec2', region_name=region)
        
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
                    instance_ids = []
                    
                    # Use EC2 describe_instances with filters to find nodes
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

def get_rds_instances(regions):
    """Get all RDS instances across all regions"""
    rds_instances = []
    
    for region in regions:
        rds_client = boto3.client('rds', region_name=region)
        
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

def get_cost_data(account_id, start_date, end_date):
    """Get cost data from AWS Cost Explorer"""
    ce_client = boto3.client('ce')
    
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
        ]
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

def main():
    # Get account ID
    account_id = get_account_id()
    print(f"AWS Account ID: {account_id}")
    
    # Get all regions
    regions = get_regions()
    
    # Get resources
    ec2_instances = get_ec2_instances(regions)
    eks_nodes = get_eks_nodes(regions)
    rds_instances = get_rds_instances(regions)
    
    all_resources = ec2_instances + eks_nodes + rds_instances
    
    # Convert to DataFrame for analysis
    df = pd.DataFrame(all_resources)
    
    # Print resource counts
    print("\nResource Counts by Environment:")
    env_counts = df.groupby(['Environment', 'ResourceType']).size().unstack(fill_value=0)
    print(env_counts)
    
    # Instance type distribution
    print("\nInstance Type Distribution:")
    type_dist = df.groupby(['ResourceType', 'Type']).size().unstack(fill_value=0)
    print(type_dist)
    
    # Get cost data for the last month
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    cost_data = get_cost_data(
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

if __name__ == "__main__":
    main()
```

## Approach and Features

This solution provides:

1. **Resource Inventory**:
   - Comprehensive list of all EC2 instances, EKS nodes, and RDS databases
   - Filtered by the "asx_environment" tag

2. **Cost Analysis**:
   - Uses AWS Cost Explorer API to get cost data per service and environment
   - Maps resources to their respective AWS service categories

3. **Scheduling Savings Calculation**:
   - Calculates potential savings from running instances only during business hours
   - Assumes 15 hours per day, 5 days per week (75 hours total) vs. 168 hours for 24/7 operation
   - Estimates approximately 55.36% savings for EC2 and EKS resources

4. **Visualizations**:
   - Resource count by environment and type
   - Current cost vs. potential savings by environment

## Security and Best Practices

In line with your preferences, this solution follows AWS security best practices:

1. Uses IAM roles/credentials with least privilege (assumes proper role configuration)
2. Doesn't hardcode any credentials
3. Handles errors gracefully
4. Uses pagination for API calls that might return large result sets

## Implementation Options and Cost Considerations

For a more complete solution, you might consider these options:

1. **Scheduling Implementation**:
   - Use AWS Instance Scheduler (lower effort, but has additional costs)
   - Create custom Lambda functions with CloudWatch Events (more effort, but lower cost)
   - Use AWS Auto Scaling scheduled actions for EKS node groups

2. **Additional Cost Saving Strategies**:
   - Rightsizing recommendations based on CloudWatch metrics
   - Reserved Instance and Savings Plan analysis
   - Identify idle resources for possible termination

Would you like me to expand on any particular aspect of this solution or provide additional analysis options?​​​​​​​​​​​​​​​​