#!/usr/bin/env python3
"""
AWS Cost Optimization Data Collector

This script collects AWS resource information for cost optimization analysis.
Requires read-only access to AWS accounts.
"""

import boto3
import json
import csv
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError
import argparse
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSCostDataCollector:
    def __init__(self, profile_name=None, region='us-east-1'):
        """Initialize AWS session with specified profile and region."""
        try:
            if profile_name:
                self.session = boto3.Session(profile_name=profile_name)
            else:
                self.session = boto3.Session()
            
            self.region = region
            self.account_id = self.session.client('sts').get_caller_identity()['Account']
            logger.info(f"Connected to AWS Account: {self.account_id}")
            
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to initialize AWS session: {e}")
            raise

    def collect_storage_data(self):
        """Collect S3, EBS, and EFS storage information."""
        storage_data = {
            's3_buckets': [],
            'ebs_volumes': [],
            'ebs_snapshots': [],
            'efs_filesystems': []
        }
        
        # S3 Buckets
        try:
            s3_client = self.session.client('s3')
            buckets = s3_client.list_buckets()['Buckets']
            
            for bucket in buckets:
                bucket_info = {
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'].isoformat(),
                    'region': s3_client.get_bucket_location(Bucket=bucket['Name'])['LocationConstraint'] or 'us-east-1'
                }
                
                # Get storage class distribution
                try:
                    inventory = s3_client.list_objects_v2(Bucket=bucket['Name'], MaxKeys=1000)
                    bucket_info['object_count'] = inventory.get('KeyCount', 0)
                except ClientError:
                    bucket_info['object_count'] = 'Access Denied'
                
                storage_data['s3_buckets'].append(bucket_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect S3 data: {e}")

        # EBS Volumes
        try:
            ec2_client = self.session.client('ec2', region_name=self.region)
            volumes = ec2_client.describe_volumes()['Volumes']
            
            for volume in volumes:
                volume_info = {
                    'volume_id': volume['VolumeId'],
                    'size': volume['Size'],
                    'volume_type': volume['VolumeType'],
                    'state': volume['State'],
                    'availability_zone': volume['AvailabilityZone'],
                    'encrypted': volume['Encrypted'],
                    'attachments': len(volume['Attachments']),
                    'creation_date': volume['CreateTime'].isoformat()
                }
                storage_data['ebs_volumes'].append(volume_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect EBS volume data: {e}")

        # EBS Snapshots
        try:
            snapshots = ec2_client.describe_snapshots(OwnerIds=[self.account_id])['Snapshots']
            
            for snapshot in snapshots:
                snapshot_info = {
                    'snapshot_id': snapshot['SnapshotId'],
                    'volume_id': snapshot.get('VolumeId', 'N/A'),
                    'size': snapshot['VolumeSize'],
                    'state': snapshot['State'],
                    'start_time': snapshot['StartTime'].isoformat(),
                    'description': snapshot.get('Description', '')
                }
                storage_data['ebs_snapshots'].append(snapshot_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect EBS snapshot data: {e}")

        # EFS File Systems
        try:
            efs_client = self.session.client('efs', region_name=self.region)
            filesystems = efs_client.describe_file_systems()['FileSystems']
            
            for fs in filesystems:
                fs_info = {
                    'file_system_id': fs['FileSystemId'],
                    'name': fs.get('Name', ''),
                    'size_in_bytes': fs['SizeInBytes']['Value'],
                    'performance_mode': fs['PerformanceMode'],
                    'throughput_mode': fs['ThroughputMode'],
                    'creation_date': fs['CreationTime'].isoformat()
                }
                storage_data['efs_filesystems'].append(fs_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect EFS data: {e}")

        return storage_data

    def collect_compute_data(self):
        """Collect EC2, Lambda, and other compute resource information."""
        compute_data = {
            'ec2_instances': [],
            'lambda_functions': [],
            'rds_instances': []
        }
        
        # EC2 Instances
        try:
            ec2_client = self.session.client('ec2', region_name=self.region)
            instances = ec2_client.describe_instances()['Reservations']
            
            for reservation in instances:
                for instance in reservation['Instances']:
                    instance_info = {
                        'instance_id': instance['InstanceId'],
                        'instance_type': instance['InstanceType'],
                        'state': instance['State']['Name'],
                        'launch_time': instance.get('LaunchTime', '').isoformat() if instance.get('LaunchTime') else '',
                        'availability_zone': instance['Placement']['AvailabilityZone'],
                        'platform': instance.get('Platform', 'Linux'),
                        'monitoring': instance['Monitoring']['State']
                    }
                    compute_data['ec2_instances'].append(instance_info)
                    
        except ClientError as e:
            logger.warning(f"Failed to collect EC2 data: {e}")

        # Lambda Functions
        try:
            lambda_client = self.session.client('lambda', region_name=self.region)
            functions = lambda_client.list_functions()['Functions']
            
            for func in functions:
                func_info = {
                    'function_name': func['FunctionName'],
                    'runtime': func['Runtime'],
                    'memory_size': func['MemorySize'],
                    'timeout': func['Timeout'],
                    'last_modified': func['LastModified']
                }
                compute_data['lambda_functions'].append(func_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect Lambda data: {e}")

        # RDS Instances
        try:
            rds_client = self.session.client('rds', region_name=self.region)
            instances = rds_client.describe_db_instances()['DBInstances']
            
            for instance in instances:
                instance_info = {
                    'db_instance_identifier': instance['DBInstanceIdentifier'],
                    'db_instance_class': instance['DBInstanceClass'],
                    'engine': instance['Engine'],
                    'engine_version': instance['EngineVersion'],
                    'allocated_storage': instance['AllocatedStorage'],
                    'storage_type': instance['StorageType'],
                    'multi_az': instance['MultiAZ'],
                    'availability_zone': instance.get('AvailabilityZone', ''),
                    'instance_create_time': instance['InstanceCreateTime'].isoformat()
                }
                compute_data['rds_instances'].append(instance_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect RDS data: {e}")

        return compute_data

    def collect_log_data(self):
        """Collect CloudWatch Logs information."""
        log_data = {
            'log_groups': []
        }
        
        try:
            logs_client = self.session.client('logs', region_name=self.region)
            log_groups = logs_client.describe_log_groups()['logGroups']
            
            for log_group in log_groups:
                group_info = {
                    'log_group_name': log_group['logGroupName'],
                    'retention_in_days': log_group.get('retentionInDays', 'Never Expire'),
                    'stored_bytes': log_group.get('storedBytes', 0),
                    'creation_time': datetime.fromtimestamp(log_group['creationTime'] / 1000).isoformat()
                }
                log_data['log_groups'].append(group_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect CloudWatch Logs data: {e}")

        return log_data

    def collect_network_data(self):
        """Collect network-related cost information."""
        network_data = {
            'nat_gateways': [],
            'load_balancers': [],
            'vpc_endpoints': []
        }
        
        try:
            ec2_client = self.session.client('ec2', region_name=self.region)
            
            # NAT Gateways
            nat_gateways = ec2_client.describe_nat_gateways()['NatGateways']
            for nat in nat_gateways:
                nat_info = {
                    'nat_gateway_id': nat['NatGatewayId'],
                    'state': nat['State'],
                    'subnet_id': nat['SubnetId'],
                    'vpc_id': nat['VpcId'],
                    'create_time': nat['CreateTime'].isoformat()
                }
                network_data['nat_gateways'].append(nat_info)
            
            # VPC Endpoints
            vpc_endpoints = ec2_client.describe_vpc_endpoints()['VpcEndpoints']
            for endpoint in vpc_endpoints:
                endpoint_info = {
                    'vpc_endpoint_id': endpoint['VpcEndpointId'],
                    'vpc_endpoint_type': endpoint['VpcEndpointType'],
                    'service_name': endpoint['ServiceName'],
                    'state': endpoint['State'],
                    'creation_timestamp': endpoint['CreationTimestamp'].isoformat()
                }
                network_data['vpc_endpoints'].append(endpoint_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect network data: {e}")

        # Load Balancers
        try:
            elb_client = self.session.client('elbv2', region_name=self.region)
            load_balancers = elb_client.describe_load_balancers()['LoadBalancers']
            
            for lb in load_balancers:
                lb_info = {
                    'load_balancer_arn': lb['LoadBalancerArn'],
                    'load_balancer_name': lb['LoadBalancerName'],
                    'type': lb['Type'],
                    'scheme': lb['Scheme'],
                    'state': lb['State']['Code'],
                    'created_time': lb['CreatedTime'].isoformat()
                }
                network_data['load_balancers'].append(lb_info)
                
        except ClientError as e:
            logger.warning(f"Failed to collect load balancer data: {e}")

        return network_data

    def collect_macie_data(self):
        """Collect Amazon Macie information."""
        macie_data = {
            'macie_status': 'Not Available',
            'data_discovery_jobs': [],
            'findings': []
        }
        
        try:
            macie_client = self.session.client('macie2', region_name=self.region)
            
            # Check Macie status
            try:
                status = macie_client.get_macie_session()
                macie_data['macie_status'] = status['status']
                macie_data['service_role'] = status.get('serviceRole', '')
                macie_data['created_at'] = status.get('createdAt', '').isoformat() if status.get('createdAt') else ''
                
                # Get discovery jobs if Macie is enabled
                if status['status'] == 'ENABLED':
                    jobs = macie_client.list_classification_jobs()['items']
                    for job in jobs:
                        job_info = {
                            'job_id': job['jobId'],
                            'job_type': job['jobType'],
                            'job_status': job['jobStatus'],
                            'name': job.get('name', ''),
                            'created_at': job['createdAt'].isoformat()
                        }
                        macie_data['data_discovery_jobs'].append(job_info)
                        
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    macie_data['macie_status'] = 'DISABLED'
                else:
                    logger.warning(f"Failed to get Macie status: {e}")
                    
        except ClientError as e:
            logger.warning(f"Macie service not available in region {self.region}: {e}")

        return macie_data

    def collect_cost_explorer_data(self, days_back=30):
        """Collect cost data from AWS Cost Explorer for target services."""
        cost_data = {
            'monthly_costs': {},
            'service_costs': {},
            'daily_costs': [],
            'rightsizing_recommendations': []
        }
        
        try:
            ce_client = self.session.client('ce', region_name='us-east-1')  # Cost Explorer is global
            
            # Define time period
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            time_period = {
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            }
            
            # Get monthly costs by service for our target services
            target_services = [
                'Amazon Elastic Compute Cloud - Compute',
                'Amazon Simple Storage Service',
                'Amazon Elastic Block Store',
                'Amazon Elastic File System',
                'Amazon CloudWatch',
                'Amazon EC2-Instance',
                'Amazon RDS Service',
                'AWS Lambda',
                'Amazon Macie',
                'Amazon ElastiCache',
                'Amazon VPC',
                'Amazon Route 53'
            ]
            
            logger.info("Collecting Cost Explorer data for target services...")
            
            # Get cost by service
            try:
                response = ce_client.get_cost_and_usage(
                    TimePeriod=time_period,
                    Granularity='MONTHLY',
                    Metrics=['BlendedCost', 'UsageQuantity'],
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                    ]
                )
                
                for result in response['ResultsByTime']:
                    month = result['TimePeriod']['Start']
                    cost_data['monthly_costs'][month] = {}
                    
                    for group in result['Groups']:
                        service_name = group['Keys'][0]
                        amount = float(group['Metrics']['BlendedCost']['Amount'])
                        unit = group['Metrics']['BlendedCost']['Unit']
                        
                        if amount > 0:  # Only include services with actual costs
                            cost_data['monthly_costs'][month][service_name] = {
                                'amount': amount,
                                'unit': unit,
                                'usage_quantity': float(group['Metrics']['UsageQuantity']['Amount'])
                            }
                
            except ClientError as e:
                logger.warning(f"Failed to get monthly cost data: {e}")
            
            # Get daily costs for trend analysis
            try:
                daily_response = ce_client.get_cost_and_usage(
                    TimePeriod=time_period,
                    Granularity='DAILY',
                    Metrics=['BlendedCost'],
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                    ],
                    Filter={
                        'Dimensions': {
                            'Key': 'SERVICE',
                            'Values': target_services,
                            'MatchOptions': ['EQUALS']
                        }
                    }
                )
                
                for result in daily_response['ResultsByTime']:
                    date = result['TimePeriod']['Start']
                    daily_total = 0
                    service_breakdown = {}
                    
                    for group in result['Groups']:
                        service_name = group['Keys'][0]
                        amount = float(group['Metrics']['BlendedCost']['Amount'])
                        if amount > 0:
                            service_breakdown[service_name] = amount
                            daily_total += amount
                    
                    if daily_total > 0:
                        cost_data['daily_costs'].append({
                            'date': date,
                            'total_cost': daily_total,
                            'services': service_breakdown
                        })
                
            except ClientError as e:
                logger.warning(f"Failed to get daily cost data: {e}")
            
            # Get rightsizing recommendations
            try:
                rightsizing_response = ce_client.get_rightsizing_recommendation(
                    Service='AmazonEC2',
                    Configuration={
                        'BenefitsConsidered': True,
                        'RecommendationTarget': 'SAME_INSTANCE_FAMILY'
                    }
                )
                
                for rec in rightsizing_response.get('RightsizingRecommendations', []):
                    recommendation = {
                        'account_id': rec.get('AccountId', ''),
                        'current_instance': rec.get('CurrentInstance', {}),
                        'rightsizing_type': rec.get('RightsizingType', ''),
                        'modify_recommendation': rec.get('ModifyRecommendationDetail', {}),
                        'terminate_recommendation': rec.get('TerminateRecommendationDetail', {})
                    }
                    cost_data['rightsizing_recommendations'].append(recommendation)
                
            except ClientError as e:
                logger.warning(f"Failed to get rightsizing recommendations: {e}")
            
            # Get Reserved Instance recommendations
            try:
                ri_response = ce_client.get_reservation_purchase_recommendation(
                    Service='AmazonEC2',
                    LookbackPeriodInDays='SIXTY_DAYS',
                    TermInYears='ONE_YEAR',
                    PaymentOption='NO_UPFRONT'
                )
                
                cost_data['reserved_instance_recommendations'] = ri_response.get('Recommendations', [])
                
            except ClientError as e:
                logger.warning(f"Failed to get RI recommendations: {e}")
            
            # Get Savings Plans recommendations
            try:
                sp_response = ce_client.get_savings_plans_purchase_recommendation(
                    SavingsPlansType='COMPUTE_SP',
                    LookbackPeriodInDays='SIXTY_DAYS',
                    TermInYears='ONE_YEAR',
                    PaymentOption='NO_UPFRONT'
                )
                
                cost_data['savings_plans_recommendations'] = sp_response.get('SavingsPlansEstimatedMonthlySavings', {})
                
            except ClientError as e:
                logger.warning(f"Failed to get Savings Plans recommendations: {e}")
            
            # Calculate service-specific metrics
            self._calculate_cost_metrics(cost_data)
            
        except ClientError as e:
            logger.error(f"Failed to collect Cost Explorer data: {e}")
        
        return cost_data
    
    def _calculate_cost_metrics(self, cost_data):
        """Calculate additional cost metrics and trends."""
        try:
            # Calculate total monthly spend by service
            service_totals = {}
            for month_data in cost_data['monthly_costs'].values():
                for service, data in month_data.items():
                    if service not in service_totals:
                        service_totals[service] = 0
                    service_totals[service] += data['amount']
            
            cost_data['service_totals'] = dict(sorted(service_totals.items(), 
                                                    key=lambda x: x[1], reverse=True))
            
            # Calculate daily trend (last 7 days vs previous 7 days)
            if len(cost_data['daily_costs']) >= 14:
                recent_costs = cost_data['daily_costs'][-7:]
                previous_costs = cost_data['daily_costs'][-14:-7]
                
                recent_avg = sum(day['total_cost'] for day in recent_costs) / 7
                previous_avg = sum(day['total_cost'] for day in previous_costs) / 7
                
                if previous_avg > 0:
                    trend_percentage = ((recent_avg - previous_avg) / previous_avg) * 100
                    cost_data['cost_trend'] = {
                        'recent_daily_average': recent_avg,
                        'previous_daily_average': previous_avg,
                        'trend_percentage': trend_percentage,
                        'trend_direction': 'increasing' if trend_percentage > 5 else 'decreasing' if trend_percentage < -5 else 'stable'
                    }
            
        except Exception as e:
            logger.warning(f"Failed to calculate cost metrics: {e}")

    def collect_cost_optimization_hub_data(self):
        """Collect recommendations from AWS Cost Optimization Hub."""
        optimization_data = {
            'recommendations': [],
            'summary': {},
            'enrollment_status': 'unknown'
        }
        
        try:
            # Cost Optimization Hub uses the cost-optimization-hub service
            coh_client = self.session.client('cost-optimization-hub', region_name='us-east-1')
            
            logger.info("Collecting Cost Optimization Hub recommendations...")
            
            # Check enrollment status
            try:
                enrollment_status = coh_client.get_enrollment_status()
                optimization_data['enrollment_status'] = enrollment_status.get('status', 'unknown')
                
                if enrollment_status.get('status') == 'Active':
                    logger.info("Cost Optimization Hub is active, collecting recommendations...")
                    
                    # Get recommendations with pagination
                    paginator = coh_client.get_paginator('list_recommendations')
                    
                    # Define filters for our target services
                    filters = [
                        {
                            'restartNeeded': False,
                            'rollbackPossible': True
                        }
                    ]
                    
                    recommendation_count = 0
                    total_estimated_savings = 0
                    
                    for page in paginator.paginate(
                        filter={
                            'resourceTypes': [
                                'Ec2Instance',
                                'EbsVolume', 
                                'EcsService',
                                'RdsDbInstance',
                                'LambdaFunction',
                                'ElastiCacheReplicationGroup'
                            ],
                            'actionTypes': [
                                'Rightsize',
                                'Stop',
                                'Upgrade',
                                'PurchaseSavingsPlans',
                                'PurchaseReservedInstances'
                            ]
                        }
                    ):
                        for recommendation in page.get('items', []):
                            rec_data = {
                                'recommendation_id': recommendation.get('recommendationId', ''),
                                'resource_id': recommendation.get('resourceId', ''),
                                'resource_arn': recommendation.get('resourceArn', ''),
                                'resource_type': recommendation.get('resourceType', ''),
                                'action_type': recommendation.get('actionType', ''),
                                'source': recommendation.get('source', ''),
                                'region': recommendation.get('region', ''),
                                'account_id': recommendation.get('accountId', ''),
                                'currency_code': recommendation.get('currencyCode', 'USD'),
                                'current_monthly_cost': float(recommendation.get('currentMonthlyNet', 0)),
                                'estimated_monthly_cost': float(recommendation.get('estimatedMonthlyNet', 0)),
                                'estimated_monthly_savings': float(recommendation.get('estimatedMonthlySavings', 0)),
                                'implementation_effort': recommendation.get('implementationEffort', 'Unknown'),
                                'last_refresh_timestamp': recommendation.get('lastRefreshTimestamp', ''),
                                'rollback_possible': recommendation.get('rollbackPossible', False),
                                'restart_needed': recommendation.get('restartNeeded', False),
                                'tags': recommendation.get('tags', {}),
                                'recommendation_lookback_period': recommendation.get('recommendationLookbackPeriod', 0)
                            }
                            
                            # Get detailed recommendation information
                            try:
                                details = coh_client.get_recommendation(
                                    recommendationId=recommendation.get('recommendationId', '')
                                )
                                
                                rec_data['details'] = {
                                    'description': details.get('recommendationId', ''),
                                    'implementation_effort': details.get('implementationEffort', 'Unknown'),
                                    'action_type_description': details.get('actionType', ''),
                                    'resource_details': details.get('resourceDetails', {}),
                                    'estimated_savings_percentage': (
                                        (rec_data['estimated_monthly_savings'] / rec_data['current_monthly_cost'] * 100)
                                        if rec_data['current_monthly_cost'] > 0 else 0
                                    )
                                }
                                
                            except ClientError as e:
                                logger.warning(f"Failed to get recommendation details for {recommendation.get('recommendationId', '')}: {e}")
                                rec_data['details'] = {}
                            
                            optimization_data['recommendations'].append(rec_data)
                            recommendation_count += 1
                            total_estimated_savings += rec_data['estimated_monthly_savings']
                    
                    # Create summary
                    optimization_data['summary'] = {
                        'total_recommendations': recommendation_count,
                        'total_estimated_monthly_savings': total_estimated_savings,
                        'recommendations_by_type': {},
                        'recommendations_by_effort': {},
                        'high_impact_recommendations': 0
                    }
                    
                    # Group recommendations by type and effort
                    for rec in optimization_data['recommendations']:
                        action_type = rec['action_type']
                        effort = rec['implementation_effort']
                        
                        if action_type not in optimization_data['summary']['recommendations_by_type']:
                            optimization_data['summary']['recommendations_by_type'][action_type] = 0
                        optimization_data['summary']['recommendations_by_type'][action_type] += 1
                        
                        if effort not in optimization_data['summary']['recommendations_by_effort']:
                            optimization_data['summary']['recommendations_by_effort'][effort] = 0
                        optimization_data['summary']['recommendations_by_effort'][effort] += 1
                        
                        # Count high-impact recommendations (>$10/month savings)
                        if rec['estimated_monthly_savings'] > 10:
                            optimization_data['summary']['high_impact_recommendations'] += 1
                    
                    logger.info(f"Collected {recommendation_count} Cost Optimization Hub recommendations with ${total_estimated_savings:.2f} estimated monthly savings")
                
                else:
                    logger.info(f"Cost Optimization Hub status: {enrollment_status.get('status', 'unknown')}")
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    logger.warning("Cost Optimization Hub access denied - may not be enrolled or lack permissions")
                    optimization_data['enrollment_status'] = 'access_denied'
                else:
                    logger.warning(f"Failed to check Cost Optimization Hub enrollment: {e}")
        
        except ClientError as e:
            if 'cost-optimization-hub' in str(e) and 'not available' in str(e):
                logger.info("Cost Optimization Hub service not available in this region")
                optimization_data['enrollment_status'] = 'service_unavailable'
            else:
                logger.warning(f"Cost Optimization Hub error: {e}")
        
        return optimization_data

    def generate_cost_report(self, environment='dev'):
        """Generate comprehensive cost optimization report."""
        logger.info("Starting AWS cost data collection...")
        
        report_data = {
            'account_id': self.account_id,
            'region': self.region,
            'environment': environment,
            'collection_timestamp': datetime.now().isoformat(),
            'storage': self.collect_storage_data(),
            'compute': self.collect_compute_data(),
            'logs': self.collect_log_data(),
            'network': self.collect_network_data(),
            'macie': self.collect_macie_data(),
            'cost_analysis': self.collect_cost_explorer_data(days_back=getattr(self, 'cost_days', 30)),
            'cost_optimization_hub': self.collect_cost_optimization_hub_data()
        }
        
        # Save to JSON file
        output_dir = 'output'
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{output_dir}/aws_cost_data_{environment}_{self.account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"Cost data report saved to: {filename}")
        return filename

def main():
    parser = argparse.ArgumentParser(description='AWS Cost Optimization Data Collector')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--environment', choices=['dev', 'prod'], default='dev', 
                       help='Environment type (default: dev)')
    parser.add_argument('--cost-days', type=int, default=30, 
                       help='Number of days back to analyze costs (default: 30)')
    
    args = parser.parse_args()
    
    try:
        collector = AWSCostDataCollector(profile_name=args.profile, region=args.region)
        # Set cost analysis period
        collector.cost_days = args.cost_days
        report_file = collector.generate_cost_report(environment=args.environment)
        print(f"AWS cost data collection completed. Report saved to: {report_file}")
        
    except Exception as e:
        logger.error(f"Failed to collect AWS cost data: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())