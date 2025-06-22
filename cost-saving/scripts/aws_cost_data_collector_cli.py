#!/usr/bin/env python3
"""
AWS Cost Optimization Data Collector (CLI Hybrid Version)

This script collects AWS resource information for cost optimization analysis
using AWS CLI commands instead of boto3 to avoid version compatibility issues.
"""

import json
import csv
import os
import subprocess
import logging
from datetime import datetime, timedelta
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSCostDataCollectorCLI:
    def __init__(self, profile_name=None, region='us-east-1'):
        """Initialize AWS CLI environment with specified profile and region."""
        self.profile_name = profile_name
        self.region = region
        self.aws_cmd_base = ['aws']
        
        if profile_name:
            self.aws_cmd_base.extend(['--profile', profile_name])
        
        self.aws_cmd_base.extend(['--region', region, '--output', 'json'])
        
        # Test AWS CLI connectivity
        try:
            self.account_id = self._run_aws_command(['sts', 'get-caller-identity'])['Account']
            logger.info(f"Connected to AWS Account: {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to connect to AWS: {e}")
            raise

    def _run_aws_command(self, command_parts, ignore_errors=False):
        """Execute AWS CLI command and return parsed JSON result."""
        cmd = self.aws_cmd_base + command_parts
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=not ignore_errors,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode != 0 and not ignore_errors:
                logger.warning(f"AWS CLI command failed: {' '.join(cmd)}")
                logger.warning(f"Error: {result.stderr}")
                return {}
            
            if result.stdout.strip():
                return json.loads(result.stdout)
            else:
                return {}
                
        except subprocess.TimeoutExpired:
            logger.error(f"AWS CLI command timed out: {' '.join(cmd)}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from AWS CLI: {e}")
            logger.error(f"Output was: {result.stdout}")
            return {}
        except Exception as e:
            logger.error(f"Error running AWS CLI command: {e}")
            return {}

    def collect_storage_data(self):
        """Collect S3, EBS, and EFS storage information using AWS CLI."""
        storage_data = {
            's3_buckets': [],
            'ebs_volumes': [],
            'ebs_snapshots': [],
            'efs_filesystems': []
        }
        
        # S3 Buckets
        try:
            logger.info("Collecting S3 bucket data...")
            buckets_response = self._run_aws_command(['s3api', 'list-buckets'])
            
            for bucket in buckets_response.get('Buckets', []):
                bucket_info = {
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'],
                }
                
                # Get bucket location
                try:
                    location_response = self._run_aws_command([
                        's3api', 'get-bucket-location', '--bucket', bucket['Name']
                    ], ignore_errors=True)
                    bucket_info['region'] = location_response.get('LocationConstraint') or 'us-east-1'
                except:
                    bucket_info['region'] = 'unknown'
                
                # Get object count (sample)
                try:
                    objects_response = self._run_aws_command([
                        's3api', 'list-objects-v2', '--bucket', bucket['Name'], '--max-items', '1000'
                    ], ignore_errors=True)
                    bucket_info['object_count'] = objects_response.get('KeyCount', 0)
                except:
                    bucket_info['object_count'] = 'Access Denied'
                
                storage_data['s3_buckets'].append(bucket_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect S3 data: {e}")

        # EBS Volumes
        try:
            logger.info("Collecting EBS volume data...")
            volumes_response = self._run_aws_command(['ec2', 'describe-volumes'])
            
            for volume in volumes_response.get('Volumes', []):
                volume_info = {
                    'volume_id': volume['VolumeId'],
                    'size': volume['Size'],
                    'volume_type': volume['VolumeType'],
                    'state': volume['State'],
                    'availability_zone': volume['AvailabilityZone'],
                    'encrypted': volume['Encrypted'],
                    'attachments': len(volume.get('Attachments', [])),
                    'creation_date': volume['CreateTime']
                }
                storage_data['ebs_volumes'].append(volume_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect EBS volume data: {e}")

        # EBS Snapshots
        try:
            logger.info("Collecting EBS snapshot data...")
            snapshots_response = self._run_aws_command([
                'ec2', 'describe-snapshots', '--owner-ids', self.account_id
            ])
            
            for snapshot in snapshots_response.get('Snapshots', []):
                snapshot_info = {
                    'snapshot_id': snapshot['SnapshotId'],
                    'volume_id': snapshot.get('VolumeId', 'N/A'),
                    'size': snapshot['VolumeSize'],
                    'state': snapshot['State'],
                    'start_time': snapshot['StartTime'],
                    'description': snapshot.get('Description', '')
                }
                storage_data['ebs_snapshots'].append(snapshot_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect EBS snapshot data: {e}")

        # EFS File Systems
        try:
            logger.info("Collecting EFS data...")
            efs_response = self._run_aws_command(['efs', 'describe-file-systems'])
            
            for fs in efs_response.get('FileSystems', []):
                fs_info = {
                    'file_system_id': fs['FileSystemId'],
                    'name': fs.get('Name', ''),
                    'size_in_bytes': fs['SizeInBytes']['Value'],
                    'performance_mode': fs['PerformanceMode'],
                    'throughput_mode': fs['ThroughputMode'],
                    'creation_date': fs['CreationTime']
                }
                storage_data['efs_filesystems'].append(fs_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect EFS data: {e}")

        return storage_data

    def collect_compute_data(self):
        """Collect EC2, Lambda, and RDS compute resource information using AWS CLI."""
        compute_data = {
            'ec2_instances': [],
            'lambda_functions': [],
            'rds_instances': []
        }
        
        # EC2 Instances
        try:
            logger.info("Collecting EC2 instance data...")
            instances_response = self._run_aws_command(['ec2', 'describe-instances'])
            
            for reservation in instances_response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_info = {
                        'instance_id': instance['InstanceId'],
                        'instance_type': instance['InstanceType'],
                        'state': instance['State']['Name'],
                        'launch_time': instance.get('LaunchTime', ''),
                        'availability_zone': instance['Placement']['AvailabilityZone'],
                        'platform': instance.get('Platform', 'Linux'),
                        'monitoring': instance['Monitoring']['State']
                    }
                    compute_data['ec2_instances'].append(instance_info)
                    
        except Exception as e:
            logger.warning(f"Failed to collect EC2 data: {e}")

        # Lambda Functions
        try:
            logger.info("Collecting Lambda function data...")
            functions_response = self._run_aws_command(['lambda', 'list-functions'])
            
            for func in functions_response.get('Functions', []):
                func_info = {
                    'function_name': func['FunctionName'],
                    'runtime': func['Runtime'],
                    'memory_size': func['MemorySize'],
                    'timeout': func['Timeout'],
                    'last_modified': func['LastModified']
                }
                compute_data['lambda_functions'].append(func_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect Lambda data: {e}")

        # RDS Instances
        try:
            logger.info("Collecting RDS instance data...")
            rds_response = self._run_aws_command(['rds', 'describe-db-instances'])
            
            for instance in rds_response.get('DBInstances', []):
                instance_info = {
                    'db_instance_identifier': instance['DBInstanceIdentifier'],
                    'db_instance_class': instance['DBInstanceClass'],
                    'engine': instance['Engine'],
                    'engine_version': instance['EngineVersion'],
                    'allocated_storage': instance['AllocatedStorage'],
                    'storage_type': instance['StorageType'],
                    'multi_az': instance['MultiAZ'],
                    'availability_zone': instance.get('AvailabilityZone', ''),
                    'instance_create_time': instance['InstanceCreateTime']
                }
                compute_data['rds_instances'].append(instance_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect RDS data: {e}")

        return compute_data

    def collect_log_data(self):
        """Collect CloudWatch Logs information using AWS CLI."""
        log_data = {
            'log_groups': []
        }
        
        try:
            logger.info("Collecting CloudWatch Logs data...")
            logs_response = self._run_aws_command(['logs', 'describe-log-groups'])
            
            for log_group in logs_response.get('logGroups', []):
                group_info = {
                    'log_group_name': log_group['logGroupName'],
                    'retention_in_days': log_group.get('retentionInDays', 'Never Expire'),
                    'stored_bytes': log_group.get('storedBytes', 0),
                    'creation_time': log_group.get('creationTime', 0)
                }
                
                # Convert creation time from epoch to ISO format
                if isinstance(group_info['creation_time'], (int, float)) and group_info['creation_time'] > 0:
                    group_info['creation_time'] = datetime.fromtimestamp(
                        group_info['creation_time'] / 1000
                    ).isoformat()
                
                log_data['log_groups'].append(group_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect CloudWatch Logs data: {e}")

        return log_data

    def collect_network_data(self):
        """Collect network-related cost information using AWS CLI."""
        network_data = {
            'nat_gateways': [],
            'load_balancers': [],
            'vpc_endpoints': []
        }
        
        try:
            # NAT Gateways
            logger.info("Collecting NAT Gateway data...")
            nat_response = self._run_aws_command(['ec2', 'describe-nat-gateways'])
            
            for nat in nat_response.get('NatGateways', []):
                nat_info = {
                    'nat_gateway_id': nat['NatGatewayId'],
                    'state': nat['State'],
                    'subnet_id': nat['SubnetId'],
                    'vpc_id': nat['VpcId'],
                    'create_time': nat['CreateTime']
                }
                network_data['nat_gateways'].append(nat_info)
            
            # VPC Endpoints
            logger.info("Collecting VPC Endpoint data...")
            endpoints_response = self._run_aws_command(['ec2', 'describe-vpc-endpoints'])
            
            for endpoint in endpoints_response.get('VpcEndpoints', []):
                endpoint_info = {
                    'vpc_endpoint_id': endpoint['VpcEndpointId'],
                    'vpc_endpoint_type': endpoint['VpcEndpointType'],
                    'service_name': endpoint['ServiceName'],
                    'state': endpoint['State'],
                    'creation_timestamp': endpoint['CreationTimestamp']
                }
                network_data['vpc_endpoints'].append(endpoint_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect network data: {e}")

        # Load Balancers
        try:
            logger.info("Collecting Load Balancer data...")
            lb_response = self._run_aws_command(['elbv2', 'describe-load-balancers'])
            
            for lb in lb_response.get('LoadBalancers', []):
                lb_info = {
                    'load_balancer_arn': lb['LoadBalancerArn'],
                    'load_balancer_name': lb['LoadBalancerName'],
                    'type': lb['Type'],
                    'scheme': lb['Scheme'],
                    'state': lb['State']['Code'],
                    'created_time': lb['CreatedTime']
                }
                network_data['load_balancers'].append(lb_info)
                
        except Exception as e:
            logger.warning(f"Failed to collect load balancer data: {e}")

        return network_data

    def collect_macie_data(self):
        """Collect Amazon Macie information using AWS CLI."""
        macie_data = {
            'macie_status': 'Not Available',
            'data_discovery_jobs': [],
            'findings': []
        }
        
        try:
            logger.info("Collecting Macie data...")
            
            # Check Macie status
            try:
                status_response = self._run_aws_command(['macie2', 'get-macie-session'], ignore_errors=True)
                
                if status_response and 'status' in status_response:
                    macie_data['macie_status'] = status_response['status']
                    macie_data['service_role'] = status_response.get('serviceRole', '')
                    macie_data['created_at'] = status_response.get('createdAt', '')
                    
                    # Get discovery jobs if Macie is enabled
                    if status_response['status'] == 'ENABLED':
                        jobs_response = self._run_aws_command([
                            'macie2', 'list-classification-jobs'
                        ], ignore_errors=True)
                        
                        for job in jobs_response.get('items', []):
                            job_info = {
                                'job_id': job['jobId'],
                                'job_type': job['jobType'],
                                'job_status': job['jobStatus'],
                                'name': job.get('name', ''),
                                'created_at': job['createdAt']
                            }
                            macie_data['data_discovery_jobs'].append(job_info)
                else:
                    macie_data['macie_status'] = 'DISABLED'
                    
            except Exception as e:
                logger.warning(f"Failed to get Macie status: {e}")
                macie_data['macie_status'] = 'DISABLED'
                    
        except Exception as e:
            logger.warning(f"Macie service error: {e}")

        return macie_data

    def collect_cost_explorer_data(self, days_back=30):
        """Collect cost data from AWS Cost Explorer using AWS CLI."""
        cost_data = {
            'monthly_costs': {},
            'service_costs': {},
            'daily_costs': [],
            'rightsizing_recommendations': []
        }
        
        try:
            logger.info("Collecting Cost Explorer data...")
            
            # Define time period
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            start_str = start_date.strftime('%Y-%m-%d')
            end_str = end_date.strftime('%Y-%m-%d')
            
            # Get monthly costs by service
            try:
                monthly_costs_cmd = [
                    'ce', 'get-cost-and-usage',
                    '--time-period', f'Start={start_str},End={end_str}',
                    '--granularity', 'MONTHLY',
                    '--metrics', 'BlendedCost', 'UsageQuantity',
                    '--group-by', 'Type=DIMENSION,Key=SERVICE'
                ]
                
                monthly_response = self._run_aws_command(monthly_costs_cmd, ignore_errors=True)
                
                for result in monthly_response.get('ResultsByTime', []):
                    month = result['TimePeriod']['Start']
                    cost_data['monthly_costs'][month] = {}
                    
                    for group in result.get('Groups', []):
                        service_name = group['Keys'][0]
                        amount = float(group['Metrics']['BlendedCost']['Amount'])
                        unit = group['Metrics']['BlendedCost']['Unit']
                        
                        if amount > 0:
                            cost_data['monthly_costs'][month][service_name] = {
                                'amount': amount,
                                'unit': unit,
                                'usage_quantity': float(group['Metrics']['UsageQuantity']['Amount'])
                            }
                
            except Exception as e:
                logger.warning(f"Failed to get monthly cost data: {e}")
            
            # Get rightsizing recommendations
            try:
                rightsizing_cmd = [
                    'ce', 'get-rightsizing-recommendation',
                    '--service', 'AmazonEC2',
                    '--configuration', 'BenefitsConsidered=true,RecommendationTarget=SAME_INSTANCE_FAMILY'
                ]
                
                rightsizing_response = self._run_aws_command(rightsizing_cmd, ignore_errors=True)
                
                for rec in rightsizing_response.get('RightsizingRecommendations', []):
                    recommendation = {
                        'account_id': rec.get('AccountId', ''),
                        'current_instance': rec.get('CurrentInstance', {}),
                        'rightsizing_type': rec.get('RightsizingType', ''),
                        'modify_recommendation': rec.get('ModifyRecommendationDetail', {}),
                        'terminate_recommendation': rec.get('TerminateRecommendationDetail', {})
                    }
                    cost_data['rightsizing_recommendations'].append(recommendation)
                
            except Exception as e:
                logger.warning(f"Failed to get rightsizing recommendations: {e}")
            
            # Calculate service-specific metrics
            self._calculate_cost_metrics(cost_data)
            
        except Exception as e:
            logger.warning(f"Failed to collect Cost Explorer data: {e}")
        
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
            
        except Exception as e:
            logger.warning(f"Failed to calculate cost metrics: {e}")

    def collect_cost_optimization_hub_data(self):
        """Collect recommendations from AWS Cost Optimization Hub using AWS CLI."""
        optimization_data = {
            'recommendations': [],
            'summary': {},
            'enrollment_status': 'unknown'
        }
        
        try:
            logger.info("Collecting Cost Optimization Hub data...")
            
            # Check enrollment status
            try:
                enrollment_cmd = ['cost-optimization-hub', 'get-enrollment-status']
                enrollment_response = self._run_aws_command(enrollment_cmd, ignore_errors=True)
                
                if enrollment_response and 'status' in enrollment_response:
                    optimization_data['enrollment_status'] = enrollment_response['status']
                    
                    if enrollment_response['status'] == 'Active':
                        logger.info("Cost Optimization Hub is active, collecting recommendations...")
                        
                        # Get recommendations
                        recommendations_cmd = [
                            'cost-optimization-hub', 'list-recommendations',
                            '--filter', json.dumps({
                                'resourceTypes': [
                                    'Ec2Instance', 'EbsVolume', 'EcsService',
                                    'RdsDbInstance', 'LambdaFunction', 'ElastiCacheReplicationGroup'
                                ],
                                'actionTypes': [
                                    'Rightsize', 'Stop', 'Upgrade',
                                    'PurchaseSavingsPlans', 'PurchaseReservedInstances'
                                ]
                            })
                        ]
                        
                        recommendations_response = self._run_aws_command(recommendations_cmd, ignore_errors=True)
                        
                        recommendation_count = 0
                        total_estimated_savings = 0
                        
                        for recommendation in recommendations_response.get('items', []):
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
                        
                        logger.info(f"Collected {recommendation_count} Cost Optimization Hub recommendations")
                    
                    else:
                        logger.info(f"Cost Optimization Hub status: {enrollment_response['status']}")
                else:
                    optimization_data['enrollment_status'] = 'service_unavailable'
                    
            except Exception as e:
                logger.warning(f"Failed to check Cost Optimization Hub enrollment: {e}")
                optimization_data['enrollment_status'] = 'access_denied'
        
        except Exception as e:
            logger.warning(f"Cost Optimization Hub error: {e}")
        
        return optimization_data

    def generate_cost_report(self, environment='dev'):
        """Generate comprehensive cost optimization report using AWS CLI."""
        logger.info("Starting AWS cost data collection with CLI...")
        
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
        
        # Custom JSON encoder to handle datetime objects
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return str(obj)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=json_serializer)
        
        logger.info(f"Cost data report saved to: {filename}")
        return filename

def main():
    parser = argparse.ArgumentParser(description='AWS Cost Optimization Data Collector (CLI Version)')
    parser.add_argument('--profile', help='AWS profile name')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--environment', choices=['dev', 'prod'], default='dev', 
                       help='Environment type (default: dev)')
    parser.add_argument('--cost-days', type=int, default=30, 
                       help='Number of days back to analyze costs (default: 30)')
    
    args = parser.parse_args()
    
    try:
        collector = AWSCostDataCollectorCLI(profile_name=args.profile, region=args.region)
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