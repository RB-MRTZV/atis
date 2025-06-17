#!/usr/bin/env python3
"""
Fetch current AWS pricing data using the AWS Price List API and update cost_config.json
"""

import boto3
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class AWSPricingFetcher:
    def __init__(self, region='ap-southeast-2'):
        self.region = region
        # Price List API is only available in us-east-1 and ap-south-1
        self.pricing_client = boto3.client('pricing', region_name='us-east-1')
        self.pricing_data = {
            'currency': 'USD',
            'region': region,
            'last_updated': datetime.now().isoformat(),
            'ec2_pricing': {},
            'rds_pricing': {},
            'eks_pricing': {}
        }
    
    def fetch_ec2_pricing(self):
        """Fetch EC2 On-Demand pricing for common instance types"""
        logger.info(f"Fetching EC2 pricing for region {self.region}")
        
        # Common instance types to fetch
        instance_types = [
            't2.micro', 't2.small', 't2.medium', 't2.large', 't2.xlarge', 't2.2xlarge',
            't3.micro', 't3.small', 't3.medium', 't3.large', 't3.xlarge', 't3.2xlarge',
            't3a.micro', 't3a.small', 't3a.medium', 't3a.large', 't3a.xlarge', 't3a.2xlarge',
            'm5.large', 'm5.xlarge', 'm5.2xlarge', 'm5.4xlarge', 'm5.8xlarge', 'm5.12xlarge', 'm5.16xlarge', 'm5.24xlarge',
            'm5a.large', 'm5a.xlarge', 'm5a.2xlarge', 'm5a.4xlarge', 'm5a.8xlarge', 'm5a.12xlarge', 'm5a.16xlarge', 'm5a.24xlarge',
            'm6i.large', 'm6i.xlarge', 'm6i.2xlarge', 'm6i.4xlarge', 'm6i.8xlarge', 'm6i.12xlarge', 'm6i.16xlarge', 'm6i.24xlarge', 'm6i.32xlarge',
            'c5.large', 'c5.xlarge', 'c5.2xlarge', 'c5.4xlarge', 'c5.9xlarge', 'c5.12xlarge', 'c5.18xlarge', 'c5.24xlarge',
            'c5n.large', 'c5n.xlarge', 'c5n.2xlarge', 'c5n.4xlarge', 'c5n.9xlarge', 'c5n.18xlarge',
            'r5.large', 'r5.xlarge', 'r5.2xlarge', 'r5.4xlarge', 'r5.8xlarge', 'r5.12xlarge', 'r5.16xlarge', 'r5.24xlarge',
            'r6i.large', 'r6i.xlarge', 'r6i.2xlarge', 'r6i.4xlarge', 'r6i.8xlarge', 'r6i.12xlarge', 'r6i.16xlarge', 'r6i.24xlarge', 'r6i.32xlarge',
            'i3.large', 'i3.xlarge', 'i3.2xlarge', 'i3.4xlarge', 'i3.8xlarge', 'i3.16xlarge',
            'p3.2xlarge', 'p3.8xlarge', 'p3.16xlarge',
            'g4dn.xlarge', 'g4dn.2xlarge', 'g4dn.4xlarge', 'g4dn.8xlarge', 'g4dn.12xlarge', 'g4dn.16xlarge'
        ]
        
        for instance_type in instance_types:
            try:
                # Get pricing for specific instance type
                response = self.pricing_client.get_products(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'instanceType',
                            'Value': instance_type
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'location',
                            'Value': self._get_location_name(self.region)
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'tenancy',
                            'Value': 'Shared'
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'operatingSystem',
                            'Value': 'Linux'
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'preInstalledSw',
                            'Value': 'NA'
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'capacitystatus',
                            'Value': 'Used'
                        }
                    ]
                )
                
                if response['PriceList']:
                    price_data = json.loads(response['PriceList'][0])
                    
                    # Extract on-demand pricing
                    terms = price_data.get('terms', {})
                    on_demand = terms.get('OnDemand', {})
                    
                    if on_demand:
                        for term_key, term_data in on_demand.items():
                            price_dimensions = term_data.get('priceDimensions', {})
                            for dim_key, dim_data in price_dimensions.items():
                                price_per_unit = dim_data.get('pricePerUnit', {})
                                if 'USD' in price_per_unit:
                                    hourly_price = float(price_per_unit['USD'])
                                    self.pricing_data['ec2_pricing'][instance_type] = hourly_price
                                    logger.info(f"EC2 {instance_type}: ${hourly_price}/hour")
                                    break
                            break
                
            except Exception as e:
                logger.warning(f"Failed to fetch pricing for EC2 {instance_type}: {str(e)}")
                continue
    
    def fetch_rds_pricing(self):
        """Fetch RDS pricing for common instance types"""
        logger.info(f"Fetching RDS pricing for region {self.region}")
        
        # Common RDS instance types
        instance_types = [
            'db.t2.micro', 'db.t2.small', 'db.t2.medium', 'db.t2.large', 'db.t2.xlarge', 'db.t2.2xlarge',
            'db.t3.micro', 'db.t3.small', 'db.t3.medium', 'db.t3.large', 'db.t3.xlarge', 'db.t3.2xlarge',
            'db.m5.large', 'db.m5.xlarge', 'db.m5.2xlarge', 'db.m5.4xlarge', 'db.m5.8xlarge', 'db.m5.12xlarge', 'db.m5.16xlarge', 'db.m5.24xlarge',
            'db.m6i.large', 'db.m6i.xlarge', 'db.m6i.2xlarge', 'db.m6i.4xlarge', 'db.m6i.8xlarge', 'db.m6i.12xlarge', 'db.m6i.16xlarge', 'db.m6i.24xlarge', 'db.m6i.32xlarge',
            'db.r5.large', 'db.r5.xlarge', 'db.r5.2xlarge', 'db.r5.4xlarge', 'db.r5.8xlarge', 'db.r5.12xlarge', 'db.r5.16xlarge', 'db.r5.24xlarge',
            'db.r6i.large', 'db.r6i.xlarge', 'db.r6i.2xlarge', 'db.r6i.4xlarge', 'db.r6i.8xlarge', 'db.r6i.12xlarge', 'db.r6i.16xlarge', 'db.r6i.24xlarge', 'db.r6i.32xlarge'
        ]
        
        for instance_type in instance_types:
            try:
                # Get pricing for PostgreSQL (most common in your setup)
                response = self.pricing_client.get_products(
                    ServiceCode='AmazonRDS',
                    Filters=[
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'instanceType',
                            'Value': instance_type
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'location',
                            'Value': self._get_location_name(self.region)
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'databaseEngine',
                            'Value': 'PostgreSQL'
                        },
                        {
                            'Type': 'TERM_MATCH',
                            'Field': 'deploymentOption',
                            'Value': 'Single-AZ'
                        }
                    ]
                )
                
                if response['PriceList']:
                    price_data = json.loads(response['PriceList'][0])
                    
                    # Extract on-demand pricing
                    terms = price_data.get('terms', {})
                    on_demand = terms.get('OnDemand', {})
                    
                    if on_demand:
                        for term_key, term_data in on_demand.items():
                            price_dimensions = term_data.get('priceDimensions', {})
                            for dim_key, dim_data in price_dimensions.items():
                                price_per_unit = dim_data.get('pricePerUnit', {})
                                if 'USD' in price_per_unit:
                                    hourly_price = float(price_per_unit['USD'])
                                    self.pricing_data['rds_pricing'][instance_type] = hourly_price
                                    logger.info(f"RDS {instance_type}: ${hourly_price}/hour")
                                    break
                            break
                
            except Exception as e:
                logger.warning(f"Failed to fetch pricing for RDS {instance_type}: {str(e)}")
                continue
    
    def fetch_eks_pricing(self):
        """Fetch EKS cluster pricing"""
        logger.info(f"Fetching EKS pricing for region {self.region}")
        
        try:
            response = self.pricing_client.get_products(
                ServiceCode='AmazonEKS',
                Filters=[
                    {
                        'Type': 'TERM_MATCH',
                        'Field': 'location',
                        'Value': self._get_location_name(self.region)
                    },
                    {
                        'Type': 'TERM_MATCH',
                        'Field': 'usagetype',
                        'Value': f'{self._get_region_code(self.region)}-EKS-Cluster-Hour'
                    }
                ]
            )
            
            if response['PriceList']:
                price_data = json.loads(response['PriceList'][0])
                
                # Extract on-demand pricing
                terms = price_data.get('terms', {})
                on_demand = terms.get('OnDemand', {})
                
                if on_demand:
                    for term_key, term_data in on_demand.items():
                        price_dimensions = term_data.get('priceDimensions', {})
                        for dim_key, dim_data in price_dimensions.items():
                            price_per_unit = dim_data.get('pricePerUnit', {})
                            if 'USD' in price_per_unit:
                                hourly_price = float(price_per_unit['USD'])
                                self.pricing_data['eks_pricing'] = {
                                    'cluster_hour': hourly_price
                                }
                                logger.info(f"EKS Cluster: ${hourly_price}/hour")
                                break
                        break
        
        except Exception as e:
            logger.warning(f"Failed to fetch EKS pricing: {str(e)}")
            # Set default EKS pricing if fetch fails
            self.pricing_data['eks_pricing'] = {
                'cluster_hour': 0.10  # Standard EKS cluster cost
            }
    
    def _get_location_name(self, region):
        """Convert AWS region code to location name used in pricing API"""
        region_mapping = {
            'us-east-1': 'US East (N. Virginia)',
            'us-east-2': 'US East (Ohio)',
            'us-west-1': 'US West (N. California)',
            'us-west-2': 'US West (Oregon)',
            'ap-southeast-1': 'Asia Pacific (Singapore)',
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'ap-southeast-3': 'Asia Pacific (Jakarta)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-northeast-2': 'Asia Pacific (Seoul)',
            'ap-northeast-3': 'Asia Pacific (Osaka)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'eu-west-1': 'Europe (Ireland)',
            'eu-west-2': 'Europe (London)',
            'eu-west-3': 'Europe (Paris)',
            'eu-central-1': 'Europe (Frankfurt)',
            'eu-north-1': 'Europe (Stockholm)',
            'ca-central-1': 'Canada (Central)',
            'sa-east-1': 'South America (Sao Paulo)'
        }
        return region_mapping.get(region, 'Asia Pacific (Sydney)')
    
    def _get_region_code(self, region):
        """Get the region code prefix used in usage types"""
        region_codes = {
            'us-east-1': 'USE1',
            'us-east-2': 'USE2',
            'us-west-1': 'USW1',
            'us-west-2': 'USW2',
            'ap-southeast-1': 'APS1',
            'ap-southeast-2': 'APS2',
            'ap-southeast-3': 'APS3',
            'ap-northeast-1': 'APN1',
            'ap-northeast-2': 'APN2',
            'ap-northeast-3': 'APN3',
            'ap-south-1': 'APS1',
            'eu-west-1': 'EUW1',
            'eu-west-2': 'EUW2',
            'eu-west-3': 'EUW3',
            'eu-central-1': 'EUC1',
            'eu-north-1': 'EUN1',
            'ca-central-1': 'CAN1',
            'sa-east-1': 'SAE1'
        }
        return region_codes.get(region, 'APS2')
    
    def fetch_all_pricing(self):
        """Fetch all pricing data"""
        logger.info("Starting AWS pricing fetch...")
        
        self.fetch_ec2_pricing()
        self.fetch_rds_pricing()
        self.fetch_eks_pricing()
        
        logger.info("Pricing fetch completed")
        return self.pricing_data
    
    def save_pricing_config(self, output_file='cost_config.json'):
        """Save pricing data to cost_config.json"""
        with open(output_file, 'w') as f:
            json.dump(self.pricing_data, f, indent=2)
        
        logger.info(f"Pricing data saved to {output_file}")
        print(f"Updated {output_file} with current AWS pricing")
        print(f"EC2 instances: {len(self.pricing_data['ec2_pricing'])}")
        print(f"RDS instances: {len(self.pricing_data['rds_pricing'])}")
        print(f"EKS pricing: {'Yes' if self.pricing_data['eks_pricing'] else 'No'}")


def main():
    """Main function to fetch and update pricing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch AWS pricing data')
    parser.add_argument('--region', default='ap-southeast-2', 
                       help='AWS region to fetch pricing for (default: ap-southeast-2)')
    parser.add_argument('--output', default='cost_config.json',
                       help='Output file for pricing data (default: cost_config.json)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    try:
        fetcher = AWSPricingFetcher(region=args.region)
        fetcher.fetch_all_pricing()
        fetcher.save_pricing_config(args.output)
        
    except Exception as e:
        logger.error(f"Failed to fetch pricing: {str(e)}")
        print(f"Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())