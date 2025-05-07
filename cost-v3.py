I'll update the code to focus on analyzing the number of each instance and instance type per environment, while removing EKS to avoid duplication with EC2 instances. Here's the improved script:

```python
import boto3
import json
import datetime
from datetime import date, timedelta
from collections import defaultdict

# Initialize AWS clients
ec2 = boto3.client('ec2')
rds = boto3.client('rds')
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
                            if tag['Key'].lower() == 'asx_environment':
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
                    if tag['Key'].lower() == 'asx_environment':
                        env = tag['Value']
            
            instances.append({
                'InstanceId': instance['DBInstanceIdentifier'],
                'InstanceType': instance['DBInstanceClass'],
                'Environment': env,
                'Service': 'RDS'
            })
    return instances

# Mock function for cost data - replace with real implementation if you have cost explorer access
def get_cost_data():
    # For demonstration, let's create sample cost data based on instance types
    cost_data = {
        'Amazon Elastic Compute Cloud - Compute': {
            't2.micro': 8.352,
            't3.micro': 7.488,
            'm5.large': 62.64,
            'c5.xlarge': 124.32,
            'c5.2xlarge': 248.64,
            'm5i.4xlarge': 572.40,
            'r5.2xlarge': 379.20
        },
        'Amazon Relational Database Service': {
            'db.t3.micro': 12.48,
            'db.m5.large': 164.16,
            'db.r5.large': 196.32,
            'db.m5.2xlarge': 328.32
        }
    }
    
    return cost_data

# Main function to process and analyze data
def analyze_resources():
    # Get instances data
    ec2_instances = get_ec2_instances()
    rds_instances = get_rds_instances()
    
    # Combine all resources
    all_resources = ec2_instances + rds_instances
    
    # Get cost data
    cost_data = get_cost_data()
    
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
    non_running_percentage = 1 - running_percentage
    
    print(f"Resources will run {running_percentage:.2%} of the time with scheduling")
    print(f"Potential savings: {non_running_percentage:.2%} of current costs")
    
    # Create a table-friendly JSON structure
    results = {
        "metadata": {
            "account_id": account_id,
            "analysis_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "running_percentage": round(running_percentage * 100, 2),
            "non_running_percentage": round(non_running_percentage * 100, 2)
        },
        "summary": {
            "total_instances": len(all_resources),
            "total_current_monthly_cost": 0,
            "total_estimated_monthly_savings": 0
        },
        "environments": [],
        "instance_counts": []
    }

    # Count instances by environment and instance type
    env_instance_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    env_costs = defaultdict(float)
    env_instance_totals = defaultdict(int)
    service_instance_totals = defaultdict(int)
    service_costs = defaultdict(float)
    instance_type_costs = defaultdict(float)
    
    # Process each resource to count instances and calculate costs
    for resource in all_resources:
        env = resource['Environment']
        instance_type = resource['InstanceType']
        service = resource['Service']
        
        # Count by environment, service, and instance type
        env_instance_counts[env][service][instance_type] += 1
        
        # Update totals
        env_instance_totals[env] += 1
        service_instance_totals[service] += 1
        
        # Calculate costs using our mock cost data
        # Map our service names to AWS service names in cost data
        aws_service_map = {
            'EC2': 'Amazon Elastic Compute Cloud - Compute',
            'RDS': 'Amazon Relational Database Service'
        }
        
        aws_service = aws_service_map.get(service)
        
        # Calculate cost for this instance
        if aws_service and aws_service in cost_data and instance_type in cost_data[aws_service]:
            instance_cost = cost_data[aws_service][instance_type]
        else:
            # Default cost estimate if not found
            instance_cost = 100.00
        
        # Update cost totals
        env_costs[env] += instance_cost
        service_costs[service] += instance_cost
        instance_type_costs[f"{service}:{instance_type}"] += instance_cost
    
    # Calculate total costs and savings
    total_current_cost = sum(env_costs.values())
    total_savings = total_current_cost * non_running_percentage
    
    # Update summary
    results["summary"]["total_current_monthly_cost"] = round(total_current_cost, 2)
    results["summary"]["total_estimated_monthly_savings"] = round(total_savings, 2)
    
    # Build environment details
    for env, services in env_instance_counts.items():
        env_data = {
            "name": env,
            "instance_count": env_instance_totals[env],
            "current_monthly_cost": round(env_costs[env], 2),
            "estimated_monthly_savings": round(env_costs[env] * non_running_percentage, 2),
            "percentage_of_total_cost": round((env_costs[env] / total_current_cost * 100) if total_current_cost > 0 else 0, 2),
            "services": []
        }
        
        # Add services for this environment
        for service, instance_types in services.items():
            service_cost = sum([
                cost_data.get(aws_service_map.get(service), {}).get(inst_type, 100.00) * count
                for inst_type, count in instance_types.items()
            ])
            
            service_data = {
                "name": service,
                "instance_count": sum(instance_types.values()),
                "current_monthly_cost": round(service_cost, 2),
                "estimated_monthly_savings": round(service_cost * non_running_percentage, 2),
                "instance_types": []
            }
            
            # Add instance types for this service
            for instance_type, count in instance_types.items():
                instance_cost = cost_data.get(aws_service_map.get(service), {}).get(instance_type, 100.00) * count
                
                instance_type_data = {
                    "type": instance_type,
                    "count": count,
                    "current_monthly_cost": round(instance_cost, 2),
                    "estimated_monthly_savings": round(instance_cost * non_running_percentage, 2)
                }
                
                service_data["instance_types"].append(instance_type_data)
            
            # Sort instance types by count
            service_data["instance_types"].sort(key=lambda x: x["count"], reverse=True)
            env_data["services"].append(service_data)
        
        # Sort services by instance count
        env_data["services"].sort(key=lambda x: x["instance_count"], reverse=True)
        results["environments"].append(env_data)
    
    # Sort environments by instance count
    results["environments"].sort(key=lambda x: x["instance_count"], reverse=True)
    
    # Build flat table of instance counts
    for env, services in env_instance_counts.items():
        for service, instance_types in services.items():
            for instance_type, count in instance_types.items():
                instance_cost = cost_data.get(aws_service_map.get(service), {}).get(instance_type, 100.00) * count
                
                results["instance_counts"].append({
                    "environment": env,
                    "service": service,
                    "instance_type": instance_type,
                    "count": count,
                    "current_monthly_cost": round(instance_cost, 2),
                    "estimated_monthly_savings": round(instance_cost * non_running_percentage, 2)
                })
    
    # Sort instance counts for easier table generation
    results["instance_counts"].sort(key=lambda x: (x["environment"], x["service"], -x["count"]))
    
    return results

# Run the analysis and print results
def main():
    print("Starting AWS resource analysis...")
    results = analyze_resources()
    
    # Print summary to console
    print("\n--- SUMMARY ---")
    print(f"AWS Account ID: {results['metadata']['account_id']}")
    print(f"Total Instances: {results['summary']['total_instances']}")
    print(f"Current Monthly Cost: ${results['summary']['total_current_monthly_cost']:.2f}")
    print(f"Estimated Monthly Savings: ${results['summary']['total_estimated_monthly_savings']:.2f}")
    print(f"Percentage of time resources would run with scheduling: {results['metadata']['running_percentage']}%")
    
    # Print environment summary
    print("\n--- ENVIRONMENT SUMMARY ---")
    print(f"{'Environment':<15} {'Instances':<10} {'Monthly Cost':<15} {'Savings':<15} {'% of Total':<10}")
    print("-" * 65)
    for env in results["environments"]:
        print(f"{env['name']:<15} {env['instance_count']:<10} ${env['current_monthly_cost']:<13.2f} ${env['estimated_monthly_savings']:<13.2f} {env['percentage_of_total_cost']:<10.2f}%")
    
    # Print instance count details
    print("\n--- INSTANCE COUNT DETAILS ---")
    print(f"{'Environment':<15} {'Service':<8} {'Instance Type':<15} {'Count':<8} {'Monthly Cost':<15} {'Savings':<15}")
    print("-" * 80)
    for item in results["instance_counts"]:
        print(f"{item['environment']:<15} {item['service']:<8} {item['instance_type']:<15} {item['count']:<8} ${item['current_monthly_cost']:<13.2f} ${item['estimated_monthly_savings']:<13.2f}")
    
    # Save results to JSON file in a format suitable for table generation
    output_file = 'aws_instance_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nAnalysis complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
```

This updated script:

1. Removes the EKS functionality completely to avoid duplication with EC2 instances
2. Focuses specifically on instance counts by environment, service, and instance type
3. Organizes the data in a hierarchical structure (environments → services → instance types)
4. Also provides a flat table structure in the "instance_counts" array for easier table generation
5. Maintains cost calculations and potential savings analysis
6. Sorts results by instance count to highlight the most numerous instance types
7. Saves the output in a JSON format that's optimized for generating tables
8. Prints detailed instance counts to the console for immediate visibility

The JSON output structure is specifically designed to be easily converted into tables or visual representations, with both hierarchical data (nested) and flat data (for simple table generation).​​​​​​​​​​​​​​​​