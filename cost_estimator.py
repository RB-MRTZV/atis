#!/usr/bin/env python3
import json
import logging
import os
from datetime import datetime
from collections import defaultdict
import pandas as pd
from aws_pricing_fetcher import AWSPricingFetcher

logger = logging.getLogger(__name__)

class CostEstimator:
    def __init__(self, region='ap-southeast-2', currency='AUD', config_file=None):
        self.region = region
        self.currency = currency
        self.pricing_fetcher = AWSPricingFetcher(region=region, currency=currency)
        
        # Load legacy config if provided, otherwise use dynamic pricing
        if config_file and os.path.exists(config_file):
            self.config = self._load_config(config_file)
            self.use_dynamic_pricing = False
            logger.info(f"Using static pricing from {config_file}")
        else:
            self.config = {
                'currency': currency,
                'region': region,
                'ec2_pricing': {},
                'rds_pricing': {},
                'eks_pricing': {'cluster_hour': 0.10}
            }
            self.use_dynamic_pricing = True
            logger.info("Using dynamic AWS pricing API")
        
        self.results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        self.detailed_results = []
    
    def _load_config(self, config_file):
        """Load cost configuration"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load cost config: {str(e)}")
            return {}
    
    def estimate_ec2_cost(self, instances):
        """Estimate costs for EC2 instances"""
        logger.info("Estimating EC2 costs...")
        
        for instance in instances:
            instance_type = instance['instance_type']
            environment = instance['environment']
            
            hourly_cost = self.config['ec2_pricing'].get(instance_type, 0)
            if hourly_cost == 0:
                if self.use_dynamic_pricing:
                    # Try to fetch pricing for this specific instance type
                    logger.info(f"Fetching missing pricing for EC2 instance type: {instance_type}")
                    new_pricing = self.pricing_fetcher.fetch_ec2_pricing([instance_type])
                    if instance_type in new_pricing:
                        hourly_cost = new_pricing[instance_type]
                        self.config['ec2_pricing'][instance_type] = hourly_cost
                        logger.info(f"Found pricing for {instance_type}: ${hourly_cost:.4f} {self.currency}/hour")
                    else:
                        logger.warning(f"No pricing found for EC2 instance type: {instance_type}")
                else:
                    logger.warning(f"No pricing found for EC2 instance type: {instance_type}")
            
            daily_cost = hourly_cost * 24
            monthly_cost = daily_cost * 30
            
            # Add to aggregated results
            self.results['EC2'][environment]['daily'] += daily_cost
            self.results['EC2'][environment]['monthly'] += monthly_cost
            self.results['EC2'][environment]['count'] += 1
            
            # Add to detailed results
            self.detailed_results.append({
                'service': 'EC2',
                'resource_id': instance['instance_id'],
                'instance_type': instance_type,
                'environment': environment,
                'type': instance['type'],
                'in_asg': instance['in_asg'],
                'asg_name': instance.get('asg_name', ''),
                'hourly_cost': hourly_cost,
                'daily_cost': daily_cost,
                'monthly_cost': monthly_cost,
                'currency': self.config['currency']
            })
    
    def estimate_rds_cost(self, rds_instances):
        """Estimate costs for RDS instances"""
        logger.info("Estimating RDS costs...")
        
        for instance in rds_instances:
            instance_class = instance.get('instance_class', '')
            environment = instance['environment']
            multi_az = instance.get('multi_az', False)
            
            # Get base hourly cost
            hourly_cost = self.config['rds_pricing'].get(instance_class, 0)
            if hourly_cost == 0:
                if self.use_dynamic_pricing:
                    # Try to fetch pricing for this specific instance class
                    logger.info(f"Fetching missing pricing for RDS instance class: {instance_class}")
                    new_pricing = self.pricing_fetcher.fetch_rds_pricing([instance_class])
                    if instance_class in new_pricing:
                        hourly_cost = new_pricing[instance_class]
                        self.config['rds_pricing'][instance_class] = hourly_cost
                        logger.info(f"Found pricing for {instance_class}: ${hourly_cost:.4f} {self.currency}/hour")
                    else:
                        logger.warning(f"No pricing found for RDS instance class: {instance_class}")
                else:
                    logger.warning(f"No pricing found for RDS instance class: {instance_class}")
            
            # Double cost for Multi-AZ deployments
            if multi_az:
                hourly_cost *= 2
            
            daily_cost = hourly_cost * 24
            monthly_cost = daily_cost * 30
            
            # Add to aggregated results
            self.results['RDS'][environment]['daily'] += daily_cost
            self.results['RDS'][environment]['monthly'] += monthly_cost
            self.results['RDS'][environment]['count'] += 1
            
            # Add to detailed results
            self.detailed_results.append({
                'service': 'RDS',
                'resource_id': instance.get('instance_id', instance.get('cluster_id', '')),
                'instance_type': instance_class,
                'environment': environment,
                'engine': instance.get('engine', ''),
                'multi_az': multi_az,
                'storage_type': instance.get('storage_type', ''),
                'hourly_cost': hourly_cost,
                'daily_cost': daily_cost,
                'monthly_cost': monthly_cost,
                'currency': self.config['currency']
            })
    
    def estimate_eks_cost(self, eks_nodes):
        """Estimate costs for EKS nodes"""
        logger.info("Estimating EKS costs...")
        
        for node in eks_nodes:
            instance_type = node['instance_type']
            environment = node['environment']
            
            # EKS nodes use EC2 pricing
            hourly_cost = self.config['ec2_pricing'].get(instance_type, 0)
            if hourly_cost == 0:
                if self.use_dynamic_pricing:
                    # Try to fetch pricing for this specific instance type
                    logger.info(f"Fetching missing pricing for EKS node type: {instance_type}")
                    new_pricing = self.pricing_fetcher.fetch_ec2_pricing([instance_type])
                    if instance_type in new_pricing:
                        hourly_cost = new_pricing[instance_type]
                        self.config['ec2_pricing'][instance_type] = hourly_cost
                        logger.info(f"Found pricing for {instance_type}: ${hourly_cost:.4f} {self.currency}/hour")
                    else:
                        logger.warning(f"No pricing found for EKS node type: {instance_type}")
                else:
                    logger.warning(f"No pricing found for EKS node type: {instance_type}")
            
            daily_cost = hourly_cost * 24
            monthly_cost = daily_cost * 30
            
            # Add to aggregated results
            self.results['EKS'][environment]['daily'] += daily_cost
            self.results['EKS'][environment]['monthly'] += monthly_cost
            self.results['EKS'][environment]['count'] += 1
            
            # Add to detailed results
            self.detailed_results.append({
                'service': 'EKS',
                'resource_id': f"{node['cluster_name']}/{node['nodegroup_name']}",
                'instance_type': instance_type,
                'environment': environment,
                'type': 'EKS Manage Node',
                'cluster_name': node['cluster_name'],
                'nodegroup_name': node['nodegroup_name'],
                'deployment_count': node.get('deployment_count', 'N/A'),
                'hourly_cost': hourly_cost,
                'daily_cost': daily_cost,
                'monthly_cost': monthly_cost,
                'currency': self.config['currency']
            })
    
    def estimate_all_costs(self, scan_results):
        """Estimate costs for all resources"""
        logger.info("Starting cost estimation...")
        
        # Reset results
        self.results = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        self.detailed_results = []
        
        # Fetch dynamic pricing if needed
        if self.use_dynamic_pricing:
            logger.info("Fetching current AWS pricing data...")
            dynamic_pricing = self.pricing_fetcher.fetch_pricing_for_resources(scan_results)
            
            # Update config with fetched pricing
            self.config.update(dynamic_pricing)
            logger.info(f"Updated pricing data: {len(self.config['ec2_pricing'])} EC2 types, {len(self.config['rds_pricing'])} RDS types")
        
        # Estimate costs for each service
        self.estimate_ec2_cost(scan_results.get('ec2_instances', []))
        self.estimate_rds_cost(scan_results.get('rds_instances', []))
        self.estimate_eks_cost(scan_results.get('eks_nodes', []))
        
        # Add metadata
        self.results['metadata'] = {
            'account_id': scan_results.get('account_id'),
            'region': scan_results.get('region'),
            'scan_time': scan_results.get('scan_time'),
            'estimation_time': datetime.utcnow().isoformat(),
            'currency': self.config['currency'],
            'config_last_updated': self.config.get('last_updated'),
            'pricing_method': 'dynamic_api' if self.use_dynamic_pricing else 'static_config'
        }
        
        logger.info("Cost estimation complete")
        return self.results, self.detailed_results
    
    def get_summary(self):
        """Get cost summary by service and environment"""
        summary = []
        
        for service in ['EC2', 'RDS', 'EKS']:
            for environment, costs in self.results[service].items():
                summary.append({
                    'service': service,
                    'environment': environment,
                    'resource_count': int(costs['count']),
                    'daily_cost': round(costs['daily'], 2),
                    'monthly_cost': round(costs['monthly'], 2),
                    'currency': self.config['currency']
                })
        
        # Calculate totals
        total_daily = sum(item['daily_cost'] for item in summary)
        total_monthly = sum(item['monthly_cost'] for item in summary)
        
        summary.append({
            'service': 'TOTAL',
            'environment': 'ALL',
            'resource_count': sum(item['resource_count'] for item in summary),
            'daily_cost': round(total_daily, 2),
            'monthly_cost': round(total_monthly, 2),
            'currency': self.config['currency']
        })
        
        return summary

if __name__ == "__main__":
    # Load scan results
    with open('aws_scan_results.json', 'r') as f:
        scan_results = json.load(f)
    
    # Estimate costs using dynamic pricing
    estimator = CostEstimator(region='ap-southeast-2', currency='AUD')
    results, detailed_results = estimator.estimate_all_costs(scan_results)
    
    # Save results
    with open('cost_estimation_results.json', 'w') as f:
        json.dump({
            'summary': estimator.get_summary(),
            'detailed': detailed_results,
            'metadata': results['metadata']
        }, f, indent=2)
    
    print("Cost estimation complete. Results saved to cost_estimation_results.json")