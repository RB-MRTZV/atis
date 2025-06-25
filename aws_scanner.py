#!/usr/bin/env python3
import boto3
import json
import sys
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AWSResourceScanner:
    def __init__(self, region='ap-southeast-2'):
        self.region = region
        self.ec2_client = None
        self.rds_client = None
        self.eks_client = None
        self.asg_client = None
        self.account_id = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        try:
            self.ec2_client = boto3.client('ec2', region_name=self.region)
            self.rds_client = boto3.client('rds', region_name=self.region)
            self.eks_client = boto3.client('eks', region_name=self.region)
            self.asg_client = boto3.client('autoscaling', region_name=self.region)
            
            sts_client = boto3.client('sts')
            self.account_id = sts_client.get_caller_identity()['Account']
            logger.info(f"Successfully authenticated for AWS account: {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to initialize AWS clients: {str(e)}")
            logger.error("Please ensure AWS credentials are properly configured")
            sys.exit(1)
    
    def _get_tag_value(self, tags, key):
        """Extract tag value from tags list"""
        if not tags:
            return None
        for tag in tags:
            if tag.get('Key') == key:
                return tag.get('Value')
        return None
    
    def scan_ec2_instances(self):
        """Scan EC2 instances and return structured data"""
        logger.info("Scanning EC2 instances...")
        instances = []
        
        try:
            paginator = self.ec2_client.get_paginator('describe_instances')
            
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        if instance['State']['Name'] != 'running':
                            continue
                        
                        tags = instance.get('Tags', [])
                        environment = self._get_tag_value(tags, 'environment') or 'unknown'
                        
                        # Check if instance is in ASG
                        in_asg = False
                        asg_name = None
                        try:
                            asg_response = self.asg_client.describe_auto_scaling_instances(
                                InstanceIds=[instance['InstanceId']]
                            )
                            if asg_response['AutoScalingInstances']:
                                in_asg = True
                                asg_name = asg_response['AutoScalingInstances'][0]['AutoScalingGroupName']
                        except:
                            pass
                        
                        # Determine instance type based on ASG membership and naming
                        instance_name = self._get_tag_value(tags, 'Name') or ''
                        if in_asg and asg_name:
                            # Check if ASG name or instance name contains 'eks' (case-insensitive)
                            if 'eks' in asg_name.lower() or 'eks' in instance_name.lower():
                                instance_type_classification = 'EKS Managed Node'
                                is_ephemeral = False
                            else:
                                instance_type_classification = 'Ephemeral'
                                is_ephemeral = True
                        else:
                            # Not in ASG - default to Managed
                            instance_type_classification = 'Managed'
                            is_ephemeral = False
                        
                        instance_data = {
                            'instance_id': instance['InstanceId'],
                            'instance_type': instance['InstanceType'],
                            'environment': environment,
                            'is_ephemeral': is_ephemeral,
                            'type': instance_type_classification,
                            'in_asg': in_asg,
                            'asg_name': asg_name,
                            'availability_zone': instance['Placement']['AvailabilityZone'],
                            'launch_time': instance['LaunchTime'].isoformat(),
                            'tags': {tag['Key']: tag['Value'] for tag in tags}
                        }
                        instances.append(instance_data)
            
            logger.info(f"Found {len(instances)} running EC2 instances")
            return instances
            
        except Exception as e:
            logger.error(f"Error scanning EC2 instances: {str(e)}")
            return []
    
    def scan_rds_clusters(self):
        """Scan RDS clusters and instances"""
        logger.info("Scanning RDS clusters...")
        rds_resources = []
        
        try:
            # Scan RDS clusters
            paginator = self.rds_client.get_paginator('describe_db_clusters')
            
            for page in paginator.paginate():
                for cluster in page['DBClusters']:
                    if cluster['Status'] != 'available':
                        continue
                    
                    tags_response = self.rds_client.list_tags_for_resource(
                        ResourceName=cluster['DBClusterArn']
                    )
                    tags = tags_response.get('TagList', [])
                    environment = self._get_tag_value(tags, 'environment') or 'unknown'
                    
                    cluster_data = {
                        'cluster_id': cluster['DBClusterIdentifier'],
                        'engine': cluster['Engine'],
                        'engine_version': cluster['EngineVersion'],
                        'multi_az': cluster.get('MultiAZ', False),
                        'environment': environment,
                        'status': cluster['Status'],
                        'instance_count': len(cluster.get('DBClusterMembers', [])),
                        'tags': {tag['Key']: tag['Value'] for tag in tags}
                    }
                    
                    # Get instance details for the cluster
                    for member in cluster.get('DBClusterMembers', []):
                        instance_response = self.rds_client.describe_db_instances(
                            DBInstanceIdentifier=member['DBInstanceIdentifier']
                        )
                        
                        if instance_response['DBInstances']:
                            instance = instance_response['DBInstances'][0]
                            instance_data = {
                                **cluster_data,
                                'instance_id': instance['DBInstanceIdentifier'],
                                'instance_class': instance['DBInstanceClass'],
                                'storage_type': instance.get('StorageType', 'unknown'),
                                'allocated_storage': instance.get('AllocatedStorage', 0),
                                'iops': instance.get('Iops', 0),
                                'is_writer': member['IsClusterWriter']
                            }
                            rds_resources.append(instance_data)
            
            # Also scan standalone RDS instances
            paginator = self.rds_client.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    if instance['DBInstanceStatus'] != 'available':
                        continue
                    
                    # Skip if already part of a cluster
                    if instance.get('DBClusterIdentifier'):
                        continue
                    
                    tags_response = self.rds_client.list_tags_for_resource(
                        ResourceName=instance['DBInstanceArn']
                    )
                    tags = tags_response.get('TagList', [])
                    environment = self._get_tag_value(tags, 'environment') or 'unknown'
                    
                    instance_data = {
                        'instance_id': instance['DBInstanceIdentifier'],
                        'instance_class': instance['DBInstanceClass'],
                        'engine': instance['Engine'],
                        'engine_version': instance['EngineVersion'],
                        'multi_az': instance.get('MultiAZ', False),
                        'environment': environment,
                        'storage_type': instance.get('StorageType', 'unknown'),
                        'allocated_storage': instance.get('AllocatedStorage', 0),
                        'iops': instance.get('Iops', 0),
                        'tags': {tag['Key']: tag['Value'] for tag in tags}
                    }
                    rds_resources.append(instance_data)
            
            logger.info(f"Found {len(rds_resources)} RDS instances")
            return rds_resources
            
        except Exception as e:
            logger.error(f"Error scanning RDS resources: {str(e)}")
            return []
    
    def scan_eks_clusters(self):
        """Scan EKS clusters and node groups"""
        logger.info("Scanning EKS clusters...")
        eks_resources = []
        
        try:
            clusters = self.eks_client.list_clusters()
            
            for cluster_name in clusters.get('clusters', []):
                cluster_response = self.eks_client.describe_cluster(name=cluster_name)
                cluster = cluster_response['cluster']
                
                if cluster['status'] != 'ACTIVE':
                    continue
                
                environment = cluster.get('tags', {}).get('environment', 'unknown')
                
                # Get node groups
                nodegroups_response = self.eks_client.list_nodegroups(clusterName=cluster_name)
                
                cluster_data = {
                    'cluster_name': cluster_name,
                    'version': cluster['version'],
                    'environment': environment,
                    'endpoint': cluster['endpoint'],
                    'node_groups': []
                }
                
                # Get Kubernetes deployments count if possible
                deployment_count = self._get_k8s_deployments(cluster)
                cluster_data['deployment_count'] = deployment_count
                
                for nodegroup_name in nodegroups_response.get('nodegroups', []):
                    nodegroup_response = self.eks_client.describe_nodegroup(
                        clusterName=cluster_name,
                        nodegroupName=nodegroup_name
                    )
                    nodegroup = nodegroup_response['nodegroup']
                    
                    if nodegroup['status'] != 'ACTIVE':
                        continue
                    
                    nodegroup_data = {
                        'nodegroup_name': nodegroup_name,
                        'instance_types': nodegroup.get('instanceTypes', []),
                        'desired_size': nodegroup['scalingConfig']['desiredSize'],
                        'min_size': nodegroup['scalingConfig']['minSize'],
                        'max_size': nodegroup['scalingConfig']['maxSize'],
                        'disk_size': nodegroup.get('diskSize', 0),
                        'ami_type': nodegroup.get('amiType', 'unknown'),
                        'capacity_type': nodegroup.get('capacityType', 'ON_DEMAND')
                    }
                    
                    cluster_data['node_groups'].append(nodegroup_data)
                    
                    # Create individual node entries for cost calculation
                    for instance_type in nodegroup.get('instanceTypes', []):
                        for i in range(nodegroup['scalingConfig']['desiredSize']):
                            node_data = {
                                'cluster_name': cluster_name,
                                'nodegroup_name': nodegroup_name,
                                'instance_type': instance_type,
                                'environment': environment,
                                'capacity_type': nodegroup.get('capacityType', 'ON_DEMAND'),
                                'deployment_count': deployment_count
                            }
                            eks_resources.append(node_data)
                
            logger.info(f"Found {len(eks_resources)} EKS nodes")
            return eks_resources
            
        except Exception as e:
            logger.error(f"Error scanning EKS resources: {str(e)}")
            return []
    
    def _get_k8s_deployments(self, cluster):
        """Try to get Kubernetes deployment count - simplified version"""
        # This would require kubectl access which might not be available
        # Returning placeholder for now
        return "N/A"
    
    def scan_all_resources(self):
        """Scan all AWS resources"""
        logger.info(f"Starting AWS resource scan for account {self.account_id} in region {self.region}")
        
        resources = {
            'account_id': self.account_id,
            'region': self.region,
            'scan_time': datetime.utcnow().isoformat(),
            'ec2_instances': self.scan_ec2_instances(),
            'rds_instances': self.scan_rds_clusters(),
            'eks_nodes': self.scan_eks_clusters()
        }
        
        # Save raw scan results
        with open('aws_scan_results.json', 'w') as f:
            json.dump(resources, f, indent=2, default=str)
        
        logger.info("Scan complete. Results saved to aws_scan_results.json")
        return resources

if __name__ == "__main__":
    scanner = AWSResourceScanner()
    scan_results = scanner.scan_all_resources()