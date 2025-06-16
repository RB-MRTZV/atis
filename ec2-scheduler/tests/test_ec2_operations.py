# tests/test_ec2_operations.py
import pytest
import boto3
import botocore.exceptions
from unittest.mock import patch, MagicMock
from src.ec2_operations import EC2Operations, InstanceOperationError

class TestEC2Operations:
    
    @patch('boto3.client')
    def test_find_tagged_instances(self, mock_client):
        """Test finding instances with tags."""
        # Mock EC2 response
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        
        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'State': {'Name': 'running'},
                            'Tags': [
                                {'Key': 'Name', 'Value': 'web-server'},
                                {'Key': 'scheduled', 'Value': 'enabled'}
                            ]
                        }
                    ]
                }
            ]
        }
        
        ec2_ops = EC2Operations('us-west-2')
        instances = ec2_ops.find_tagged_instances('scheduled', 'enabled')
        
        # Assert correct filter was passed
        mock_ec2.describe_instances.assert_called_with(
            Filters=[{'Name': 'tag:scheduled', 'Values': ['enabled']}]
        )
        
        # Check result
        assert len(instances) == 1
        assert instances[0]['InstanceId'] == 'i-1234567890abcdef0'
        assert instances[0]['State'] == 'running'
        assert instances[0]['Name'] == 'web-server'
        
    @patch('boto3.client')
    def test_start_instances_success(self, mock_client):
        """Test starting instances successfully."""
        # Mock EC2 response
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        
        mock_ec2.start_instances.return_value = {
            'StartingInstances': [
                {
                    'InstanceId': 'i-1234567890abcdef0',
                    'PreviousState': {'Name': 'stopped'},
                    'CurrentState': {'Name': 'pending'}
                }
            ]
        }
        
        ec2_ops = EC2Operations('us-west-2')
        results = ec2_ops.start_instances(['i-1234567890abcdef0'])
        
        # Check API was called correctly
        mock_ec2.start_instances.assert_called_with(InstanceIds=['i-1234567890abcdef0'])
        
        # Check results
        assert len(results['succeeded']) == 1
        assert results['succeeded'][0]['InstanceId'] == 'i-1234567890abcdef0'
        assert results['succeeded'][0]['PreviousState'] == 'stopped'
        assert results['succeeded'][0]['CurrentState'] == 'pending'
        assert len(results['failed']) == 0
        
    @patch('boto3.client')
    def test_start_instances_error(self, mock_client):
        """Test handling errors when starting instances."""
        # Mock EC2 response with error
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        
        mock_ec2.start_instances.side_effect = botocore.exceptions.ClientError(
            {'Error': {'Code': 'InvalidInstanceID.NotFound', 'Message': 'Instance not found'}},
            'StartInstances'
        )
        
        ec2_ops = EC2Operations('us-west-2')
        results = ec2_ops.start_instances(['i-1234567890abcdef0'])
        
        # Check results
        assert len(results['succeeded']) == 0
        assert len(results['failed']) == 1
        assert results['failed'][0]['InstanceId'] == 'i-1234567890abcdef0'
        assert 'Instance not found' in results['failed'][0]['Error']
        
    @patch('boto3.client')
    def test_stop_instances_success(self, mock_client):
        """Test stopping instances successfully."""
        # Mock EC2 response
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        
        mock_ec2.stop_instances.return_value = {
            'StoppingInstances': [
                {
                    'InstanceId': 'i-1234567890abcdef0',
                    'PreviousState': {'Name': 'running'},
                    'CurrentState': {'Name': 'stopping'}
                }
            ]
        }
        
        ec2_ops = EC2Operations('us-west-2')
        results = ec2_ops.stop_instances(['i-1234567890abcdef0'], force=False)
        
        # Check API was called correctly
        mock_ec2.stop_instances.assert_called_with(InstanceIds=['i-1234567890abcdef0'], Force=False)
        
        # Check results
        assert len(results['succeeded']) == 1
        assert results['succeeded'][0]['InstanceId'] == 'i-1234567890abcdef0'
        assert results['succeeded'][0]['PreviousState'] == 'running'
        assert results['succeeded'][0]['CurrentState'] == 'stopping'
        assert len(results['failed']) == 0
        
    @patch('boto3.client')
    def test_verify_instance_states(self, mock_client):
        """Test verifying instance states."""
        # Mock EC2 response
        mock_ec2 = MagicMock()
        mock_client.return_value = mock_ec2
        
        mock_ec2.describe_instances.return_value = {
            'Reservations': [
                {
                    'Instances': [
                        {
                            'InstanceId': 'i-1234567890abcdef0',
                            'State': {'Name': 'running'}
                        }
                    ]
                }
            ]
        }
        
        ec2_ops = EC2Operations('us-west-2')
        results = ec2_ops.verify_instance_states(
            [{'InstanceId': 'i-1234567890abcdef0'}], 
            'running',
            timeout=10,
            check_interval=1
        )
        
        # Check API was called correctly
        mock_ec2.describe_instances.assert_called_with(InstanceIds=['i-1234567890abcdef0'])
        
        # Check results
        assert len(results['verified']) == 1
        assert results['verified'][0]['InstanceId'] == 'i-1234567890abcdef0'
        assert results['verified'][0]['CurrentState'] == 'running'
        assert len(results['failed']) == 0