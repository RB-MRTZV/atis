# tests/test_reporting.py
import os
import json
import pytest
import tempfile
from unittest.mock import patch, mock_open
from src.reporting import Reporter, ReportingError

class TestReporter:
    
    def test_add_result(self):
        """Test adding result to the reporter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = Reporter(tmpdir)
            
            reporter.add_result(
                account='test-account',
                region='us-west-2',
                instance_id='i-1234567890abcdef0',
                instance_name='web-server',
                previous_state='running',
                new_state='stopped',
                action='stop',
                timestamp='2025-05-21T12:34:56',
                status='Success'
            )
            
            assert len(reporter.results) == 1
            assert reporter.results[0]['Account'] == 'test-account'
            assert reporter.results[0]['InstanceId'] == 'i-1234567890abcdef0'
            assert reporter.results[0]['Status'] == 'Success'
            assert reporter.results[0]['Error'] == ''
            
    def test_generate_csv_report(self):
        """Test generating CSV report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = Reporter(tmpdir)
            
            # Add some results
            reporter.add_result(
                account='test-account',
                region='us-west-2',
                instance_id='i-1234',
                instance_name='web-server',
                previous_state='running',
                new_state='stopped',
                action='stop',
                timestamp='2025-05-21T12:34:56',
                status='Success'
            )
            
            reporter.add_result(
                account='test-account',
                region='us-west-2',
                instance_id='i-5678',
                instance_name='db-server',
                previous_state='stopped',
                new_state='stopped',
                action='start',
                timestamp='2025-05-21T12:34:57',
                status='Failed',
                error='Instance in invalid state'
            )
            
            # Generate report
            csv_file = reporter.generate_csv_report()
            
            # Check file exists and has content
            assert os.path.exists(csv_file)
            
            with open(csv_file, 'r') as f:
                content = f.read()
                assert 'Account,Region,InstanceId,Name,PreviousState,NewState,Action,Timestamp,Status,Error' in content
                assert 'test-account,us-west-2,i-1234,web-server,running,stopped,stop,2025-05-21T12:34:56,Success,' in content
                assert 'test-account,us-west-2,i-5678,db-server,stopped,stopped,start,2025-05-21T12:34:57,Failed,Instance in invalid state' in content
                
    def test_generate_summary(self):
        """Test generating summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = Reporter(tmpdir)
            
            # Add some results
            reporter.add_result(
                account='prod',
                region='us-west-2',
                instance_id='i-1234',
                instance_name='web-server',
                previous_state='running',
                new_state='stopped',
                action='stop',
                timestamp='2025-05-21T12:34:56',
                status='Success'
            )
            
            reporter.add_result(
                account='dev',
                region='us-west-2',
                instance_id='i-5678',
                instance_name='db-server',
                previous_state='stopped',
                new_state='stopped',
                action='start',
                timestamp='2025-05-21T12:34:57',
                status='Failed',
                error='Instance in invalid state'
            )
            
            reporter.add_result(
                account='prod',
                region='eu-central-1',
                instance_id='i-abcd',
                instance_name='api-server',
                previous_state='stopped',
                new_state='running',
                action='start',
                timestamp='2025-05-21T12:34:58',
                status='Success'
            )
            
            # Generate summary
            summary = reporter.generate_summary()
            
            # Check content
            assert 'Total instances processed: 3' in summary
            assert 'Successful operations: 2' in summary
            assert 'Failed operations: 1' in summary
            assert 'stop: 1 total, 1 successful, 0 failed' in summary
            assert 'start: 2 total, 1 successful, 1 failed' in summary
            assert 'prod: 2 total, 2 successful, 0 failed' in summary
            assert 'dev: 1 total, 0 successful, 1 failed' in summary