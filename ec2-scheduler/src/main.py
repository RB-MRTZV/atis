# src/main.py
import argparse
import logging
import os
import sys
from datetime import datetime

from config_manager import ConfigManager, ConfigurationError
from ec2_operations import EC2Operations, InstanceOperationError
from asg_operations import ASGOperations, ASGOperationError
from reporting import Reporter, ReportingError
from sns_notifier import SNSNotifier, NotificationError

def setup_logging(log_level='INFO', log_file=None):
    """Set up logging.
    
    Args:
        log_level (str): Logging level
        log_file (str): Log file path
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
        
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)
    
    # Set up file handler if log file provided
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)
        
def parse_args():
    """Parse command line arguments.
    
    Returns:
        Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='EC2 Instance Scheduler with ASG Support')
    
    parser.add_argument('--action', choices=['start', 'stop'], required=True,
                        help='Action to perform on instances')
    parser.add_argument('--region', help='AWS region (defaults to config)')
    parser.add_argument('--accounts', help='Comma-separated list of accounts to process')
    parser.add_argument('--dry-run', action='store_true', help='Simulate actions without executing')
    parser.add_argument('--verify', action='store_true', help='Verify instance states after operation')
    parser.add_argument('--notify-only', action='store_true', help='Send notification without performing actions')
    parser.add_argument('--force', action='store_true', help='Force stop instances (only applies to stop action)')
    
    return parser.parse_args()

