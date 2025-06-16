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
    
    def handle_asg_instance_stop(self, instance_id):
        """Handle stopping an ASG-managed instance (suspend processes first).
        
        Args:
            instance_id (str): Instance ID to stop
            
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
                    
                    return {
                        'InstanceId': instance_id,
                        'ASGName': asg_name,
                        'PreviousState': instance_info['PreviousState']['Name'],
                        'CurrentState': instance_info['CurrentState']['Name'],
                        'Status': 'Success',
                        'ProcessesSuspended': True,
                        'Timestamp': datetime.now().isoformat()
                    }
                    
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
    
    def handle_asg_instance_start(self, instance_id):
        """Handle starting an ASG-managed instance and resume processes if needed.
        
        Args:
            instance_id (str): Instance ID to start
            
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
                
                # Check if this is the last instance in the ASG to start
                # If so, we can resume processes and clean up state
                asg_response = self.asg_client.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[asg_name]
                )
                
                if asg_response['AutoScalingGroups']:
                    asg_data = asg_response['AutoScalingGroups'][0]
                    
                    # Check if all instances in ASG are running
                    all_running = True
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
                    
                    processes_resumed = False
                    state_cleaned = False
                    
                    if all_running:
                        # Resume ASG processes
                        resume_result = self.resume_asg_processes(asg_name)
                        processes_resumed = (resume_result['Status'] == 'Success')
                        
                        # Clean up stored state
                        if processes_resumed:
                            cleanup_result = self.cleanup_asg_state(asg_name)
                            state_cleaned = (cleanup_result['Status'] == 'Success')
                    
                    return {
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
                else:
                    return {
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