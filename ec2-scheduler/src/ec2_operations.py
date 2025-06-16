# src/ec2_operations.py
import boto3
import logging
import botocore.exceptions
import time
from datetime import datetime

class InstanceOperationError(Exception):
    """Exception raised for instance operation errors."""
    pass

class EC2Operations:
    """Handles EC2 instance operations."""
    
    def __init__(self, region):
        """Initialize EC2 operations.
        
        Args:
            region (str): AWS region
        """
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.ec2_client = boto3.client('ec2', region_name=region)
        
    def find_tagged_instances(self, tag_key, tag_value):
        """Find EC2 instances with the specified tag.
        
        Args:
            tag_key (str): Tag key to filter on
            tag_value (str): Tag value to filter on
            
        Returns:
            list: List of instance dictionaries with environment tags
        """
        try:
            self.logger.info(f"Finding instances with tag {tag_key}:{tag_value}")
            
            # Create filter for the tag
            filters = [
                {
                    'Name': f'tag:{tag_key}',
                    'Values': [tag_value]
                }
            ]
            
            # Get instances with the specified tag
            response = self.ec2_client.describe_instances(Filters=filters)
            
            instances = []
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    instance_name = ''
                    environment_tag = ''
                    all_tags = {}
                    
                    # Extract all tags including environment
                    for tag in instance.get('Tags', []):
                        all_tags[tag['Key']] = tag['Value']
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']
                        elif tag['Key'].lower() in ['environment', 'env', 'stage']:
                            environment_tag = tag['Value']
                    
                    # If no explicit environment tag, try to infer from other tags
                    if not environment_tag:
                        # Check for common environment patterns in name or other tags
                        for key, value in all_tags.items():
                            if any(env in value.lower() for env in ['prod', 'production', 'staging', 'stage', 'dev', 'development', 'test', 'testing']):
                                environment_tag = value
                                break
                    
                    instances.append({
                        'InstanceId': instance['InstanceId'],
                        'State': instance['State']['Name'],
                        'Name': instance_name,
                        'Environment': environment_tag,
                        'AllTags': all_tags
                    })
            
            self.logger.info(f"Found {len(instances)} tagged instances")
            return instances
            
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error finding tagged instances: {str(e)}")
            raise InstanceOperationError(f"Error finding tagged instances: {str(e)}")
            
    def start_instances(self, instance_ids):
        """Start EC2 instances.
        
        Args:
            instance_ids (list): List of instance IDs to start
            
        Returns:
            dict: Result of operation with success and failures
        """
        if not instance_ids:
            self.logger.info("No instances to start")
            return {'succeeded': [], 'failed': []}
            
        results = {'succeeded': [], 'failed': []}
        
        try:
            self.logger.info(f"Starting instances: {instance_ids}")
            response = self.ec2_client.start_instances(InstanceIds=instance_ids)
            
            # Process results
            for instance in response.get('StartingInstances', []):
                instance_id = instance['InstanceId']
                previous_state = instance['PreviousState']['Name']
                current_state = instance['CurrentState']['Name']
                
                self.logger.info(f"Instance {instance_id}: {previous_state} -> {current_state}")
                
                results['succeeded'].append({
                    'InstanceId': instance_id,
                    'PreviousState': previous_state,
                    'CurrentState': current_state,
                    'Timestamp': datetime.now().isoformat()
                })
                
        except botocore.exceptions.ClientError as e:
            error_msg = str(e)
            self.logger.error(f"Error starting instances: {error_msg}")
            
            # Handle specific error cases
            if 'InvalidInstanceID.NotFound' in error_msg:
                # Some instances might not exist
                missing_ids = []
                for instance_id in instance_ids:
                    if instance_id in error_msg:
                        missing_ids.append(instance_id)
                        results['failed'].append({
                            'InstanceId': instance_id,
                            'Error': 'Instance not found',
                            'Timestamp': datetime.now().isoformat()
                        })
                
                # Try to start remaining instances
                remaining_ids = [id for id in instance_ids if id not in missing_ids]
                if remaining_ids:
                    self.logger.info(f"Retrying with remaining instances: {remaining_ids}")
                    retry_results = self.start_instances(remaining_ids)
                    results['succeeded'].extend(retry_results['succeeded'])
                    results['failed'].extend(retry_results['failed'])
            else:
                # Other error, mark all as failed
                for instance_id in instance_ids:
                    results['failed'].append({
                        'InstanceId': instance_id,
                        'Error': error_msg,
                        'Timestamp': datetime.now().isoformat()
                    })
                    
        return results
        
    def stop_instances(self, instance_ids, force=False):
        """Stop EC2 instances.
        
        Args:
            instance_ids (list): List of instance IDs to stop
            force (bool): Whether to force stop
            
        Returns:
            dict: Result of operation with success and failures
        """
        if not instance_ids:
            self.logger.info("No instances to stop")
            return {'succeeded': [], 'failed': []}
            
        results = {'succeeded': [], 'failed': []}
        
        try:
            self.logger.info(f"Stopping instances: {instance_ids}")
            response = self.ec2_client.stop_instances(InstanceIds=instance_ids, Force=force)
            
            # Process results
            for instance in response.get('StoppingInstances', []):
                instance_id = instance['InstanceId']
                previous_state = instance['PreviousState']['Name']
                current_state = instance['CurrentState']['Name']
                
                self.logger.info(f"Instance {instance_id}: {previous_state} -> {current_state}")
                
                results['succeeded'].append({
                    'InstanceId': instance_id,
                    'PreviousState': previous_state,
                    'CurrentState': current_state,
                    'Timestamp': datetime.now().isoformat()
                })
                
        except botocore.exceptions.ClientError as e:
            error_msg = str(e)
            self.logger.error(f"Error stopping instances: {error_msg}")
            
            # Handle specific error cases
            if 'InvalidInstanceID.NotFound' in error_msg:
                # Some instances might not exist
                missing_ids = []
                for instance_id in instance_ids:
                    if instance_id in error_msg:
                        missing_ids.append(instance_id)
                        results['failed'].append({
                            'InstanceId': instance_id,
                            'Error': 'Instance not found',
                            'Timestamp': datetime.now().isoformat()
                        })
                
                # Try to stop remaining instances
                remaining_ids = [id for id in instance_ids if id not in missing_ids]
                if remaining_ids:
                    self.logger.info(f"Retrying with remaining instances: {remaining_ids}")
                    retry_results = self.stop_instances(remaining_ids, force)
                    results['succeeded'].extend(retry_results['succeeded'])
                    results['failed'].extend(retry_results['failed'])
            else:
                # Other error, mark all as failed
                for instance_id in instance_ids:
                    results['failed'].append({
                        'InstanceId': instance_id,
                        'Error': error_msg,
                        'Timestamp': datetime.now().isoformat()
                    })
                    
        return results
        
    def verify_instance_states(self, instances, expected_state, timeout=300, check_interval=10):
        """Verify instances have reached the expected state.
        
        Args:
            instances (list): List of instance IDs
            expected_state (str): Expected state (running/stopped)
            timeout (int): Timeout in seconds
            check_interval (int): Interval between checks in seconds
            
        Returns:
            dict: Verification results
        """
        if not instances:
            return {'verified': [], 'failed': []}
            
        results = {'verified': [], 'failed': []}
        instance_ids = [i['InstanceId'] for i in instances]
        
        self.logger.info(f"Verifying state for instances: {instance_ids}, expected: {expected_state}")
        
        end_time = time.time() + timeout
        while time.time() < end_time and instance_ids:
            try:
                response = self.ec2_client.describe_instances(InstanceIds=instance_ids)
                
                # Update instance_ids list with those still not in expected state
                pending_ids = []
                for reservation in response.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance_id = instance['InstanceId']
                        current_state = instance['State']['Name']
                        
                        if current_state == expected_state:
                            self.logger.info(f"Instance {instance_id} state verified: {current_state}")
                            results['verified'].append({
                                'InstanceId': instance_id,
                                'CurrentState': current_state,
                                'Timestamp': datetime.now().isoformat()
                            })
                        else:
                            self.logger.debug(f"Instance {instance_id} state: {current_state}, waiting for {expected_state}")
                            pending_ids.append(instance_id)
                
                instance_ids = pending_ids
                
                if not instance_ids:
                    break
                    
                time.sleep(check_interval)
                
            except botocore.exceptions.ClientError as e:
                self.logger.error(f"Error verifying instance states: {str(e)}")
                
                # Mark all pending instances as failed
                for instance_id in instance_ids:
                    results['failed'].append({
                        'InstanceId': instance_id,
                        'Error': str(e),
                        'Timestamp': datetime.now().isoformat()
                    })
                break
        
        # Any instances still pending after timeout are marked as failed
        for instance_id in instance_ids:
            self.logger.warning(f"Instance {instance_id} did not reach {expected_state} within timeout")
            results['failed'].append({
                'InstanceId': instance_id,
                'Error': f"Timeout waiting for state {expected_state}",
                'Timestamp': datetime.now().isoformat()
            })
            
        return results