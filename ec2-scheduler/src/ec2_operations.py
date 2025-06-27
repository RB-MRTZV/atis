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
        
    def find_tagged_instances(self, tag_key, tag_value, asg_tag_key=None, asg_tag_value=None):
        """Find EC2 instances with the specified tag.
        
        Args:
            tag_key (str): Tag key to filter on
            tag_value (str): Tag value to filter on
            asg_tag_key (str): Optional ASG tag key to identify ASG-managed instances
            asg_tag_value (str): Optional ASG tag value to identify ASG-managed instances
            
        Returns:
            list: List of instance dictionaries with environment tags and ASG status
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
                    is_asg_managed = False
                    
                    # Extract all tags including environment
                    for tag in instance.get('Tags', []):
                        all_tags[tag['Key']] = tag['Value']
                        if tag['Key'] == 'Name':
                            instance_name = tag['Value']
                        elif tag['Key'].lower() in ['environment', 'env', 'stage']:
                            environment_tag = tag['Value']
                        elif asg_tag_key and tag['Key'] == asg_tag_key and tag['Value'] == asg_tag_value:
                            is_asg_managed = True
                    
                    # Check for ASG tag in aws:autoscaling:groupName as fallback
                    if not is_asg_managed and 'aws:autoscaling:groupName' in all_tags:
                        is_asg_managed = True
                    
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
                        'AllTags': all_tags,
                        'IsASGManaged': is_asg_managed,
                        'InstanceType': instance.get('InstanceType', 'Unknown'),
                        'LaunchTime': instance.get('LaunchTime', '').isoformat() if instance.get('LaunchTime') else 'Unknown'
                    })
            
            self.logger.info(f"Found {len(instances)} tagged instances")
            return instances
            
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error finding tagged instances: {str(e)}")
            raise InstanceOperationError(f"Error finding tagged instances: {str(e)}")
    
    def display_dry_run_summary(self, instances, action):
        """Display a detailed dry-run summary of instances that would be affected.
        
        This method provides a comprehensive console output showing:
        - Total instances found vs those that would actually change state
        - Visual indicators: ✓ (would change), ⚠ (already in target state), 📦 (ASG-managed)
        - Instance details: ID, name, current state, expected state, type, environment
        - Breakdown by regular EC2 vs ASG-managed instances
        - Clear legend explaining all status indicators
        
        The output is optimized for GitLab CI pipeline visibility and human readability.
        
        Args:
            instances (list): List of instance dictionaries from find_tagged_instances()
            action (str): Action to be performed ('start' or 'stop')
            
        Returns:
            str: Formatted summary for console output and logging
        """
        if not instances:
            summary = f"\n=== DRY RUN SUMMARY ===\nNo instances found with the specified tags.\n"
            print(summary)
            return summary
        
        expected_state = 'running' if action == 'start' else 'stopped'
        
        # Separate regular and ASG-managed instances
        regular_instances = [i for i in instances if not i['IsASGManaged']]
        asg_instances = [i for i in instances if i['IsASGManaged']]
        
        summary_lines = [
            "\n" + "="*80,
            f"DRY RUN SUMMARY - Action: {action.upper()}",
            "="*80,
            f"Total instances found: {len(instances)}",
            f"  - Regular EC2 instances: {len(regular_instances)}",
            f"  - ASG-managed instances: {len(asg_instances)}",
            ""
        ]
        
        if regular_instances:
            summary_lines.extend([
                "REGULAR EC2 INSTANCES:",
                "-" * 40
            ])
            
            for instance in regular_instances:
                current_state = instance['State']
                would_change = current_state != expected_state
                status_indicator = "✓" if would_change else "⚠"
                
                summary_lines.append(
                    f"{status_indicator} {instance['InstanceId']:19} | "
                    f"{instance['Name'][:25]:25} | "
                    f"Current: {current_state:10} | "
                    f"Expected: {expected_state:10} | "
                    f"Type: {instance['InstanceType']:10} | "
                    f"Env: {instance['Environment'][:10]:10}"
                )
            
            # Count instances that would actually change
            changing_regular = len([i for i in regular_instances if i['State'] != expected_state])
            summary_lines.append(f"\nRegular instances that would change state: {changing_regular}/{len(regular_instances)}")
        
        if asg_instances:
            summary_lines.extend([
                "",
                "ASG-MANAGED INSTANCES:",
                "-" * 40
            ])
            
            for instance in asg_instances:
                current_state = instance['State']
                asg_name = instance['AllTags'].get('aws:autoscaling:groupName', 'Unknown ASG')
                
                summary_lines.append(
                    f"📦 {instance['InstanceId']:19} | "
                    f"{instance['Name'][:25]:25} | "
                    f"Current: {current_state:10} | "
                    f"ASG: {asg_name[:15]:15} | "
                    f"Type: {instance['InstanceType']:10} | "
                    f"Env: {instance['Environment'][:10]:10}"
                )
            
            summary_lines.append(f"\nASG instances require ASG scaling operations (not direct instance control)")
        
        summary_lines.extend([
            "",
            "LEGEND:",
            "  ✓ = Instance state would change",
            "  ⚠ = Instance already in target state (no change needed)",
            "  📦 = ASG-managed instance (requires ASG operations)",
            "",
            f"[DRY RUN] No actual AWS operations will be performed.",
            "="*80
        ])
        
        summary = "\n".join(summary_lines)
        print(summary)
        return summary
            
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
        
    def verify_instance_states(self, instances, expected_state, status_check_level='state', timeout=300, check_interval=10):
        """Verify instances have reached the expected state with optional comprehensive status checks.
        
        Provides three levels of verification depth:
        
        1. 'state' (default): Basic instance state verification (running/stopped)
           - Checks only the EC2 instance state
           - Fastest verification method
           - Backward compatible with existing implementations
           
        2. 'system': State + AWS system status checks  
           - Includes state verification plus AWS hypervisor-level system status
           - Verifies underlying infrastructure health
           - Only applies to running instances (stopped instances skip status checks)
           
        3. 'full': State + system + instance status + network reachability
           - Most comprehensive verification level
           - Includes all system checks plus guest OS status and network connectivity
           - Ensures instances are fully operational and reachable
           - Only applies to running instances (stopped instances skip status checks)
        
        For stopped instances, all levels default to state-only verification since
        AWS status checks are not applicable to stopped instances.
        
        Args:
            instances (list): List of instance IDs or instance dicts from successful operations
            expected_state (str): Expected instance state ('running' or 'stopped')
            status_check_level (str): Verification depth - 'state', 'system', or 'full'
            timeout (int): Maximum time to wait for verification in seconds (default: 300)
            check_interval (int): Interval between verification attempts in seconds (default: 10)
            
        Returns:
            dict: Verification results with the following structure:
                {
                    'verified': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'CurrentState': 'running',
                            'StatusDetails': {
                                'passed': True,
                                'summary': 'State: running ✓, System: ok ✓',
                                'details': {...}
                            },
                            'Timestamp': '2024-01-01T12:00:00.000Z'
                        }
                    ],
                    'failed': [
                        {
                            'InstanceId': 'i-abcdef1234567890',
                            'Error': 'Timeout waiting for system verification',
                            'StatusDetails': {
                                'passed': False,
                                'summary': 'State: running ✓, System: initializing ✗'
                            },
                            'Timestamp': '2024-01-01T12:05:00.000Z'
                        }
                    ]
                }
        """
        if not instances:
            return {'verified': [], 'failed': []}
            
        results = {'verified': [], 'failed': []}
        
        # Handle both list of IDs and list of dicts
        if isinstance(instances[0], dict):
            instance_ids = [i['InstanceId'] for i in instances]
        else:
            instance_ids = instances
        
        self.logger.info(f"Verifying instances with {status_check_level} level checks: {instance_ids}, expected state: {expected_state}")
        
        end_time = time.time() + timeout
        while time.time() < end_time and instance_ids:
            try:
                response = self.ec2_client.describe_instances(InstanceIds=instance_ids)
                
                # Get status checks if needed
                status_response = None
                if status_check_level in ['system', 'full']:
                    try:
                        status_response = self.ec2_client.describe_instance_status(
                            InstanceIds=instance_ids,
                            IncludeAllInstances=True
                        )
                    except botocore.exceptions.ClientError as e:
                        self.logger.warning(f"Could not get instance status: {str(e)}")
                
                # Update instance_ids list with those still not meeting criteria
                pending_ids = []
                for reservation in response.get('Reservations', []):
                    for instance in reservation.get('Instances', []):
                        instance_id = instance['InstanceId']
                        current_state = instance['State']['Name']
                        
                        verification_result = self._verify_instance_comprehensive(
                            instance, expected_state, status_check_level, status_response
                        )
                        
                        if verification_result['passed']:
                            self.logger.info(f"Instance {instance_id} verification passed: {verification_result['summary']}")
                            results['verified'].append({
                                'InstanceId': instance_id,
                                'CurrentState': current_state,
                                'StatusDetails': verification_result,
                                'Timestamp': datetime.now().isoformat()
                            })
                        else:
                            self.logger.debug(f"Instance {instance_id} verification pending: {verification_result['summary']}")
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
                        'StatusDetails': {'passed': False, 'summary': f'API Error: {str(e)}'},
                        'Timestamp': datetime.now().isoformat()
                    })
                break
        
        # Any instances still pending after timeout are marked as failed
        for instance_id in instance_ids:
            self.logger.warning(f"Instance {instance_id} did not pass {status_check_level} verification within timeout")
            results['failed'].append({
                'InstanceId': instance_id,
                'Error': f"Timeout waiting for {status_check_level} verification",
                'StatusDetails': {'passed': False, 'summary': f'Timeout after {timeout}s'},
                'Timestamp': datetime.now().isoformat()
            })
            
        return results

    def _verify_instance_comprehensive(self, instance, expected_state, status_check_level, status_response):
        """Perform comprehensive verification of an instance based on the check level.
        
        Args:
            instance (dict): Instance data from describe_instances
            expected_state (str): Expected instance state
            status_check_level (str): Level of checks to perform
            status_response (dict): Response from describe_instance_status
            
        Returns:
            dict: Verification result with detailed status
        """
        instance_id = instance['InstanceId']
        current_state = instance['State']['Name']
        
        result = {
            'passed': False,
            'summary': '',
            'details': {
                'state_check': {'passed': False, 'value': current_state, 'expected': expected_state},
                'system_status': {'passed': None, 'value': None},
                'instance_status': {'passed': None, 'value': None},
                'reachability': {'passed': None, 'value': None}
            }
        }
        
        # Level 1: State check (always performed)
        state_passed = current_state == expected_state
        result['details']['state_check']['passed'] = state_passed
        
        if not state_passed:
            result['summary'] = f"State: {current_state} (expected {expected_state})"
            return result
        
        if status_check_level == 'state':
            result['passed'] = True
            result['summary'] = f"State: {current_state} ✓"
            return result
        
        # Level 2: System status checks (for running instances)
        if status_check_level in ['system', 'full'] and expected_state == 'running':
            if status_response:
                instance_status = None
                for status in status_response.get('InstanceStatuses', []):
                    if status['InstanceId'] == instance_id:
                        instance_status = status
                        break
                
                if instance_status:
                    # System status check
                    system_status = instance_status.get('SystemStatus', {}).get('Status', 'unknown')
                    system_passed = system_status == 'ok'
                    result['details']['system_status'] = {'passed': system_passed, 'value': system_status}
                    
                    if status_check_level == 'system':
                        result['passed'] = system_passed
                        result['summary'] = f"State: {current_state} ✓, System: {system_status} {'✓' if system_passed else '✗'}"
                        return result
                    
                    # Level 3: Full checks (system + instance status + reachability)
                    if status_check_level == 'full':
                        # Instance status check
                        instance_status_check = instance_status.get('InstanceStatus', {}).get('Status', 'unknown')
                        instance_passed = instance_status_check == 'ok'
                        result['details']['instance_status'] = {'passed': instance_passed, 'value': instance_status_check}
                        
                        # Reachability check
                        reachability = instance_status.get('InstanceStatus', {}).get('Details', [])
                        reachability_passed = True
                        reachability_summary = 'ok'
                        
                        for detail in reachability:
                            if detail.get('Name') == 'reachability' and detail.get('Status') != 'passed':
                                reachability_passed = False
                                reachability_summary = detail.get('Status', 'unknown')
                                break
                        
                        result['details']['reachability'] = {'passed': reachability_passed, 'value': reachability_summary}
                        
                        # All checks must pass for full verification
                        all_passed = system_passed and instance_passed and reachability_passed
                        result['passed'] = all_passed
                        
                        status_indicators = [
                            f"State: {current_state} ✓",
                            f"System: {system_status} {'✓' if system_passed else '✗'}",
                            f"Instance: {instance_status_check} {'✓' if instance_passed else '✗'}",
                            f"Reachability: {reachability_summary} {'✓' if reachability_passed else '✗'}"
                        ]
                        result['summary'] = ', '.join(status_indicators)
                        return result
                else:
                    # No status information available yet
                    result['details']['system_status'] = {'passed': False, 'value': 'unavailable'}
                    result['summary'] = f"State: {current_state} ✓, System status: unavailable"
                    return result
            else:
                # Could not get status response
                result['details']['system_status'] = {'passed': False, 'value': 'api_error'}
                result['summary'] = f"State: {current_state} ✓, System status: API error"
                return result
        
        # For stopped instances with system/full checks, only state matters
        if expected_state == 'stopped':
            result['passed'] = True
            result['summary'] = f"State: {current_state} ✓ (stopped instances skip status checks)"
            return result
        
        # Default fallback
        result['passed'] = state_passed
        result['summary'] = f"State: {current_state} {'✓' if state_passed else '✗'}"
        return result