def process_ec2_instances(ec2_ops, asg_ops, tag_key, tag_value, asg_tag_key, asg_tag_value, action, args, account, region, reporter):
    """Process EC2 instances for an account, handling ASG-managed instances appropriately.
    
    Args:
        ec2_ops: EC2Operations instance
        asg_ops: ASGOperations instance  
        tag_key: Tag key to filter on
        tag_value: Tag value to filter on
        asg_tag_key: Tag key to identify ASG-managed instances
        asg_tag_value: Tag value to identify ASG-managed instances
        action: Action to perform (start/stop)
        args: Command line arguments
        account: Account information
        region: AWS region
        reporter: Reporter instance
        
    Returns:
        int: Number of instances processed
    """
    logger = logging.getLogger(__name__)
    account_name = account['name']
    
    # Find instances with the specified tag, identifying ASG-managed ones
    tagged_instances = ec2_ops.find_tagged_instances(tag_key, tag_value, asg_tag_key, asg_tag_value)
    
    if not tagged_instances:
        logger.info(f"No tagged EC2 instances found in account {account_name}")
        return 0
        
    # Separate regular instances from ASG-managed instances
    regular_instances = [i for i in tagged_instances if not i['IsASGManaged']]
    asg_managed_instances = [i for i in tagged_instances if i['IsASGManaged']]
    
    logger.info(f"Found {len(tagged_instances)} tagged instances in account {account_name}: "
                f"{len(regular_instances)} regular, {len(asg_managed_instances)} ASG-managed")
    
    # Execute the requested action
    if not args.notify_only and not args.dry_run:
        
        # Process regular EC2 instances
        if regular_instances:
            regular_instance_ids = [instance['InstanceId'] for instance in regular_instances]
            
            if action == 'start':
                results = ec2_ops.start_instances(regular_instance_ids)
                expected_state = 'running'
            else:  # stop
                results = ec2_ops.stop_instances(regular_instance_ids, args.force)
                expected_state = 'stopped'
                
            # Record successful operations
            for instance in results['succeeded']:
                instance_id = instance['InstanceId']
                instance_obj = next((i for i in regular_instances if i['InstanceId'] == instance_id), {})
                instance_name = instance_obj.get('Name', '')
                environment_info = f"Environment: {instance_obj.get('Environment', 'Unknown')}"
                
                reporter.add_result(
                    resource_type='EC2',
                    account=account_name,
                    region=region,
                    resource_id=instance_id,
                    resource_name=instance_name,
                    previous_state=instance['PreviousState'],
                    new_state=instance['CurrentState'],
                    action=action,
                    timestamp=instance['Timestamp'],
                    status='Success',
                    details=environment_info
                )
                
            # Record failed operations
            for instance in results['failed']:
                instance_id = instance['InstanceId']
                instance_obj = next((i for i in regular_instances if i['InstanceId'] == instance_id), {})
                instance_name = instance_obj.get('Name', '')
                environment_info = f"Environment: {instance_obj.get('Environment', 'Unknown')}"
                
                reporter.add_result(
                    resource_type='EC2',
                    account=account_name,
                    region=region,
                    resource_id=instance_id,
                    resource_name=instance_name,
                    previous_state='Unknown',
                    new_state='Unknown',
                    action=action,
                    timestamp=instance['Timestamp'],
                    status='Failed',
                    error=instance.get('Error', 'Unknown error'),
                    details=environment_info
                )
                
            # Verify regular instance states if requested
            if args.verify:
                logger.info(f"Verifying regular EC2 instance states in account {account_name}")
                
                # Only verify instances that were successfully started/stopped
                instances_to_verify = [{'InstanceId': i['InstanceId']} for i in results['succeeded']]
                verify_results = ec2_ops.verify_instance_states(instances_to_verify, expected_state)
                
                # Update report with verification results
                for instance in verify_results['failed']:
                    instance_id = instance['InstanceId']
                    
                    # Find and update the existing result
                    for result in reporter.results:
                        if (result['ResourceId'] == instance_id and 
                            result['Account'] == account_name and 
                            result['ResourceType'] == 'EC2' and
                            result['Status'] == 'Success'):
                            
                            result['Status'] = 'Failed'
                            result['Error'] = instance.get('Error', 'Verification failed')
                            result['Timestamp'] = instance['Timestamp']
                            break
        
        # Process ASG-managed instances
        if asg_managed_instances:
            logger.info(f"Processing {len(asg_managed_instances)} ASG-managed instances")
            
            for instance in asg_managed_instances:
                instance_id = instance['InstanceId']
                instance_name = instance['Name']
                
                try:
                    if action == 'start':
                        result = asg_ops.handle_asg_instance_start(instance_id)
                    else:  # stop
                        result = asg_ops.handle_asg_instance_stop(instance_id)
                    
                    # Prepare environment tag information for details
                    environment_info = f"Environment: {instance.get('Environment', 'Unknown')}"
                    
                    reporter.add_result(
                        resource_type='EC2',
                        account=account_name,
                        region=region,
                        resource_id=instance_id,
                        resource_name=instance_name,
                        previous_state=result.get('PreviousState', 'Unknown'),
                        new_state=result.get('CurrentState', 'Unknown'),
                        action=action,
                        timestamp=result['Timestamp'],
                        status=result['Status'],
                        error=result.get('Error', ''),
                        details=environment_info
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing ASG-managed instance {instance_id}: {str(e)}")
                    reporter.add_result(
                        resource_type='EC2-ASG',
                        account=account_name,
                        region=region,
                        resource_id=instance_id,
                        resource_name=instance_name,
                        previous_state='Unknown',
                        new_state='Unknown',
                        action=action,
                        timestamp=datetime.now().isoformat(),
                        status='Failed',
                        error=str(e)
                    )
    else:
        # Dry run or notify only mode
        logger.info(f"Dry run or notify only mode, would {action} "
                    f"{len(tagged_instances)} instances in account {account_name}")
        
        # Add entries for dry run
        for instance in tagged_instances:
            resource_type = 'EC2-ASG' if instance['IsASGManaged'] else 'EC2'
            environment_info = f"Environment: {instance.get('Environment', 'Unknown')}"
            if instance['IsASGManaged']:
                environment_info += ", ASG-managed"
            
            reporter.add_result(
                resource_type=resource_type,
                account=account_name,
                region=region,
                resource_id=instance['InstanceId'],
                resource_name=instance['Name'],
                previous_state=instance['State'],
                new_state='[DRY RUN]',
                action=action,
                timestamp=datetime.now().isoformat(),
                status='Simulated',
                details=environment_info
            )
    
    return len(tagged_instances)

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        log_config = config_manager.get_log_config()
        setup_logging(log_config['level'], log_config['file'])
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting EC2 Scheduler with ASG support - action: {args.action}")
        
        # Get AWS region
        region = config_manager.get_region(args.region)
        logger.info(f"Using AWS region: {region}")
        
        # Get accounts to process
        account_names = args.accounts.split(',') if args.accounts else None
        accounts = config_manager.get_accounts(account_names)
        logger.info(f"Processing {len(accounts)} accounts")
        
        # Get tag configuration
        tag_key, tag_value = config_manager.get_tag_config()
        logger.info(f"Using tag filter: {tag_key}:{tag_value}")
        
        # Get ASG tag configuration
        asg_tag_key, asg_tag_value = config_manager.get_asg_tag_config()
        logger.info(f"Using ASG identification tag: {asg_tag_key}:{asg_tag_value}")
        
        # Initialize reporter
        reporter = Reporter()
        
        # Process each account
        for account in accounts:
            account_name = account['name']
            account_id = account['account_id']
            
            logger.info(f"Processing account: {account_name} ({account_id})")
            
            try:
                # Initialize operations
                ec2_ops = EC2Operations(region)
                asg_ops = ASGOperations(region)
                
                # Process instances (both regular and ASG-managed)
                total_processed = process_ec2_instances(
                    ec2_ops, asg_ops, tag_key, tag_value, asg_tag_key, asg_tag_value,
                    args.action, args, account, region, reporter
                )
                
                logger.info(f"Processed {total_processed} instances in account {account_name}")
                
            except Exception as e:
                logger.error(f"Error processing account {account_name}: {str(e)}")
                continue
                
        # Generate reports
        if reporter.results:
            logger.info("Generating reports")
            
            csv_report = reporter.generate_csv_report()
            json_report = reporter.generate_json_report()
            table_report = reporter.generate_table_report()
            html_report = reporter.generate_html_report()
            
            logger.info(f"Reports generated: {csv_report}, {json_report}, {html_report}")
            
            # Send notification
            sns_topic_arn = config_manager.get_sns_topic_arn()
            if sns_topic_arn:
                try:
                    notifier = SNSNotifier(sns_topic_arn, region)
                    
                    # Generate summary for notification
                    summary = f"EC2 Scheduler completed for {args.target}.\nTotal resources processed: {total_processed}"
                    if args.dry_run:
                        summary += "\n[DRY RUN] No actual changes were made."
                    
                    # Send notification using enhanced method
                    success = notifier.send_success_notification(args.action, summary, table_report)
                    if success:
                        logger.info("Notification sent successfully")
                    else:
                        logger.warning("Notification sending returned false")
                        
                except Exception as e:
                    logger.error(f"Failed to send notification: {str(e)}")
                    # Send failure notification
                    try:
                        notifier = SNSNotifier(sns_topic_arn, region)
                        notifier.send_failure_notification(args.action, str(e))
                    except:
                        pass  # Don't fail if failure notification also fails
            else:
                logger.warning("No SNS topic ARN configured, skipping notification")
        else:
            logger.info("No resources processed, no reports generated")
            
        logger.info("EC2 Scheduler completed successfully")
        return 0
        
    except ConfigurationError as e:
        logging.error(f"Configuration error: {str(e)}")
        return 1
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())