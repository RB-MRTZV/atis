import boto3
import logging
import time
import botocore.exceptions
from datetime import datetime

class RDSOperationError(Exception):
    """Exception raised for RDS operation errors."""
    pass

class RDSOperations:
    """Handles RDS and Aurora cluster operations."""
    
    def __init__(self, region, dry_run=False):
        """Initialize RDS operations.
        
        Args:
            region (str): AWS region
            dry_run (bool): Whether to run in dry-run mode
        """
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.dry_run = dry_run
        self.rds_client = boto3.client('rds', region_name=region)
        
        if self.dry_run:
            self.logger.info("RDS Operations initialized in DRY RUN mode - no actual changes will be made")

    def find_tagged_clusters(self, tag_key, tag_value):
        """Find Aurora clusters with the specified tag.
        
        Args:
            tag_key (str): Tag key to filter on
            tag_value (str): Tag value to filter on
            
        Returns:
            list: List of cluster dictionaries
        """
        try:
            self.logger.info(f"Finding Aurora clusters with tag {tag_key}:{tag_value}")
            
            if self.dry_run:
                self.logger.info("[DRY RUN] Would search for tagged Aurora clusters")
                return [{
                    'DBClusterIdentifier': 'mock-aurora-cluster-1',
                    'DBClusterArn': 'arn:aws:rds:region:account:cluster:mock-aurora-cluster-1',
                    'Status': 'available',
                    'Engine': 'aurora-postgresql',
                    'DBClusterMembers': [
                        {'DBInstanceIdentifier': 'mock-instance-1', 'IsClusterWriter': True},
                        {'DBInstanceIdentifier': 'mock-instance-2', 'IsClusterWriter': False}
                    ]
                }]
            
            clusters = []
            paginator = self.rds_client.get_paginator('describe_db_clusters')
            
            for page in paginator.paginate():
                for cluster in page['DBClusters']:
                    # Only process Aurora PostgreSQL clusters
                    if not cluster['Engine'].startswith('aurora-postgresql'):
                        continue
                        
                    cluster_arn = cluster['DBClusterArn']
                    
                    try:
                        tags_response = self.rds_client.list_tags_for_resource(ResourceName=cluster_arn)
                        tag_dict = {tag['Key']: tag['Value'] for tag in tags_response['TagList']}
                        
                        if tag_dict.get(tag_key) == tag_value:
                            clusters.append({
                                'DBClusterIdentifier': cluster['DBClusterIdentifier'],
                                'DBClusterArn': cluster_arn,
                                'Status': cluster['Status'],
                                'Engine': cluster['Engine'],
                                'DBClusterMembers': cluster.get('DBClusterMembers', [])
                            })
                    except botocore.exceptions.ClientError as e:
                        self.logger.warning(f"Could not get tags for cluster {cluster['DBClusterIdentifier']}: {str(e)}")
                        continue
            
            self.logger.info(f"Found {len(clusters)} tagged Aurora PostgreSQL clusters")
            return clusters
            
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error finding tagged Aurora clusters: {str(e)}")
            raise RDSOperationError(f"Error finding tagged Aurora clusters: {str(e)}")

    def find_tagged_instances(self, tag_key, tag_value):
        """Find standalone RDS instances with the specified tag.
        
        Args:
            tag_key (str): Tag key to filter on
            tag_value (str): Tag value to filter on
            
        Returns:
            list: List of instance dictionaries
        """
        try:
            self.logger.info(f"Finding RDS instances with tag {tag_key}:{tag_value}")
            
            if self.dry_run:
                self.logger.info("[DRY RUN] Would search for tagged RDS instances")
                return [{
                    'DBInstanceIdentifier': 'mock-rds-instance-1',
                    'DBInstanceArn': 'arn:aws:rds:region:account:db:mock-rds-instance-1',
                    'DBInstanceStatus': 'available',
                    'Engine': 'postgres'
                }]
            
            instances = []
            paginator = self.rds_client.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for instance in page['DBInstances']:
                    # Skip Aurora cluster members (they're managed at cluster level)
                    if instance.get('DBClusterIdentifier'):
                        continue
                        
                    instance_arn = instance['DBInstanceArn']
                    
                    try:
                        tags_response = self.rds_client.list_tags_for_resource(ResourceName=instance_arn)
                        tag_dict = {tag['Key']: tag['Value'] for tag in tags_response['TagList']}
                        
                        if tag_dict.get(tag_key) == tag_value:
                            instances.append({
                                'DBInstanceIdentifier': instance['DBInstanceIdentifier'],
                                'DBInstanceArn': instance_arn,
                                'DBInstanceStatus': instance['DBInstanceStatus'],
                                'Engine': instance['Engine']
                            })
                    except botocore.exceptions.ClientError as e:
                        self.logger.warning(f"Could not get tags for instance {instance['DBInstanceIdentifier']}: {str(e)}")
                        continue
            
            self.logger.info(f"Found {len(instances)} tagged RDS instances")
            return instances
            
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error finding tagged RDS instances: {str(e)}")
            raise RDSOperationError(f"Error finding tagged RDS instances: {str(e)}")

    def start_clusters(self, cluster_identifiers):
        """Start Aurora clusters.
        
        Args:
            cluster_identifiers (list): List of cluster identifiers to start
            
        Returns:
            dict: Result of operation with success and failures
        """
        if not cluster_identifiers:
            self.logger.info("No clusters to start")
            return {'succeeded': [], 'failed': []}
            
        results = {'succeeded': [], 'failed': []}
        
        for cluster_id in cluster_identifiers:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would start Aurora cluster: {cluster_id}")
                    results['succeeded'].append({
                        'DBClusterIdentifier': cluster_id,
                        'Action': 'start',
                        'PreviousStatus': 'stopped',
                        'CurrentStatus': 'starting',
                        'Timestamp': datetime.now().isoformat(),
                        'Status': 'DryRun'
                    })
                    continue
                
                self.logger.info(f"Starting Aurora cluster: {cluster_id}")
                self.rds_client.start_db_cluster(DBClusterIdentifier=cluster_id)
                
                results['succeeded'].append({
                    'DBClusterIdentifier': cluster_id,
                    'Action': 'start',
                    'PreviousStatus': 'stopped',
                    'CurrentStatus': 'starting',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Success'
                })
                
            except botocore.exceptions.ClientError as e:
                error_msg = str(e)
                self.logger.error(f"Error starting Aurora cluster {cluster_id}: {error_msg}")
                results['failed'].append({
                    'DBClusterIdentifier': cluster_id,
                    'Action': 'start',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Failed',
                    'Error': error_msg
                })
                
        return results

    def stop_clusters(self, cluster_identifiers):
        """Stop Aurora clusters.
        
        Args:
            cluster_identifiers (list): List of cluster identifiers to stop
            
        Returns:
            dict: Result of operation with success and failures
        """
        if not cluster_identifiers:
            self.logger.info("No clusters to stop")
            return {'succeeded': [], 'failed': []}
            
        results = {'succeeded': [], 'failed': []}
        
        for cluster_id in cluster_identifiers:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would stop Aurora cluster: {cluster_id}")
                    results['succeeded'].append({
                        'DBClusterIdentifier': cluster_id,
                        'Action': 'stop',
                        'PreviousStatus': 'available',
                        'CurrentStatus': 'stopping',
                        'Timestamp': datetime.now().isoformat(),
                        'Status': 'DryRun'
                    })
                    continue
                
                self.logger.info(f"Stopping Aurora cluster: {cluster_id}")
                self.rds_client.stop_db_cluster(DBClusterIdentifier=cluster_id)
                
                results['succeeded'].append({
                    'DBClusterIdentifier': cluster_id,
                    'Action': 'stop',
                    'PreviousStatus': 'available',
                    'CurrentStatus': 'stopping',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Success'
                })
                
            except botocore.exceptions.ClientError as e:
                error_msg = str(e)
                self.logger.error(f"Error stopping Aurora cluster {cluster_id}: {error_msg}")
                results['failed'].append({
                    'DBClusterIdentifier': cluster_id,
                    'Action': 'stop',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Failed',
                    'Error': error_msg
                })
                
        return results

    def start_instances(self, instance_identifiers):
        """Start standalone RDS instances.
        
        Args:
            instance_identifiers (list): List of instance identifiers to start
            
        Returns:
            dict: Result of operation with success and failures
        """
        if not instance_identifiers:
            self.logger.info("No instances to start")
            return {'succeeded': [], 'failed': []}
            
        results = {'succeeded': [], 'failed': []}
        
        for instance_id in instance_identifiers:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would start RDS instance: {instance_id}")
                    results['succeeded'].append({
                        'DBInstanceIdentifier': instance_id,
                        'Action': 'start',
                        'PreviousStatus': 'stopped',
                        'CurrentStatus': 'starting',
                        'Timestamp': datetime.now().isoformat(),
                        'Status': 'DryRun'
                    })
                    continue
                
                self.logger.info(f"Starting RDS instance: {instance_id}")
                self.rds_client.start_db_instance(DBInstanceIdentifier=instance_id)
                
                results['succeeded'].append({
                    'DBInstanceIdentifier': instance_id,
                    'Action': 'start',
                    'PreviousStatus': 'stopped',
                    'CurrentStatus': 'starting',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Success'
                })
                
            except botocore.exceptions.ClientError as e:
                error_msg = str(e)
                self.logger.error(f"Error starting RDS instance {instance_id}: {error_msg}")
                results['failed'].append({
                    'DBInstanceIdentifier': instance_id,
                    'Action': 'start',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Failed',
                    'Error': error_msg
                })
                
        return results

    def stop_instances(self, instance_identifiers):
        """Stop standalone RDS instances.
        
        Args:
            instance_identifiers (list): List of instance identifiers to stop
            
        Returns:
            dict: Result of operation with success and failures
        """
        if not instance_identifiers:
            self.logger.info("No instances to stop")
            return {'succeeded': [], 'failed': []}
            
        results = {'succeeded': [], 'failed': []}
        
        for instance_id in instance_identifiers:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would stop RDS instance: {instance_id}")
                    results['succeeded'].append({
                        'DBInstanceIdentifier': instance_id,
                        'Action': 'stop',
                        'PreviousStatus': 'available',
                        'CurrentStatus': 'stopping',
                        'Timestamp': datetime.now().isoformat(),
                        'Status': 'DryRun'
                    })
                    continue
                
                self.logger.info(f"Stopping RDS instance: {instance_id}")
                self.rds_client.stop_db_instance(DBInstanceIdentifier=instance_id)
                
                results['succeeded'].append({
                    'DBInstanceIdentifier': instance_id,
                    'Action': 'stop',
                    'PreviousStatus': 'available',
                    'CurrentStatus': 'stopping',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Success'
                })
                
            except botocore.exceptions.ClientError as e:
                error_msg = str(e)
                self.logger.error(f"Error stopping RDS instance {instance_id}: {error_msg}")
                results['failed'].append({
                    'DBInstanceIdentifier': instance_id,
                    'Action': 'stop',
                    'Timestamp': datetime.now().isoformat(),
                    'Status': 'Failed',
                    'Error': error_msg
                })
                
        return results

    def verify_cluster_states(self, cluster_identifiers, expected_state, timeout=600, check_interval=30):
        """Verify Aurora clusters have reached the expected state.
        
        Args:
            cluster_identifiers (list): List of cluster identifiers
            expected_state (str): Expected state (available/stopped)
            timeout (int): Timeout in seconds (default 10 minutes)
            check_interval (int): Interval between checks in seconds
            
        Returns:
            dict: Verification results
        """
        if not cluster_identifiers:
            return {'verified': [], 'failed': []}
            
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would verify cluster states: {expected_state}")
            return {
                'verified': [{'DBClusterIdentifier': cid, 'CurrentStatus': expected_state, 
                            'Timestamp': datetime.now().isoformat()} for cid in cluster_identifiers],
                'failed': []
            }
            
        results = {'verified': [], 'failed': []}
        pending_clusters = cluster_identifiers.copy()
        
        self.logger.info(f"Verifying state for clusters: {pending_clusters}, expected: {expected_state}")
        
        end_time = time.time() + timeout
        while time.time() < end_time and pending_clusters:
            try:
                response = self.rds_client.describe_db_clusters(
                    DBClusterIdentifiers=pending_clusters
                )
                
                still_pending = []
                for cluster in response.get('DBClusters', []):
                    cluster_id = cluster['DBClusterIdentifier']
                    current_state = cluster['Status']
                    
                    if current_state == expected_state:
                        self.logger.info(f"Cluster {cluster_id} state verified: {current_state}")
                        results['verified'].append({
                            'DBClusterIdentifier': cluster_id,
                            'CurrentStatus': current_state,
                            'Timestamp': datetime.now().isoformat()
                        })
                    else:
                        self.logger.debug(f"Cluster {cluster_id} state: {current_state}, waiting for {expected_state}")
                        still_pending.append(cluster_id)
                
                pending_clusters = still_pending
                
                if not pending_clusters:
                    break
                    
                time.sleep(check_interval)
                
            except botocore.exceptions.ClientError as e:
                self.logger.error(f"Error verifying cluster states: {str(e)}")
                
                # Mark all pending clusters as failed
                for cluster_id in pending_clusters:
                    results['failed'].append({
                        'DBClusterIdentifier': cluster_id,
                        'Error': str(e),
                        'Timestamp': datetime.now().isoformat()
                    })
                break
        
        # Mark any remaining clusters as timed out
        for cluster_id in pending_clusters:
            self.logger.warning(f"Cluster {cluster_id} verification timed out")
            results['failed'].append({
                'DBClusterIdentifier': cluster_id,
                'Error': f'Verification timed out after {timeout} seconds',
                'Timestamp': datetime.now().isoformat()
            })
        
        return results

    def verify_instance_states(self, instance_identifiers, expected_state, timeout=300, check_interval=15):
        """Verify RDS instances have reached the expected state.
        
        Args:
            instance_identifiers (list): List of instance identifiers
            expected_state (str): Expected state (available/stopped)
            timeout (int): Timeout in seconds (default 5 minutes)
            check_interval (int): Interval between checks in seconds
            
        Returns:
            dict: Verification results
        """
        if not instance_identifiers:
            return {'verified': [], 'failed': []}
            
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would verify instance states: {expected_state}")
            return {
                'verified': [{'DBInstanceIdentifier': iid, 'CurrentStatus': expected_state, 
                            'Timestamp': datetime.now().isoformat()} for iid in instance_identifiers],
                'failed': []
            }
            
        results = {'verified': [], 'failed': []}
        pending_instances = instance_identifiers.copy()
        
        self.logger.info(f"Verifying state for instances: {pending_instances}, expected: {expected_state}")
        
        end_time = time.time() + timeout
        while time.time() < end_time and pending_instances:
            try:
                response = self.rds_client.describe_db_instances(
                    DBInstanceIdentifiers=pending_instances
                )
                
                still_pending = []
                for instance in response.get('DBInstances', []):
                    instance_id = instance['DBInstanceIdentifier']
                    current_state = instance['DBInstanceStatus']
                    
                    if current_state == expected_state:
                        self.logger.info(f"Instance {instance_id} state verified: {current_state}")
                        results['verified'].append({
                            'DBInstanceIdentifier': instance_id,
                            'CurrentStatus': current_state,
                            'Timestamp': datetime.now().isoformat()
                        })
                    else:
                        self.logger.debug(f"Instance {instance_id} state: {current_state}, waiting for {expected_state}")
                        still_pending.append(instance_id)
                
                pending_instances = still_pending
                
                if not pending_instances:
                    break
                    
                time.sleep(check_interval)
                
            except botocore.exceptions.ClientError as e:
                self.logger.error(f"Error verifying instance states: {str(e)}")
                
                # Mark all pending instances as failed
                for instance_id in pending_instances:
                    results['failed'].append({
                        'DBInstanceIdentifier': instance_id,
                        'Error': str(e),
                        'Timestamp': datetime.now().isoformat()
                    })
                break
        
        # Mark any remaining instances as timed out
        for instance_id in pending_instances:
            self.logger.warning(f"Instance {instance_id} verification timed out")
            results['failed'].append({
                'DBInstanceIdentifier': instance_id,
                'Error': f'Verification timed out after {timeout} seconds',
                'Timestamp': datetime.now().isoformat()
            })
        
        return results