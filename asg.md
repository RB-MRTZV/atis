# src/asg_operations.py
import boto3
import logging
import botocore.exceptions
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
        
    def get_asg_name_from_instance(self, instance_tags):
        """Get ASG name from instance tags using AWS built-in tag.
        
        Args:
            instance_tags (dict): Dictionary of instance tags
            
        Returns:
            str: ASG name if found, None otherwise
        """
        return instance_tags.get('aws:autoscaling:groupname')
    
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
            # Check if processes are already suspended
            response = self.asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                return {
                    'ASGName': asg_name,
                    'SuspendedProcesses': processes,
                    'Status': 'Failed',
                    'Error': f'ASG {asg_name} not found',
                    'Timestamp': datetime.now().isoformat()
                }
            
            asg_data = response['AutoScalingGroups'][0]
            already_suspended = [p['ProcessName'] for p in asg_data.get('SuspendedProcesses', [])]
            
            # Only suspend processes that aren't already suspended
            processes_to_suspend = [p for p in processes if p not in already_suspended]
            
            if processes_to_suspend:
                self.logger.info(f"Suspending processes {processes_to_suspend} for ASG {asg_name}")
                
                self.asg_client.suspend_processes(
                    AutoScalingGroupName=asg_name,
                    ScalingProcesses=processes_to_suspend
                )
                
                return {
                    'ASGName': asg_name,
                    'SuspendedProcesses': processes_to_suspend,
                    'AlreadySuspended': already_suspended,
                    'Status': 'Success',
                    'Timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.info(f"All required processes already suspended for ASG {asg_name}")
                return {
                    'ASGName': asg_name,
                    'SuspendedProcesses': [],
                    'AlreadySuspended': already_suspended,
                    'Status': 'Success',
                    'Message': 'Processes already suspended',
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
            # Check current suspended processes
            response = self.asg_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[asg_name]
            )
            
            if not response['AutoScalingGroups']:
                return {
                    'ASGName': asg_name,
                    'ResumedProcesses': processes,
                    'Status': 'Failed',
                    'Error': f'ASG {asg_name} not found',
                    'Timestamp': datetime.now().isoformat()
                }
            
            asg_data = response['AutoScalingGroups'][0]
            currently_suspended = [p['ProcessName'] for p in asg_data.get('SuspendedProcesses', [])]
            
            # Only resume processes that are currently suspended
            processes_to_resume = [p for p in processes if p in currently_suspended]
            
            if processes_to_resume:
                self.logger.info(f"Resuming processes {processes_to_resume} for ASG {asg_name}")
                
                self.asg_client.resume_processes(
                    AutoScalingGroupName=asg_name,
                    ScalingProcesses=processes_to_resume
                )
                
                return {
                    'ASGName': asg_name,
                    'ResumedProcesses': processes_to_resume,
                    'Status': 'Success',
                    'Timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.info(f"No processes to resume for ASG {asg_name}")
                return {
                    'ASGName': asg_name,
                    'ResumedProcesses': [],
                    'Status': 'Success',
                    'Message': 'No processes to resume',
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
    
    def handle_asg_instance_stop(self, instance_id, instance_tags):
        """Handle stopping an ASG-managed instance (suspend processes first).
        
        Args:
            instance_id (str): Instance ID to stop
            instance_tags (dict): Dictionary of instance tags
            
        Returns:
            dict: Result of operation
        """
        try:
            # Get ASG name from AWS built-in tag
            asg_name = self.get_asg_name_from_instance(instance_tags)
            if not asg_name:
                return {
                    'InstanceId': instance_id,
                    'ASGName': None,
                    'Status': 'Failed',
                    'Error': 'No ASG name found in instance tags',
                    'Timestamp': datetime.now().isoformat()
                }
            
            self.logger.info(f"Handling ASG-managed instance {instance_id} in ASG {asg_name}")
            
            # Suspend ASG processes (this handles checking if already suspended)
            suspend_result = self.suspend_asg_processes(asg_name)
            
            if suspend_result['Status'] != 'Success':
                return {
                    'InstanceId': instance_id,
                    'ASGName': asg_name,
                    'Status': 'Failed',
                    'Error': f"Failed to suspend ASG processes: {suspend_result.get('Error', 'Unknown error')}",
                    'Timestamp': datetime.now().isoformat()
                }
            
            # Stop the instance
            try:
                response = self.ec2_client.stop_instances(InstanceIds=[instance_id])
                instance_info = response['StoppingInstances'][0]
                
                return {
                    'InstanceId': instance_id,
                    'ASGName': asg_name,
                    'PreviousState': instance_info['PreviousState']['Name'],
                    'CurrentState': instance_info['CurrentState']['Name'],
                    'Status': 'Success',
                    'ProcessesSuspended': len(suspend_result.get('SuspendedProcesses', [])) > 0,
                    'SuspendDetails': suspend_result,
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
                
        except Exception as e:
            self.logger.error(f"Error handling ASG instance stop {instance_id}: {str(e)}")
            return {
                'InstanceId': instance_id,
                'ASGName': asg_name if 'asg_name' in locals() else None,
                'Status': 'Failed',
                'Error': str(e),
                'Timestamp': datetime.now().isoformat()
            }
    
    def handle_asg_instance_start(self, instance_id, instance_tags):
        """Handle starting an ASG-managed instance and resume processes if needed.
        
        Args:
            instance_id (str): Instance ID to start
            instance_tags (dict): Dictionary of instance tags
            
        Returns:
            dict: Result of operation
        """
        try:
            # Get ASG name from AWS built-in tag
            asg_name = self.get_asg_name_from_instance(instance_tags)
            if not asg_name:
                return {
                    'InstanceId': instance_id,
                    'ASGName': None,
                    'Status': 'Failed',
                    'Error': 'No ASG name found in instance tags',
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
                
                # Check if we should resume ASG processes
                # We'll resume if there are any suspended processes that we typically manage
                resume_result = self.resume_asg_processes(asg_name)
                
                return {
                    'InstanceId': instance_id,
                    'ASGName': asg_name,
                    'PreviousState': instance_info['PreviousState']['Name'],
                    'CurrentState': instance_info['CurrentState']['Name'],
                    'Status': 'Success',
                    'ProcessesResumed': len(resume_result.get('ResumedProcesses', [])) > 0,
                    'ResumeDetails': resume_result,
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