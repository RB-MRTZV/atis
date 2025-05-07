I'll help you list all EC2 and RDS instance types in your current region and find their on-demand hourly rates using AWS APIs. Let me create a Python script that does this for you.

```python
import boto3
import json
from prettytable import PrettyTable

def list_instances_with_prices():
    """List all EC2 and RDS instances in the current region with their on-demand hourly prices."""
    # Initialize AWS clients
    ec2_client = boto3.client('ec2')
    rds_client = boto3.client('rds')
    pricing_client = boto3.client('pricing', region_name='us-east-1')  # Pricing API is only available in us-east-1
    
    # Get current region
    session = boto3.session.Session()
    current_region = session.region_name
    print(f"Checking instances in region: {current_region}")
    
    # Get all EC2 instances
    ec2_response = ec2_client.describe_instances()
    ec2_instances = []
    
    for reservation in ec2_response['Reservations']:
        for instance in reservation['Instances']:
            instance_type = instance['InstanceType']
            instance_id = instance['InstanceId']
            
            # Get instance name from tags if available
            instance_name = ''
            if 'Tags' in instance:
                for tag in instance['Tags']:
                    if tag['Key'] == 'Name':
                        instance_name = tag['Value']
                        break
            
            ec2_instances.append({
                'id': instance_id,
                'name': instance_name,
                'type': instance_type,
                'service': 'EC2'
            })
    
    # Get all RDS instances
    rds_response = rds_client.describe_db_instances()
    rds_instances = []
    
    for instance in rds_response['DBInstances']:
        instance_id = instance['DBInstanceIdentifier']
        instance_type = instance['DBInstanceClass']
        
        rds_instances.append({
            'id': instance_id,
            'name': instance_id,
            'type': instance_type,
            'service': 'RDS'
        })
    
    # Combine both instance lists
    all_instances = ec2_instances + rds_instances
    
    # Create a table to display results
    table = PrettyTable()
    table.field_names = ["Service", "Instance ID", "Name", "Type", "Hourly Rate (USD)"]
    
    # Dictionary to track instance types we've already looked up to avoid duplicate API calls
    price_cache = {}
    
    # Get pricing for each instance type
    for instance in all_instances:
        instance_type = instance['type']
        service = instance['service']
        
        # Create a cache key
        cache_key = f"{service}:{instance_type}:{current_region}"
        
        # Check if we've already looked up this instance type
        if cache_key not in price_cache:
            try:
                if service == 'EC2':
                    # EC2 pricing filter
                    filters = [
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': get_region_name(current_region)},
                        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                        {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                        {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
                    ]
                    
                    response = pricing_client.get_products(
                        ServiceCode='AmazonEC2',
                        Filters=filters,
                        MaxResults=1
                    )
                    
                else:  # RDS
                    # RDS pricing filter
                    filters = [
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': get_region_name(current_region)},
                        {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'},
                        {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': 'MySQL'}  # Assume MySQL by default
                    ]
                    
                    response = pricing_client.get_products(
                        ServiceCode='AmazonRDS',
                        Filters=filters,
                        MaxResults=1
                    )
                
                if response['PriceList']:
                    price_list = json.loads(response['PriceList'][0])
                    terms = price_list.get('terms', {}).get('OnDemand', {})
                    
                    # Get first price dimension
                    dimensions = list(list(terms.values())[0]['priceDimensions'].values())[0]
                    price = dimensions['pricePerUnit']['USD']
                    price_cache[cache_key] = price
                else:
                    price_cache[cache_key] = "Price not found"
                    
            except Exception as e:
                print(f"Error getting price for {instance_type}: {str(e)}")
                price_cache[cache_key] = "Error retrieving price"
        
        # Add instance to the table
        table.add_row([
            instance['service'],
            instance['id'],
            instance['name'],
            instance['type'],
            price_cache.get(cache_key, "Unknown")
        ])
    
    print(table)
    
    # Also return the raw data
    return {"instances": all_instances, "prices": price_cache}

def get_region_name(region_code):
    """Map region code to region name as used in the pricing API."""
    region_names = {
        'us-east-1': 'US East (N. Virginia)',
        'us-east-2': 'US East (Ohio)',
        'us-west-1': 'US West (N. California)',
        'us-west-2': 'US West (Oregon)',
        'ap-east-1': 'Asia Pacific (Hong Kong)',
        'ap-south-1': 'Asia Pacific (Mumbai)',
        'ap-northeast-1': 'Asia Pacific (Tokyo)',
        'ap-northeast-2': 'Asia Pacific (Seoul)',
        'ap-northeast-3': 'Asia Pacific (Osaka)',
        'ap-southeast-1': 'Asia Pacific (Singapore)',
        'ap-southeast-2': 'Asia Pacific (Sydney)',
        'ca-central-1': 'Canada (Central)',
        'eu-central-1': 'EU (Frankfurt)',
        'eu-west-1': 'EU (Ireland)',
        'eu-west-2': 'EU (London)',
        'eu-west-3': 'EU (Paris)',
        'eu-north-1': 'EU (Stockholm)',
        'eu-south-1': 'EU (Milan)',
        'me-south-1': 'Middle East (Bahrain)',
        'sa-east-1': 'South America (Sao Paulo)'
    }
    return region_names.get(region_code, '')

if __name__ == "__main__":
    list_instances_with_prices()
```

Would you like me to explain or break down this code?​​​​​​​​​​​​​​​​