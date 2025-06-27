# src/asg_operations.py
import boto3
import logging
import botocore.exceptions
import json
import time
from datetime import datetime

class ASGOperationError(Exception):
    """Exception raised for ASG operation errors."""
    pass

class ASGOperations:
    """Handles Auto Scaling Group operations for ASG-managed instances."""
    
    def __init__(self, region):
        """Initialize ASG operations.
        
        Args:
            region (str): AWS region
        """
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.asg_client = boto3.client('autoscaling', region_name=region)
        self.ec2_client = boto3.client('ec2', region_name=region)
        
    def find_asg_for_instance(self, instance_id):
        """Find the ASG that manages a specific instance.
        
        Args:
            instance_id (str): EC2 instance ID
            
        Returns:
            str: ASG name if found, None otherwise
        """
        try:
            # Get all ASGs and find the one containing this instance
            paginator = self.asg_client.get_paginator('describe_auto_scaling_groups')
            
            for page in paginator.paginate():
                for asg in page['AutoScalingGroups']:
                    for instance in asg.get('Instances', []):
                        if instance['InstanceId'] == instance_id:
                            return asg['AutoScalingGroupName']
            
            return None
            
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error finding ASG for instance {instance_id}: {str(e)}")
            return None
    
    def suspend_asg_processes(self, asg_name, processes=None):
        """Suspend ASG processes.
        
        Args:
            asg_name (str): Name of the ASG
            processes (list): List of processes to suspend. If None, suspends default processes.
            
        Returns:
            dict: Result of operation
        """
        if processes is None:
            processes = ['Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy']
        
        try:
            self.logger.info(f"Suspending processes {processes} for ASG {asg_name}")
            
            self.asg_client.suspend_processes(
                AutoScalingGroupName=asg_name,
                ScalingProcesses=processes
            )
            
            return {
                'ASGName': asg_name,
                'SuspendedProcesses': processes,
                'Status': 'Success',
                'Timestamp': datetime.now().isoformat()
            }
            
        except botocore.exceptions.ClientError as e:
            error_msg = str(e)
            self.logger.error(f"Error suspending processes for ASG {asg_name}: {error_msg}")
            return {
                'ASGName': asg_name,
                'SuspendedProcesses': processes,
                'Status': 'Failed',
                'Error': error_msg,
                'Timestamp': datetime.now().isoformat()
            }
    
    def resume_asg_processes(self, asg_name, processes=None):
        """Resume ASG processes.
        
        Args:
            asg_name (str): Name of the ASG
            processes (list): List of processes to resume. If None, resumes default processes.
            
        Returns:
            dict: Result of operation
        """
        if processes is None:
            processes = ['Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy']
        
        try:
            self.logger.info(f"Resuming processes {processes} for ASG {asg_name}")
            
            self.asg_client.resume_processes(
                AutoScalingGroupName=asg_name,
                ScalingProcesses=processes
            )
            
            return {
                'ASGName': asg_name,
                'ResumedProcesses': processes,
                'Status': 'Success',
                'Timestamp': datetime.now().isoformat()
            }
            
        except botocore.exceptions.ClientError as e:
            error_msg = str(e)
            self.logger.error(f"Error resuming processes for ASG {asg_name}: {error_msg}")
            return {
                'ASGName': asg_name,
                'ResumedProcesses': processes,
                'Status': 'Failed',
                'Error': error_msg,
                'Timestamp': datetime.now().isoformat()
            }
    
    def store_asg_state(self, asg_name, asg_data):
        """Store ASG original state in tags for later restoration.
        
        Args:
            asg_name (str): Name of the ASG
            asg_data (dict): ASG data including capacity settings
            
        Returns:
            dict: Result of operation
        """
        try:
            # Prepare state data
            state_data = {
                'desired': asg_data['DesiredCapacity'],
                'min': asg_data['MinSize'],
                'max': asg_data['MaxSize'],
                'stopped_at': datetime.now().isoformat(),
                'instance_ids': [i['InstanceId'] for i in asg_data['Instances']]
            }
            
            self.logger.info(f"Storing state for ASG {asg_name}: {state_data}")
            
            # Store state in ASG tags
            self.asg_client.create_or_update_tags(
                Tags=[{
                    'Key': 'ASGManagerState',
                    'Value': json.dumps(state_data),
                    'ResourceId': asg_name,
                    'ResourceType': 'auto-scaling-group',
                    'PropagateAtLaunch': False
                }]
            )
            
            return {
                'ASGName': asg_name,
                'StoredState': state_data,
                'Status': 'Success',
                'Timestamp': datetime.now().isoformat()
            }
            
        except botocore.exceptions.ClientError as e:
            error_msg = str(e)
            self.logger.error(f"Error storing state for ASG {asg_name}: {error_msg}")
            return {
                'ASGName': asg_name,
                'Status': 'Failed',
                'Error': error_msg,
                'Timestamp': datetime.now().isoformat()
            }
    
    def retrieve_asg_state(self, asg_name):
        """Retrieve ASG stored state from tags.
        
        Args:
            asg_name (str): Name of the ASG
            
        Returns:
            dict: Stored state data or None if not found
        """
        try:
            # Get ASG details including tags
            response = self.asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                return None
                
            asg = response['AutoScalingGroups'][0]
            
            # Find the state tag
            for tag in asg.get('Tags', []):
                if tag['Key'] == 'ASGManagerState':
                    return json.loads(tag['Value'])
            
            return None
            
        except (botocore.exceptions.ClientError, json.JSONDecodeError) as e:
            self.logger.error(f"Error retrieving state for ASG {asg_name}: {str(e)}")
            return None
    
    def cleanup_asg_state(self, asg_name):
        """Remove stored state from ASG tags.
        
        Args:
            asg_name (str): Name of the ASG
            
        Returns:
            dict: Result of operation
        """
        try:
            self.logger.info(f"Cleaning up state for ASG {asg_name}")
            
            self.asg_client.delete_tags(
                Tags=[{
                    'Key': 'ASGManagerState',
                    'ResourceId': asg_name,
                    'ResourceType': 'auto-scaling-group'
                }]
            )
            
            return {
                'ASGName': asg_name,
                'Status': 'Success',
                'Timestamp': datetime.now().isoformat()
            }
            
        except botocore.exceptions.ClientError as e:
            error_msg = str(e)
            self.logger.error(f"Error cleaning up state for ASG {asg_name}: {error_msg}")
            return {
                'ASGName': asg_name,
                'Status': 'Failed',
                'Error': error_msg,
                'Timestamp': datetime.now().isoformat()
            }
    
    def handle_asg_instance_stop(self, instance_id, verify=False, status_check_level='state'):
        """Handle stopping an ASG-managed instance (suspend processes first) with optional verification.
        
        Args:
            instance_id (str): Instance ID to stop
            verify (bool): Whether to verify instance state after stopping
            status_check_level (str): Level of status checks ('state' only for stopped instances)
            
        Returns:
            dict: Result of operation
        """
        try:
            # Find the ASG for this instance
            asg_name = self.find_asg_for_instance(instance_id)
            if not asg_name:
                return {
                    'InstanceId': instance_id,
                    'ASGName': None,
                    'Status': 'Failed',
                    'Error': 'ASG not found for instance',
                    'Timestamp': datetime.now().isoformat()
                }
            
            self.logger.info(f"Handling ASG-managed instance {instance_id} in ASG {asg_name}")
            
            # Get ASG information
            response = self.asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                return {
                    'InstanceId': instance_id,
                    'ASGName': asg_name,
                    'Status': 'Failed',
                    'Error': 'ASG details not found',
                    'Timestamp': datetime.now().isoformat()
                }
            
            asg_data = response['AutoScalingGroups'][0]
            
            # Check if processes are already suspended for this ASG
            suspended_processes = [p['ProcessName'] for p in asg_data.get('SuspendedProcesses', [])]
            required_processes = ['Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy']
            
            processes_suspended = False
            if not all(process in suspended_processes for process in required_processes):
                # Store ASG state and suspend processes
                state_result = self.store_asg_state(asg_name, asg_data)
                if state_result['Status'] == 'Success':
                    suspend_result = self.suspend_asg_processes(asg_name)
                    processes_suspended = (suspend_result['Status'] == 'Success')
                else:
                    return {
                        'InstanceId': instance_id,
                        'ASGName': asg_name,
                        'Status': 'Failed',
                        'Error': 'Failed to store ASG state',
                        'Timestamp': datetime.now().isoformat()
                    }
            else:
                processes_suspended = True
                self.logger.info(f"ASG {asg_name} processes already suspended")
            
            # Stop the instance
            if processes_suspended:
                try:
                    response = self.ec2_client.stop_instances(InstanceIds=[instance_id])
                    instance_info = response['StoppingInstances'][0]
                    
                    # Perform verification if requested
                    verification_result = None
                    if verify:
                        self.logger.info(f"Verifying ASG instance {instance_id} stopped state")
                        
                        # Wait for instance to be stopped first
                        self.logger.info(f"Waiting for instance {instance_id} to be stopped...")
                        waiter = self.ec2_client.get_waiter('instance_stopped')
                        waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 40})
                        
                        verification_result = self.verify_asg_instance_state(
                            instance_id, 'stopped', status_check_level
                        )
                        
                        if not verification_result['passed']:
                            return {
                                'InstanceId': instance_id,
                                'ASGName': asg_name,
                                'PreviousState': instance_info['PreviousState']['Name'],
                                'CurrentState': instance_info['CurrentState']['Name'],
                                'Status': 'Verification Failed',
                                'Error': f"Verification failed: {verification_result['summary']}",
                                'ProcessesSuspended': True,
                                'VerificationDetails': verification_result,
                                'Timestamp': datetime.now().isoformat()
                            }
                    
                    result = {
                        'InstanceId': instance_id,
                        'ASGName': asg_name,
                        'PreviousState': instance_info['PreviousState']['Name'],
                        'CurrentState': instance_info['CurrentState']['Name'],
                        'Status': 'Success',
                        'ProcessesSuspended': True,
                        'Timestamp': datetime.now().isoformat()
                    }
                    
                    if verify:
                        result['VerificationDetails'] = verification_result
                    
                    return result
                    
                except botocore.exceptions.ClientError as e:
                    return {
                        'InstanceId': instance_id,
                        'ASGName': asg_name,
                        'Status': 'Failed',
                        'Error': f'Failed to stop instance: {str(e)}',
                        'Timestamp': datetime.now().isoformat()
                    }
            else:
                return {
                    'InstanceId': instance_id,
                    'ASGName': asg_name,
                    'Status': 'Failed',
                    'Error': 'Failed to suspend ASG processes',
                    'Timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error handling ASG instance stop {instance_id}: {str(e)}")
            return {
                'InstanceId': instance_id,
                'ASGName': asg_name if 'asg_name' in locals() else None,
                'Status': 'Failed',
                'Error': str(e),
                'Timestamp': datetime.now().isoformat()
            }
    
    def handle_asg_instance_start(self, instance_id, verify=False, status_check_level='state'):
        """Handle starting an ASG-managed instance and optionally verify with status checks before resuming ASG processes.
        
        Args:
            instance_id (str): Instance ID to start
            verify (bool): Whether to verify instance state after starting
            status_check_level (str): Level of status checks ('state', 'system', 'full')
            
        Returns:
            dict: Result of operation
        """
        try:
            # Find the ASG for this instance
            asg_name = self.find_asg_for_instance(instance_id)
            if not asg_name:
                return {
                    'InstanceId': instance_id,
                    'ASGName': None,
                    'Status': 'Failed',
                    'Error': 'ASG not found for instance',
                    'Timestamp': datetime.now().isoformat()
                }
            
            self.logger.info(f"Handling ASG-managed instance {instance_id} in ASG {asg_name}")
            
            # Start the instance first
            try:
                response = self.ec2_client.start_instances(InstanceIds=[instance_id])
                instance_info = response['StartingInstances'][0]
                
                # Wait for instance to be running
                self.logger.info(f"Waiting for instance {instance_id} to be running...")
                waiter = self.ec2_client.get_waiter('instance_running')
                waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 40})
                
                # Perform verification if requested
                verification_result = None
                if verify:
                    self.logger.info(f"Verifying ASG instance {instance_id} with {status_check_level} level checks")
                    verification_result = self.verify_asg_instance_state(
                        instance_id, 'running', status_check_level
                    )
                    
                    if not verification_result['passed']:
                        return {
                            'InstanceId': instance_id,
                            'ASGName': asg_name,
                            'PreviousState': instance_info['PreviousState']['Name'],
                            'CurrentState': instance_info['CurrentState']['Name'],
                            'Status': 'Verification Failed',
                            'Error': f"Verification failed: {verification_result['summary']}",
                            'VerificationDetails': verification_result,
                            'Timestamp': datetime.now().isoformat()
                        }
                
                # Check if this is the last instance in the ASG to start
                # If so, we can resume processes and clean up state
                asg_response = self.asg_client.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name]
                )
                
                if asg_response['AutoScalingGroups']:
                    asg_data = asg_response['AutoScalingGroups'][0]
                    
                    # Check if all instances in ASG are running (and verified if required)
                    all_running = True
                    all_verified = True
                    for instance in asg_data.get('Instances', []):
                        # Get instance state
                        ec2_response = self.ec2_client.describe_instances(
                            InstanceIds=[instance['InstanceId']]
                        )
                        for reservation in ec2_response['Reservations']:
                            for ec2_instance in reservation['Instances']:
                                if ec2_instance['State']['Name'] != 'running':
                                    all_running = False
                                    break
                                    
                                # If verification is required, verify all instances
                                if verify and all_running:
                                    inst_verification = self.verify_asg_instance_state(
                                        instance['InstanceId'], 'running', status_check_level
                                    )
                                    if not inst_verification['passed']:
                                        all_verified = False
                                        self.logger.warning(f"Instance {instance['InstanceId']} verification failed: {inst_verification['summary']}")
                    
                    processes_resumed = False
                    state_cleaned = False
                    
                    # Only resume processes if all instances are running and verified (if required)
                    if all_running and (not verify or all_verified):
                        # Resume ASG processes
                        resume_result = self.resume_asg_processes(asg_name)
                        processes_resumed = (resume_result['Status'] == 'Success')
                        
                        # Clean up stored state
                        if processes_resumed:
                            cleanup_result = self.cleanup_asg_state(asg_name)
                            state_cleaned = (cleanup_result['Status'] == 'Success')
                    elif verify and not all_verified:
                        self.logger.warning(f"Not resuming ASG {asg_name} processes - some instances failed verification")
                    
                    result = {
                        'InstanceId': instance_id,
                        'ASGName': asg_name,
                        'PreviousState': instance_info['PreviousState']['Name'],
                        'CurrentState': instance_info['CurrentState']['Name'],
                        'Status': 'Success',
                        'ProcessesResumed': processes_resumed,
                        'StateCleanedUp': state_cleaned,
                        'AllInstancesRunning': all_running,
                        'Timestamp': datetime.now().isoformat()
                    }
                    
                    if verify:
                        result['AllInstancesVerified'] = all_verified
                        result['VerificationDetails'] = verification_result
                    
                    return result
                else:
                    result = {
                        'InstanceId': instance_id,
                        'ASGName': asg_name,
                        'PreviousState': instance_info['PreviousState']['Name'],
                        'CurrentState': instance_info['CurrentState']['Name'],
                        'Status': 'Success',
                        'ProcessesResumed': False,
                        'StateCleanedUp': False,
                        'Error': 'Could not retrieve ASG details',
                        'Timestamp': datetime.now().isoformat()
                    }
                    
                    if verify:
                        result['VerificationDetails'] = verification_result
                    
                    return result
                    
            except botocore.exceptions.ClientError as e:
                return {
                    'InstanceId': instance_id,
                    'ASGName': asg_name,
                    'Status': 'Failed',
                    'Error': f'Failed to start instance: {str(e)}',
                    'Timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error handling ASG instance start {instance_id}: {str(e)}")
            return {
                'InstanceId': instance_id,
                'ASGName': asg_name if 'asg_name' in locals() else None,
                'Status': 'Failed',
                'Error': str(e),
                'Timestamp': datetime.now().isoformat()
            }
    
    def is_asg_stopped(self, asg_name):
        """Check if ASG is in stopped state (has suspended processes).
        
        Args:
            asg_name (str): Name of the ASG
            
        Returns:
            bool: True if ASG appears to be stopped
        """
        try:
            response = self.asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                return False
                
            asg = response['AutoScalingGroups'][0]
            suspended_processes = [p['ProcessName'] for p in asg.get('SuspendedProcesses', [])]
            required_suspended = ['Launch', 'Terminate', 'HealthCheck', 'ReplaceUnhealthy']
            
            return all(process in suspended_processes for process in required_suspended)
            
        except botocore.exceptions.ClientError as e:
            self.logger.error(f"Error checking ASG state {asg_name}: {str(e)}")
            return False
    
    def verify_asg_instance_state(self, instance_id, expected_state, status_check_level='state', timeout=300, check_interval=10):
        """Verify ASG-managed instance has reached the expected state with optional comprehensive status checks.
        
        This method provides the same verification levels as regular EC2 instances:
        
        1. 'state' (default): Basic instance state verification (running/stopped)
        2. 'system': State + AWS system status checks (running instances only)
        3. 'full': State + system + instance status + network reachability (running instances only)
        
        For stopped instances, all levels default to state-only verification since
        AWS status checks are not applicable to stopped instances.
        
        Args:
            instance_id (str): Instance ID to verify
            expected_state (str): Expected instance state ('running' or 'stopped')
            status_check_level (str): Verification depth - 'state', 'system', or 'full'
            timeout (int): Maximum time to wait for verification in seconds (default: 300)
            check_interval (int): Interval between verification attempts in seconds (default: 10)
            
        Returns:
            dict: Verification result with detailed status information
        """
        self.logger.info(f"Verifying ASG instance {instance_id} with {status_check_level} level checks, expected state: {expected_state}")
        
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                # Get instance details
                response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
                
                if not response['Reservations']:
                    return {
                        'passed': False,
                        'summary': 'Instance not found',
                        'details': {'state_check': {'passed': False, 'value': 'not_found', 'expected': expected_state}}
                    }
                
                instance = response['Reservations'][0]['Instances'][0]
                current_state = instance['State']['Name']
                
                # Get status checks if needed
                status_response = None
                if status_check_level in ['system', 'full'] and expected_state == 'running':
                    try:
                        status_response = self.ec2_client.describe_instance_status(
                            InstanceIds=[instance_id],
                            IncludeAllInstances=True
                        )
                    except botocore.exceptions.ClientError as e:
                        self.logger.warning(f"Could not get instance status for ASG instance {instance_id}: {str(e)}")
                
                # Perform comprehensive verification using same logic as regular EC2 instances
                verification_result = self._verify_instance_comprehensive(
                    instance, expected_state, status_check_level, status_response
                )
                
                if verification_result['passed']:
                    self.logger.info(f"ASG instance {instance_id} verification passed: {verification_result['summary']}")
                    return verification_result
                else:
                    self.logger.debug(f"ASG instance {instance_id} verification pending: {verification_result['summary']}")
                    
                time.sleep(check_interval)
                
            except botocore.exceptions.ClientError as e:
                self.logger.error(f"Error verifying ASG instance state {instance_id}: {str(e)}")
                return {
                    'passed': False,
                    'summary': f'API Error: {str(e)}',
                    'details': {'api_error': str(e)}
                }
        
        # Timeout occurred
        self.logger.warning(f"ASG instance {instance_id} did not pass {status_check_level} verification within timeout")
        return {
            'passed': False,
            'summary': f'Timeout after {timeout}s',
            'details': {'timeout': True, 'timeout_seconds': timeout}
        }
    
    def _verify_instance_comprehensive(self, instance, expected_state, status_check_level, status_response):
        """Perform comprehensive verification of an ASG instance based on the check level.
        
        Uses the same verification logic as regular EC2 instances for consistency.
        
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