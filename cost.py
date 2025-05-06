I'll help you analyze your AWS account costs and calculate potential savings by scheduling instances to run only during business hours. Let's create a Python script that will:

1. Connect to AWS and gather information about your EC2 instances, EKS nodes, and RDS databases
2. Analyze resources by environment using the asx_environment tag
3. Calculate current costs
4. Estimate savings from scheduling resources to run only Monday-Friday, 8 AM to 11 PM

Let's start by creating a script to gather and analyze this data:

```python
import boto3
import json
import datetime
from datetime import date, timedelta
import pandas as pd
from collections import defaultdict

# Initialize AWS clients
ec2 = boto3.client('ec2')
rds = boto3.client('rds')
eks = boto3.client('eks')
ce = boto3.client('ce')  # Cost Explorer client

# Get account ID
sts = boto3.client('sts')
account_id = sts.get_caller_identity()['Account']
print(f"AWS Account ID: {account_id}")

# Function to get all EC2 instances
def get_ec2_instances():
    instances = []
    paginator = ec2.get_paginator('describe_instances')
    for page in paginator.paginate():
        for reservation in page['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'running':
                    # Get environment tag if it exists
                    env = "unknown"
                    if 'Tags' in instance:
                        for tag in instance['Tags']:
                            if tag['Key'] == 'asx_environment':
                                env = tag['Value']
                    
                    instances.append({
                        'InstanceId': instance['InstanceId'],
                        'InstanceType': instance['InstanceType'],
                        'Environment': env,
                        'Service': 'EC2'
                    })
    return instances

# Function to get all RDS instances
def get_rds_instances():
    instances = []
    paginator = rds.get_paginator('describe_db_instances')
    for page in paginator.paginate():
        for instance in page['DBInstances']:
            # Get environment tag if it exists
            env = "unknown"
            if 'TagList' in instance:
                for tag in instance['TagList']:
                    if tag['Key'] == 'asx_environment':
                        env = tag['Value']
            
            instances.append({
                'InstanceId': instance['DBInstanceIdentifier'],
                'InstanceType': instance['DBInstanceClass'],
                'Environment': env,
                'Service': 'RDS'
            })
    return instances

# Function to get all EKS nodes (via EC2 instances with EKS tags)
def get_eks_nodes():
    nodes = []
    
    # First get all EKS clusters
    clusters = []
    try:
        response = eks.list_clusters()
        clusters = response['clusters']
    except Exception as e:
        print(f"Error listing EKS clusters: {e}")
        
    # For each cluster, find node groups and their instance types
    for cluster_name in clusters:
        try:
            # Get node groups for this cluster
            response = eks.list_nodegroups(clusterName=cluster_name)
            nodegroups = response['nodegroups']
            
            for nodegroup_name in nodegroups:
                # Get details about this node group
                ng_details = eks.describe_nodegroup(
                    clusterName=cluster_name,
                    nodegroupName=nodegroup_name
                )
                
                # Get instance type and environment tag
                instance_type = ng_details['nodegroup'].get('instanceTypes', ['unknown'])[0]
                
                env = "unknown"
                if 'tags' in ng_details['nodegroup']:
                    env = ng_details['nodegroup']['tags'].get('asx_environment', 'unknown')
                    
                # Get scaling details
                desired_size = ng_details['nodegroup'].get('scalingConfig', {}).get('desiredSize', 0)
                
                # Add each node as a separate entry
                for i in range(desired_size):
                    nodes.append({
                        'InstanceId': f"{cluster_name}-{nodegroup_name}-node-{i}",
                        'InstanceType': instance_type,
                        'Environment': env,
                        'Service': 'EKS'
                    })
        except Exception as e:
            print(f"Error processing EKS cluster {cluster_name}: {e}")
    
    return nodes

# Function to get cost data from Cost Explorer
def get_cost_data():
    # Calculate date range - last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # Format dates for Cost Explorer
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Get cost by service and instance type
    response = ce.get_cost_and_usage(
        TimePeriod={
            'Start': start_date_str,
            'End': end_date_str
        },
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': 'SERVICE'},
            {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}
        ]
    )
    
    # Process results
    cost_data = {}
    
    for result in response['ResultsByTime']:
        for group in result['Groups']:
            service = group['Keys'][0]
            instance_type = group['Keys'][1]
            
            # Filter to only EC2, RDS, and EKS services
            if any(s in service.lower() for s in ['ec2', 'rds', 'eks']):
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                
                if service not in cost_data:
                    cost_data[service] = {}
                
                cost_data[service][instance_type] = cost
    
    return cost_data

# Main function to process and analyze data
def analyze_resources():
    # Get instances data
    ec2_instances = get_ec2_instances()
    rds_instances = get_rds_instances()
    eks_nodes = get_eks_nodes()
    
    # Combine all resources
    all_resources = ec2_instances + rds_instances + eks_nodes
    
    # Get cost data
    cost_data = get_cost_data()
    
    # Organize data by environment and instance type
    env_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    for resource in all_resources:
        env = resource['Environment']
        instance_type = resource['InstanceType']
        service = resource['Service']
        
        # Count instance by environment, service, and instance type
        env_data[env][service][instance_type] += 1
    
    # Calculate current costs and potential savings
    total_current_cost = 0
    total_savings = 0
    
    # Calculate business hours vs total hours in a month
    business_hours_per_day = 15  # 8 AM to 11 PM
    business_days_per_week = 5   # Monday to Friday
    
    # Average days in a month
    avg_days_per_month = 30.44
    avg_business_days_per_month = (avg_days_per_month / 7) * business_days_per_week
    
    # Total hours in a month
    total_hours_per_month = 24 * avg_days_per_month
    
    # Business hours in a month
    business_hours_per_month = business_hours_per_day * avg_business_days_per_month
    
    # Percentage of time resources would be running with scheduling
    running_percentage = business_hours_per_month / total_hours_per_month
    
    # Detailed results data structure
    results = {
        'account_id': account_id,
        'environments': {},
        'summary': {
            'total_current_monthly_cost': 0,
            'estimated_monthly_savings': 0,
            'total_instances': sum(len(inst) for inst in [ec2_instances, rds_instances, eks_nodes])
        }
    }
    
    # Process each environment
    for env, services in env_data.items():
        env_cost = 0
        env_instance_count = 0
        
        # Initialize environment in results
        results['environments'][env] = {
            'services': {},
            'total_instances': 0,
            'current_monthly_cost': 0,
            'estimated_monthly_savings': 0
        }
        
        # Process each service in the environment
        for service, instance_types in services.items():
            service_cost = 0
            service_instance_count = 0
            
            # Initialize service in results
            results['environments'][env]['services'][service] = {
                'instance_types': {},
                'total_instances': 0,
                'current_monthly_cost': 0,
                'estimated_monthly_savings': 0
            }
            
            # Process each instance type in the service
            for instance_type, count in instance_types.items():
                # Match the AWS service name with our internal service name
                aws_service = None
                if service == 'EC2':
                    aws_service = 'Amazon Elastic Compute Cloud - Compute'
                elif service == 'RDS':
                    aws_service = 'Amazon Relational Database Service'
                elif service == 'EKS':
                    aws_service = 'Amazon Elastic Container Service for Kubernetes'
                
                # Skip if we can't match the service
                if aws_service is None or aws_service not in cost_data:
                    continue
                
                # Get cost for this instance type
                instance_cost = 0
                if instance_type in cost_data[aws_service]:
                    # If we have exact instance type cost
                    instance_cost = cost_data[aws_service][instance_type]
                else:
                    # If we don't have an exact match, estimate based on average cost per instance
                    total_service_cost = sum(cost_data[aws_service].values())
                    service_instance_count_in_cost = sum(env_data[e][service].values() 
                                                        for e in env_data.keys())
                    
                    if service_instance_count_in_cost > 0:
                        avg_cost_per_instance = total_service_cost / service_instance_count_in_cost
                        instance_cost = avg_cost_per_instance * count
                
                # Calculate cost for this instance type
                type_total_cost = instance_cost
                type_savings = type_total_cost * (1 - running_percentage)
                
                # Update counters
                service_cost += type_total_cost
                service_instance_count += count
                
                # Add instance type details to results
                results['environments'][env]['services'][service]['instance_types'][instance_type] = {
                    'count': count,
                    'current_monthly_cost': round(type_total_cost, 2),
                    'estimated_monthly_savings': round(type_savings, 2)
                }
            
            # Update service totals
            results['environments'][env]['services'][service]['total_instances'] = service_instance_count
            results['environments'][env]['services'][service]['current_monthly_cost'] = round(service_cost, 2)
            results['environments'][env]['services'][service]['estimated_monthly_savings'] = round(service_cost * (1 - running_percentage), 2)
            
            # Update environment counters
            env_cost += service_cost
            env_instance_count += service_instance_count
        
        # Update environment totals
        results['environments'][env]['total_instances'] = env_instance_count
        results['environments'][env]['current_monthly_cost'] = round(env_cost, 2)
        results['environments'][env]['estimated_monthly_savings'] = round(env_cost * (1 - running_percentage), 2)
        
        # Update global totals
        total_current_cost += env_cost
        total_savings += env_cost * (1 - running_percentage)
    
    # Update summary
    results['summary']['total_current_monthly_cost'] = round(total_current_cost, 2)
    results['summary']['estimated_monthly_savings'] = round(total_savings, 2)
    results['summary']['running_percentage'] = round(running_percentage * 100, 2)
    
    return results

# Run the analysis
def main():
    print("Starting AWS resource analysis...")
    results = analyze_resources()
    
    # Print summary to console
    print("\n--- SUMMARY ---")
    print(f"AWS Account ID: {results['account_id']}")
    print(f"Total Instances: {results['summary']['total_instances']}")
    print(f"Current Monthly Cost: ${results['summary']['total_current_monthly_cost']:.2f}")
    print(f"Estimated Monthly Savings: ${results['summary']['estimated_monthly_savings']:.2f}")
    print(f"Percentage of time resources would run with scheduling: {results['summary']['running_percentage']}%")
    
    # Print detailed breakdown
    print("\n--- DETAILED BREAKDOWN BY ENVIRONMENT ---")
    for env, env_data in results['environments'].items():
        print(f"\nEnvironment: {env}")
        print(f"  Total Instances: {env_data['total_instances']}")
        print(f"  Current Monthly Cost: ${env_data['current_monthly_cost']:.2f}")
        print(f"  Estimated Monthly Savings: ${env_data['estimated_monthly_savings']:.2f}")
        
        print("  --- Services ---")
        for service, service_data in env_data['services'].items():
            print(f"    {service}:")
            print(f"      Total Instances: {service_data['total_instances']}")
            print(f"      Current Monthly Cost: ${service_data['current_monthly_cost']:.2f}")
            print(f"      Estimated Monthly Savings: ${service_data['estimated_monthly_savings']:.2f}")
            
            print("      --- Instance Types ---")
            for inst_type, type_data in service_data['instance_types'].items():
                print(f"        {inst_type}: {type_data['count']} instances, "
                      f"Cost: ${type_data['current_monthly_cost']:.2f}, "
                      f"Potential Savings: ${type_data['estimated_monthly_savings']:.2f}")
    
    # Save results to JSON file
    with open('aws_cost_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nAnalysis complete. Results saved to aws_cost_analysis.json")

if __name__ == "__main__":
    main()
```

Would you like me to explain how this script works?​​​​​​​​​​​​​​​​
