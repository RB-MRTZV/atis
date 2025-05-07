I'll modify the script to store the results in a more structured JSON format that will be easier to use for generating tables later. Here's the updated code with improved JSON output formatting:

```python
import boto3
import json
import datetime
from datetime import date, timedelta
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
                    tags = ng_details['nodegroup']['tags']
                    for key, value in tags.items():
                        if key.lower() == 'asx_environment':
                            env = value
                    
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
        },
        'Amazon Elastic Container Service for Kubernetes': {
            't3.medium': 30.24,
            'm5.large': 62.64,
            'c5.xlarge': 124.32
        }
    }
    
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
    
    # Organize data by environment, service, and instance type
    env_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    
    for resource in all_resources:
        env = resource['Environment']
        instance_type = resource['InstanceType']
        service = resource['Service']
        
        # Count instance by environment, service, and instance type
        env_data[env][service][instance_type] += 1
    
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
    
    # Create a more table-friendly JSON structure
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
        "environment_summary": [],
        "service_summary": [],
        "instance_type_summary": [],
        "detailed_data": []
    }
    
    # Summary dictionaries to accumulate data
    env_summary = {}
    service_summary = {}
    instance_type_summary = {}
    
    # Calculate total costs for each environment and resource type
    total_current_cost = 0
    total_savings = 0
    
    # Process each environment
    for env, services in env_data.items():
        env_cost = 0
        env_instance_count = 0
        
        # Process each service in the environment
        for service, instance_types in services.items():
            service_cost = 0
            service_instance_count = 0
            
            # Map our service names to AWS service names in cost data
            aws_service_map = {
                'EC2': 'Amazon Elastic Compute Cloud - Compute',
                'RDS': 'Amazon Relational Database Service',
                'EKS': 'Amazon Elastic Container Service for Kubernetes'
            }
            
            aws_service = aws_service_map.get(service)
            
            # Process each instance type in the service
            for instance_type, count in instance_types.items():
                # Skip if we can't match the service
                if aws_service is None or aws_service not in cost_data:
                    continue
                
                # Get cost for this instance type
                instance_cost = 0
                if instance_type in cost_data[aws_service]:
                    # If we have exact instance type cost
                    instance_cost = cost_data[aws_service][instance_type]
                else:
                    # If we don't have an exact match, use a default value or estimate
                    # For demonstration, we'll use a generic cost
                    instance_cost = 100.00  # Default cost
                
                # Calculate total cost for all instances of this type
                type_total_cost = instance_cost * count
                type_savings = type_total_cost * non_running_percentage
                
                # Update counters
                service_cost += type_total_cost
                service_instance_count += count
                
                # Add to instance type summary
                instance_key = f"{service}:{instance_type}"
                if instance_key not in instance_type_summary:
                    instance_type_summary[instance_key] = {
                        "service": service,
                        "instance_type": instance_type,
                        "count": 0,
                        "current_monthly_cost": 0,
                        "estimated_monthly_savings": 0,
                        "environments": {}
                    }
                
                instance_type_summary[instance_key]["count"] += count
                instance_type_summary[instance_key]["current_monthly_cost"] += type_total_cost
                instance_type_summary[instance_key]["estimated_monthly_savings"] += type_savings
                
                if env not in instance_type_summary[instance_key]["environments"]:
                    instance_type_summary[instance_key]["environments"][env] = {
                        "count": 0,
                        "current_monthly_cost": 0,
                        "estimated_monthly_savings": 0
                    }
                
                instance_type_summary[instance_key]["environments"][env]["count"] += count
                instance_type_summary[instance_key]["environments"][env]["current_monthly_cost"] += type_total_cost
                instance_type_summary[instance_key]["environments"][env]["estimated_monthly_savings"] += type_savings
                
                # Add to detailed data
                results["detailed_data"].append({
                    "environment": env,
                    "service": service,
                    "instance_type": instance_type,
                    "count": count,
                    "cost_per_instance": round(instance_cost, 2),
                    "current_monthly_cost": round(type_total_cost, 2),
                    "estimated_monthly_savings": round(type_savings, 2)
                })
            
            # Add to service summary
            if service not in service_summary:
                service_summary[service] = {
                    "service": service,
                    "count": 0,
                    "current_monthly_cost": 0,
                    "estimated_monthly_savings": 0,
                    "environments": {}
                }
            
            service_summary[service]["count"] += service_instance_count
            service_summary[service]["current_monthly_cost"] += service_cost
            service_summary[service]["estimated_monthly_savings"] += service_cost * non_running_percentage
            
            if env not in service_summary[service]["environments"]:
                service_summary[service]["environments"][env] = {
                    "count": 0,
                    "current_monthly_cost": 0,
                    "estimated_monthly_savings": 0
                }
            
            service_summary[service]["environments"][env]["count"] += service_instance_count
            service_summary[service]["environments"][env]["current_monthly_cost"] += service_cost
            service_summary[service]["environments"][env]["estimated_monthly_savings"] += service_cost * non_running_percentage
            
            # Update environment counters
            env_cost += service_cost
            env_instance_count += service_instance_count
        
        # Add to environment summary
        if env not in env_summary:
            env_summary[env] = {
                "environment": env,
                "count": 0,
                "current_monthly_cost": 0,
                "estimated_monthly_savings": 0,
                "services": {}
            }
        
        env_summary[env]["count"] += env_instance_count
        env_summary[env]["current_monthly_cost"] += env_cost
        env_summary[env]["estimated_monthly_savings"] += env_cost * non_running_percentage
        
        # Update global totals
        total_current_cost += env_cost
        total_savings += env_cost * non_running_percentage
    
    # Update summary
    results["summary"]["total_current_monthly_cost"] = round(total_current_cost, 2)
    results["summary"]["total_estimated_monthly_savings"] = round(total_savings, 2)
    
    # Convert summary dictionaries to lists for better table generation
    for env, data in env_summary.items():
        results["environment_summary"].append({
            "environment": env,
            "count": data["count"],
            "current_monthly_cost": round(data["current_monthly_cost"], 2),
            "estimated_monthly_savings": round(data["estimated_monthly_savings"], 2),
            "percentage_of_total_cost": round((data["current_monthly_cost"] / total_current_cost * 100) if total_current_cost > 0 else 0, 2)
        })
    
    for service, data in service_summary.items():
        results["service_summary"].append({
            "service": service,
            "count": data["count"],
            "current_monthly_cost": round(data["current_monthly_cost"], 2),
            "estimated_monthly_savings": round(data["estimated_monthly_savings"], 2),
            "percentage_of_total_cost": round((data["current_monthly_cost"] / total_current_cost * 100) if total_current_cost > 0 else 0, 2)
        })
    
    for instance_key, data in instance_type_summary.items():
        results["instance_type_summary"].append({
            "service": data["service"],
            "instance_type": data["instance_type"],
            "count": data["count"],
            "current_monthly_cost": round(data["current_monthly_cost"], 2),
            "estimated_monthly_savings": round(data["estimated_monthly_savings"], 2),
            "percentage_of_total_cost": round((data["current_monthly_cost"] / total_current_cost * 100) if total_current_cost > 0 else 0, 2)
        })
    
    # Sort summaries for better display
    results["environment_summary"].sort(key=lambda x: x["current_monthly_cost"], reverse=True)
    results["service_summary"].sort(key=lambda x: x["current_monthly_cost"], reverse=True)
    results["instance_type_summary"].sort(key=lambda x: x["current_monthly_cost"], reverse=True)
    
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
    print(f"{'Environment':<15} {'Count':<8} {'Monthly Cost':<15} {'Savings':<15} {'% of Total':<10}")
    print("-" * 65)
    for env in results["environment_summary"]:
        print(f"{env['environment']:<15} {env['count']:<8} ${env['current_monthly_cost']:<13.2f} ${env['estimated_monthly_savings']:<13.2f} {env['percentage_of_total_cost']:<10.2f}%")
    
    # Print service summary
    print("\n--- SERVICE SUMMARY ---")
    print(f"{'Service':<10} {'Count':<8} {'Monthly Cost':<15} {'Savings':<15} {'% of Total':<10}")
    print("-" * 60)
    for svc in results["service_summary"]:
        print(f"{svc['service']:<10} {svc['count']:<8} ${svc['current_monthly_cost']:<13.2f} ${svc['estimated_monthly_savings']:<13.2f} {svc['percentage_of_total_cost']:<10.2f}%")
    
    # Print top 10 instance types by cost
    print("\n--- TOP 10 INSTANCE TYPES BY COST ---")
    print(f"{'Service':<8} {'Type':<15} {'Count':<8} {'Monthly Cost':<15} {'Savings':<15} {'% of Total':<10}")
    print("-" * 75)
    for inst in results["instance_type_summary"][:10]:
        print(f"{inst['service']:<8} {inst['instance_type']:<15} {inst['count']:<8} ${inst['current_monthly_cost']:<13.2f} ${inst['estimated_monthly_savings']:<13.2f} {inst['percentage_of_total_cost']:<10.2f}%")
    
    # Save results to JSON file
    output_file = 'aws_cost_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nAnalysis complete. Results saved to {output_file}")
    
    # Save a table-friendly CSV version for each summary
    for summary_type in ["environment_summary", "service_summary", "instance_type_summary"]:
        output_csv = f'aws_cost_{summary_type}.csv'
        try:
            import csv
            with open(output_csv, 'w', newline='') as csvfile:
                if results[summary_type]:
                    fieldnames = results[summary_type][0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in results[summary_type]:
                        writer.writerow(row)
            print(f"CSV file created: {output_csv}")
        except Exception as e:
            print(f"Error creating CSV file {output_csv}: {e}")

if __name__ == "__main__":
    main()
```

This improved script:

1. Creates a more structured JSON format that will be easier to use for generating tables:
   - Separates metadata from the actual data
   - Includes summary sections for environments, services, and instance types
   - Formats all data in table-friendly arrays of objects

2. Adds percentage calculations to show each environment/service/instance type's proportion of total cost

3. Sorts results by cost (highest to lowest) to highlight the most expensive resources

4. Adds CSV export functionality for each summary, making it even easier to import the data into a spreadsheet or visualization tool

5. Formats the console output as tables for better readability

6. Rounds all monetary values to 2 decimal places for consistency

This structured JSON format will make it much easier to generate tables or visualizations from the data later, as each section is organized in a consistent array format with clearly defined fields.​​​​​​​​​​​​​​​​