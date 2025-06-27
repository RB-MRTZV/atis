#!/usr/bin/env python3
"""
AWS Pricing Fetcher - Dynamically fetches AWS pricing data using AWS Price List API
Caches pricing data locally to avoid repeated API calls
"""

import json
import logging
import boto3
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

class AWSPricingFetcher:
    def __init__(self, region='ap-southeast-2', currency='AUD'):
        self.region = region
        self.currency = currency
        self.cache_dir = Path('pricing_cache')
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize AWS pricing client (us-east-1 is the only region for pricing API)
        self.pricing_client = boto3.client('pricing', region_name='us-east-1')
        
        # Cache configuration
        self.cache_duration_hours = 24  # Cache for 24 hours
        
    def _get_cache_filename(self, service):
        """Generate cache filename for a service"""
        return self.cache_dir / f"{service}_{self.region}_{self.currency}.json"
    
    def _is_cache_valid(self, cache_file):
        """Check if cache file exists and is not expired"""
        if not cache_file.exists():
            return False
            
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                cache_time = datetime.fromisoformat(data.get('cached_at', ''))
                expiry_time = cache_time + timedelta(hours=self.cache_duration_hours)
                return datetime.now() < expiry_time
        except Exception as e:
            logger.warning(f"Cache validation failed for {cache_file}: {e}")
            return False
    
    def _save_to_cache(self, service, pricing_data):
        """Save pricing data to cache"""
        cache_file = self._get_cache_filename(service)
        cache_data = {
            'service': service,
            'region': self.region,
            'currency': self.currency,
            'cached_at': datetime.now().isoformat(),
            'pricing_data': pricing_data
        }
        
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            logger.info(f"Pricing data cached for {service}")
        except Exception as e:
            logger.error(f"Failed to cache pricing data for {service}: {e}")
    
    def _load_from_cache(self, service):
        """Load pricing data from cache"""
        cache_file = self._get_cache_filename(service)
        
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
                return data['pricing_data']
        except Exception as e:
            logger.error(f"Failed to load cached pricing data for {service}: {e}")
            return {}
    
    def fetch_ec2_pricing(self, instance_types):
        """Fetch EC2 pricing for specific instance types"""
        cache_file = self._get_cache_filename('ec2')
        
        # Check cache first
        if self._is_cache_valid(cache_file):
            logger.info("Using cached EC2 pricing data")
            return self._load_from_cache('ec2')
        
        logger.info(f"Fetching EC2 pricing from AWS API for region {self.region}")
        pricing_data = {}
        
        try:
            # Get products for EC2
            paginator = self.pricing_client.get_paginator('get_products')
            
            for instance_type in instance_types:
                logger.debug(f"Fetching pricing for EC2 instance type: {instance_type}")
                
                # Fetch pricing for this specific instance type
                response_iterator = paginator.paginate(
                    ServiceCode='AmazonEC2',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name()},
                        {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                        {'Type': 'TERM_MATCH', 'Field': 'operating-system', 'Value': 'Linux'},
                        {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'}
                    ]
                )
                
                for page in response_iterator:
                    for price_item in page['PriceList']:
                        product = json.loads(price_item)
                        
                        # Extract On-Demand pricing
                        terms = product.get('terms', {})
                        on_demand = terms.get('OnDemand', {})
                        
                        for term_key, term_data in on_demand.items():
                            price_dimensions = term_data.get('priceDimensions', {})
                            for price_key, price_data in price_dimensions.items():
                                price_per_unit = price_data.get('pricePerUnit', {})
                                hourly_cost = float(price_per_unit.get(self.currency, 0))
                                
                                if hourly_cost > 0:
                                    pricing_data[instance_type] = hourly_cost
                                    logger.debug(f"Found pricing for {instance_type}: {hourly_cost} {self.currency}/hour")
                                    break
                        
                        if instance_type in pricing_data:
                            break
                    
                    if instance_type in pricing_data:
                        break
                
                if instance_type not in pricing_data:
                    logger.warning(f"No pricing found for EC2 instance type: {instance_type}")
        
        except Exception as e:
            logger.error(f"Failed to fetch EC2 pricing: {e}")
            return {}
        
        # Cache the results
        self._save_to_cache('ec2', pricing_data)
        return pricing_data
    
    def fetch_rds_pricing(self, instance_classes):
        """Fetch RDS pricing for specific instance classes"""
        cache_file = self._get_cache_filename('rds')
        
        # Check cache first
        if self._is_cache_valid(cache_file):
            logger.info("Using cached RDS pricing data")
            return self._load_from_cache('rds')
        
        logger.info(f"Fetching RDS pricing from AWS API for region {self.region}")
        pricing_data = {}
        
        try:
            paginator = self.pricing_client.get_paginator('get_products')
            
            for instance_class in instance_classes:
                logger.debug(f"Fetching pricing for RDS instance class: {instance_class}")
                
                response_iterator = paginator.paginate(
                    ServiceCode='AmazonRDS',
                    Filters=[
                        {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_class},
                        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': self._get_location_name()},
                        {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': 'Single-AZ'}
                    ]
                )
                
                for page in response_iterator:
                    for price_item in page['PriceList']:
                        product = json.loads(price_item)
                        
                        # Extract On-Demand pricing
                        terms = product.get('terms', {})
                        on_demand = terms.get('OnDemand', {})
                        
                        for term_key, term_data in on_demand.items():
                            price_dimensions = term_data.get('priceDimensions', {})
                            for price_key, price_data in price_dimensions.items():
                                price_per_unit = price_data.get('pricePerUnit', {})
                                hourly_cost = float(price_per_unit.get(self.currency, 0))
                                
                                if hourly_cost > 0:
                                    pricing_data[instance_class] = hourly_cost
                                    logger.debug(f"Found pricing for {instance_class}: {hourly_cost} {self.currency}/hour")
                                    break
                        
                        if instance_class in pricing_data:
                            break
                    
                    if instance_class in pricing_data:
                        break
                
                if instance_class not in pricing_data:
                    logger.warning(f"No pricing found for RDS instance class: {instance_class}")
        
        except Exception as e:
            logger.error(f"Failed to fetch RDS pricing: {e}")
            return {}
        
        # Cache the results
        self._save_to_cache('rds', pricing_data)
        return pricing_data
    
    def _get_location_name(self):
        """Convert AWS region code to location name for pricing API"""
        region_mapping = {
            'ap-southeast-2': 'Asia Pacific (Sydney)',
            'us-east-1': 'US East (N. Virginia)',
            'us-west-2': 'US West (Oregon)',
            'eu-west-1': 'Europe (Ireland)',
            'ap-northeast-1': 'Asia Pacific (Tokyo)',
            'ap-south-1': 'Asia Pacific (Mumbai)',
            'eu-central-1': 'Europe (Frankfurt)',
            # Add more regions as needed
        }
        
        return region_mapping.get(self.region, 'Asia Pacific (Sydney)')
    
    def fetch_pricing_for_resources(self, scan_results):
        """Fetch pricing for all resources found in scan results"""
        logger.info("Fetching pricing for discovered resources...")
        
        # Extract unique instance types from scan results
        ec2_instance_types = set()
        rds_instance_classes = set()
        
        # Collect EC2 instance types
        for instance in scan_results.get('ec2_instances', []):
            ec2_instance_types.add(instance['instance_type'])
        
        # Collect EKS node instance types (they use EC2 pricing)
        for node in scan_results.get('eks_nodes', []):
            ec2_instance_types.add(node['instance_type'])
        
        # Collect RDS instance classes
        for instance in scan_results.get('rds_instances', []):
            if 'instance_class' in instance:
                rds_instance_classes.add(instance['instance_class'])
        
        # Fetch pricing data
        pricing_data = {
            'currency': self.currency,
            'region': self.region,
            'last_updated': datetime.now().isoformat(),
            'ec2_pricing': {},
            'rds_pricing': {},
            'eks_pricing': {'cluster_hour': 0.10}  # EKS cluster cost is standard
        }
        
        if ec2_instance_types:
            logger.info(f"Fetching pricing for {len(ec2_instance_types)} EC2 instance types")
            ec2_pricing = self.fetch_ec2_pricing(list(ec2_instance_types))
            
            # Add fallback pricing for common instances if API doesn't return data
            if not ec2_pricing:
                logger.warning("No EC2 pricing data returned from API, using fallback estimates")
                ec2_pricing = self._get_fallback_ec2_pricing(list(ec2_instance_types))
            
            pricing_data['ec2_pricing'] = ec2_pricing
        
        if rds_instance_classes:
            logger.info(f"Fetching pricing for {len(rds_instance_classes)} RDS instance classes")
            rds_pricing = self.fetch_rds_pricing(list(rds_instance_classes))
            
            # Add fallback pricing for common instances if API doesn't return data
            if not rds_pricing:
                logger.warning("No RDS pricing data returned from API, using fallback estimates")
                rds_pricing = self._get_fallback_rds_pricing(list(rds_instance_classes))
            
            pricing_data['rds_pricing'] = rds_pricing
        
        return pricing_data
    
    def _get_fallback_ec2_pricing(self, instance_types):
        """Provide fallback pricing estimates for common EC2 instance types in AUD"""
        fallback_pricing = {
            # T3 instances (AUD/hour)
            't3.nano': 0.0068,
            't3.micro': 0.0136,
            't3.small': 0.0272,
            't3.medium': 0.0544,
            't3.large': 0.1088,
            't3.xlarge': 0.2176,
            't3.2xlarge': 0.4352,
            
            # T2 instances (AUD/hour)
            't2.nano': 0.0076,
            't2.micro': 0.0152,
            't2.small': 0.0304,
            't2.medium': 0.0608,
            't2.large': 0.1216,
            't2.xlarge': 0.2432,
            't2.2xlarge': 0.4864,
            
            # M5 instances (AUD/hour)
            'm5.large': 0.125,
            'm5.xlarge': 0.250,
            'm5.2xlarge': 0.500,
            'm5.4xlarge': 1.000,
            'm5.8xlarge': 2.000,
            'm5.12xlarge': 3.000,
            'm5.16xlarge': 4.000,
            'm5.24xlarge': 6.000,
            
            # C5 instances (AUD/hour)
            'c5.large': 0.115,
            'c5.xlarge': 0.230,
            'c5.2xlarge': 0.460,
            'c5.4xlarge': 0.920,
            'c5.9xlarge': 2.070,
            'c5.12xlarge': 2.760,
            'c5.18xlarge': 4.140,
            'c5.24xlarge': 5.520,
            
            # R5 instances (AUD/hour)
            'r5.large': 0.157,
            'r5.xlarge': 0.314,
            'r5.2xlarge': 0.628,
            'r5.4xlarge': 1.256,
            'r5.8xlarge': 2.512,
            'r5.12xlarge': 3.768,
            'r5.16xlarge': 5.024,
            'r5.24xlarge': 7.536
        }
        
        pricing = {}
        for instance_type in instance_types:
            if instance_type in fallback_pricing:
                pricing[instance_type] = fallback_pricing[instance_type]
                logger.info(f"Using fallback pricing for {instance_type}: ${fallback_pricing[instance_type]:.4f} AUD/hour")
            else:
                # Estimate based on instance family
                estimated_cost = self._estimate_instance_cost(instance_type)
                if estimated_cost > 0:
                    pricing[instance_type] = estimated_cost
                    logger.info(f"Estimated pricing for {instance_type}: ${estimated_cost:.4f} AUD/hour")
        
        return pricing
    
    def _get_fallback_rds_pricing(self, instance_classes):
        """Provide fallback pricing estimates for common RDS instance classes in AUD"""
        fallback_pricing = {
            # T3 instances (AUD/hour)
            'db.t3.micro': 0.029,
            'db.t3.small': 0.058,
            'db.t3.medium': 0.116,
            'db.t3.large': 0.232,
            'db.t3.xlarge': 0.464,
            'db.t3.2xlarge': 0.928,
            
            # T2 instances (AUD/hour)
            'db.t2.micro': 0.029,
            'db.t2.small': 0.058,
            'db.t2.medium': 0.116,
            'db.t2.large': 0.232,
            'db.t2.xlarge': 0.464,
            'db.t2.2xlarge': 0.928,
            
            # M5 instances (AUD/hour)
            'db.m5.large': 0.256,
            'db.m5.xlarge': 0.512,
            'db.m5.2xlarge': 1.024,
            'db.m5.4xlarge': 2.048,
            'db.m5.8xlarge': 4.096,
            'db.m5.12xlarge': 6.144,
            'db.m5.16xlarge': 8.192,
            'db.m5.24xlarge': 12.288,
            
            # R5 instances (AUD/hour)
            'db.r5.large': 0.312,
            'db.r5.xlarge': 0.624,
            'db.r5.2xlarge': 1.248,
            'db.r5.4xlarge': 2.496,
            'db.r5.8xlarge': 4.992,
            'db.r5.12xlarge': 7.488,
            'db.r5.16xlarge': 9.984,
            'db.r5.24xlarge': 14.976
        }
        
        pricing = {}
        for instance_class in instance_classes:
            if instance_class in fallback_pricing:
                pricing[instance_class] = fallback_pricing[instance_class]
                logger.info(f"Using fallback pricing for {instance_class}: ${fallback_pricing[instance_class]:.4f} AUD/hour")
            else:
                # Estimate based on instance family
                estimated_cost = self._estimate_rds_cost(instance_class)
                if estimated_cost > 0:
                    pricing[instance_class] = estimated_cost
                    logger.info(f"Estimated pricing for {instance_class}: ${estimated_cost:.4f} AUD/hour")
        
        return pricing
    
    def _estimate_instance_cost(self, instance_type):
        """Estimate cost for unknown instance types based on family patterns"""
        # Basic estimation based on instance family and size
        base_costs = {
            't3': 0.0136,  # micro base
            't2': 0.0152,  # micro base
            'm5': 0.125,   # large base
            'c5': 0.115,   # large base
            'r5': 0.157,   # large base
        }
        
        multipliers = {
            'nano': 0.5,
            'micro': 1.0,
            'small': 2.0,
            'medium': 4.0,
            'large': 8.0,
            'xlarge': 16.0,
            '2xlarge': 32.0,
            '4xlarge': 64.0,
            '8xlarge': 128.0,
            '12xlarge': 192.0,
            '16xlarge': 256.0,
            '24xlarge': 384.0
        }
        
        parts = instance_type.split('.')
        if len(parts) >= 2:
            family = parts[0]
            size = parts[1]
            
            base_cost = base_costs.get(family, 0.1)  # Default base cost
            multiplier = multipliers.get(size, 1.0)
            
            return base_cost * multiplier
        
        return 0
    
    def _estimate_rds_cost(self, instance_class):
        """Estimate cost for unknown RDS instance classes"""
        # Remove 'db.' prefix if present
        if instance_class.startswith('db.'):
            instance_type = instance_class[3:]
        else:
            instance_type = instance_class
        
        # RDS is typically 2x EC2 pricing
        ec2_cost = self._estimate_instance_cost(instance_type)
        return ec2_cost * 2.0 if ec2_cost > 0 else 0
    
    def clear_cache(self):
        """Clear all cached pricing data"""
        try:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()
            logger.info("Pricing cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear pricing cache: {e}")

if __name__ == "__main__":
    # Test the pricing fetcher
    fetcher = AWSPricingFetcher(region='ap-southeast-2', currency='AUD')
    
    # Test with some common instance types
    test_instance_types = ['t3.micro', 't3.small', 'm5.large']
    pricing = fetcher.fetch_ec2_pricing(test_instance_types)
    
    print("EC2 Pricing Test Results:")
    for instance_type, cost in pricing.items():
        print(f"  {instance_type}: ${cost:.4f} AUD/hour")