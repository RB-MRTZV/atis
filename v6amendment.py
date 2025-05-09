# Function to generate an environment summary CSV file
def generate_environment_summary_csv(results):
    # Create CSV file with AWS account number in the filename
    account_id = results['metadata']['account_id']
    csv_filename = f"{account_id}-Environment-summary.csv"
    
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = [
            'Environment',
            'Total Instances',
            'EKS Node Count',
            'EKS Monthly Cost',
            'EC2 Instance Count',
            'EC2 Monthly Cost',
            'RDS Instance Count',
            'RDS Monthly Cost',
            'Total Cost',
            'Estimated Monthly Saving'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        # Add rows for each environment
        for env in results["environments"]:
            # Initialize counters for each service
            eks_count = 0
            eks_cost = 0
            ec2_count = 0
            ec2_cost = 0
            rds_count = 0
            rds_cost = 0
            
            # Calculate service-specific counts and costs
            for service_data in env["service_breakdown"]:
                if service_data['service'] == 'EKS Node':
                    eks_count = service_data['count']
                    eks_cost = service_data['cost']
                elif service_data['service'] == 'EC2':
                    ec2_count = service_data['count']
                    ec2_cost = service_data['cost']
                elif service_data['service'] == 'RDS':
                    rds_count = service_data['count']
                    rds_cost = service_data['cost']
            
            writer.writerow({
                'Environment': env['name'],
                'Total Instances': env['instance_count'],
                'EKS Node Count': eks_count,
                'EKS Monthly Cost': f"${eks_cost:.2f}",
                'EC2 Instance Count': ec2_count,
                'EC2 Monthly Cost': f"${ec2_cost:.2f}",
                'RDS Instance Count': rds_count,
                'RDS Monthly Cost': f"${rds_cost:.2f}",
                'Total Cost': f"${env['current_monthly_cost']:.2f}",
                'Estimated Monthly Saving': f"${env['estimated_monthly_savings']:.2f}"
            })
    
    print(f"\nEnvironment summary CSV generated: {csv_filename}")

# Update the existing CSV generation function to include account ID in filenames
def generate_csv_table(results):
    # Get account ID
    account_id = results['metadata']['account_id']
    
    # Create CSV file with account ID in the filename
    csv_filename = f"{account_id}-aws_instance_analysis.csv"
    
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = [
            'Environment',
            'Service',
            'Instance Type',
            'Count',
            'Cost/Instance',
            'Monthly Cost',
            'Savings'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        # Add rows for each instance count entry
        for item in results["instance_counts"]:
            writer.writerow({
                'Environment': item['environment'],
                'Service': item['service'],
                'Instance Type': item['instance_type'],
                'Count': item['count'],
                'Cost/Instance': f"${item['cost_per_instance']:.2f}",
                'Monthly Cost': f"${item['current_monthly_cost']:.2f}",
                'Savings': f"${item['estimated_monthly_savings']:.2f}"
            })
    
    print(f"\nCSV table generated: {csv_filename}")
    
    # Also generate separate CSVs for each environment
    generate_env_csv_files(results)
    
    # Generate the environment summary CSV
    generate_environment_summary_csv(results)

# Update the per-environment CSV files to include account ID
def generate_env_csv_files(results):
    # Get account ID
    account_id = results['metadata']['account_id']
    
    # Create output directory if it doesn't exist
    csv_dir = 'aws_cost_analysis'
    if not os.path.exists(csv_dir):
        os.makedirs(csv_dir)
    
    # Generate a CSV file for each environment
    for env_data in results["environments"]:
        env_name = env_data["name"]
        csv_filename = f"{csv_dir}/{account_id}-{env_name}_cost_analysis.csv"
        
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = [
                'Service', 
                'Instance Type', 
                'Cost/Instance', 
                'Count', 
                'Monthly Cost', 
                'Savings'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            # Add rows for each service and instance type
            for service in env_data["services"]:
                for instance_type in service["instance_types"]:
                    writer.writerow({
                        'Service': service["name"],
                        'Instance Type': instance_type["type"],
                        'Cost/Instance': f"${instance_type['cost_per_instance']:.2f}",
                        'Count': instance_type["count"],
                        'Monthly Cost': f"${instance_type['current_monthly_cost']:.2f}",
                        'Savings': f"${instance_type['estimated_monthly_savings']:.2f}"
                    })
    
    print(f"Environment-specific CSV files generated in the '{csv_dir}' directory")
