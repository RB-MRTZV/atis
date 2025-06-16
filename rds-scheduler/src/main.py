import argparse
import logging
import os
import sys
from datetime import datetime

from config_manager import ConfigManager
from rds_operations import RDSOperations, RDSOperationError
from reporting import Reporter, ReportingError
from sns_notifier import SNSNotifier

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
    parser = argparse.ArgumentParser(description='RDS and Aurora PostgreSQL Scheduler')
    
    parser.add_argument('--action', choices=['start', 'stop'], required=True,
                        help='Action to perform on RDS resources')
    parser.add_argument('--target', choices=['clusters', 'instances', 'both'], default='both',
                        help='Target resource type (Aurora clusters, RDS instances, or both)')
    parser.add_argument('--region', help='AWS region (defaults to config)')
    parser.add_argument('--account', help='Account name to process')
    parser.add_argument('--tag-key', help='Tag key to filter resources (defaults to config)')
    parser.add_argument('--tag-value', help='Tag value to filter resources (defaults to config)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate actions without executing')
    parser.add_argument('--verify', action='store_true', help='Verify resource states after action')
    parser.add_argument('--notify-only', action='store_true', help='Send notification without performing actions')
    
    return parser.parse_args()

def process_aurora_clusters(rds_ops, clusters, action, args, account, region, reporter):
    """Process Aurora PostgreSQL clusters.
    
    Args:
        rds_ops: RDSOperations instance
        clusters: List of clusters to process
        action: Action to perform (start/stop)
        args: Command line arguments
        account: Account information
        region: AWS region
        reporter: Reporter instance
        
    Returns:
        int: Number of clusters processed
    """
    logger = logging.getLogger(__name__)
    account_name = account['name'] if account else 'default'
    
    if not clusters:
        logger.info(f"No Aurora clusters found in account {account_name}")
        return 0
    
    cluster_ids = [cluster['DBClusterIdentifier'] for cluster in clusters]
    logger.info(f"Processing {len(cluster_ids)} Aurora clusters in account {account_name}: {cluster_ids}")
    
    # Execute the requested action (dry-run is handled in RDSOperations)
    if not args.notify_only:
        if action == 'start':
            results = rds_ops.start_clusters(cluster_ids)
        else:  # stop
            results = rds_ops.stop_clusters(cluster_ids)
        
        # Process results and add to reporter
        for result in results['succeeded']:
            reporter.add_result(
                account=account_name,
                region=region,
                resource_type='Aurora Cluster',
                resource_id=result['DBClusterIdentifier'],
                previous_state=result.get('PreviousStatus', 'unknown'),
                new_state=result.get('CurrentStatus', 'unknown'),
                action=action,
                timestamp=result['Timestamp'],
                status=result['Status'],
                error=None
            )
        
        for result in results['failed']:
            reporter.add_result(
                account=account_name,
                region=region,
                resource_type='Aurora Cluster',
                resource_id=result['DBClusterIdentifier'],
                previous_state='unknown',
                new_state='error',
                action=action,
                timestamp=result['Timestamp'],
                status=result['Status'],
                error=result.get('Error')
            )
        
        # Verify states if requested
        if args.verify and results['succeeded']:
            expected_state = 'available' if action == 'start' else 'stopped'
            succeeded_cluster_ids = [r['DBClusterIdentifier'] for r in results['succeeded']]
            
            logger.info(f"Verifying cluster states, expecting: {expected_state}")
            verification_results = rds_ops.verify_cluster_states(succeeded_cluster_ids, expected_state)
            
            # Add verification results to reporter
            for result in verification_results['verified']:
                reporter.add_result(
                    account=account_name,
                    region=region,
                    resource_type='Aurora Cluster',
                    resource_id=result['DBClusterIdentifier'],
                    previous_state='transitioning',
                    new_state=result['CurrentStatus'],
                    action=f'{action}_verify',
                    timestamp=result['Timestamp'],
                    status='Verified',
                    error=None
                )
            
            for result in verification_results['failed']:
                reporter.add_result(
                    account=account_name,
                    region=region,
                    resource_type='Aurora Cluster',
                    resource_id=result['DBClusterIdentifier'],
                    previous_state='transitioning',
                    new_state='verification_failed',
                    action=f'{action}_verify',
                    timestamp=result['Timestamp'],
                    status='Failed',
                    error=result.get('Error')
                )
    
    return len(clusters)

def process_rds_instances(rds_ops, instances, action, args, account, region, reporter):
    """Process standalone RDS instances.
    
    Args:
        rds_ops: RDSOperations instance
        instances: List of instances to process
        action: Action to perform (start/stop)
        args: Command line arguments
        account: Account information
        region: AWS region
        reporter: Reporter instance
        
    Returns:
        int: Number of instances processed
    """
    logger = logging.getLogger(__name__)
    account_name = account['name'] if account else 'default'
    
    if not instances:
        logger.info(f"No RDS instances found in account {account_name}")
        return 0
    
    instance_ids = [instance['DBInstanceIdentifier'] for instance in instances]
    logger.info(f"Processing {len(instance_ids)} RDS instances in account {account_name}: {instance_ids}")
    
    # Execute the requested action (dry-run is handled in RDSOperations)
    if not args.notify_only:
        if action == 'start':
            results = rds_ops.start_instances(instance_ids)
        else:  # stop
            results = rds_ops.stop_instances(instance_ids)
        
        # Process results and add to reporter
        for result in results['succeeded']:
            reporter.add_result(
                account=account_name,
                region=region,
                resource_type='RDS Instance',
                resource_id=result['DBInstanceIdentifier'],
                previous_state=result.get('PreviousStatus', 'unknown'),
                new_state=result.get('CurrentStatus', 'unknown'),
                action=action,
                timestamp=result['Timestamp'],
                status=result['Status'],
                error=None
            )
        
        for result in results['failed']:
            reporter.add_result(
                account=account_name,
                region=region,
                resource_type='RDS Instance',
                resource_id=result['DBInstanceIdentifier'],
                previous_state='unknown',
                new_state='error',
                action=action,
                timestamp=result['Timestamp'],
                status=result['Status'],
                error=result.get('Error')
            )
        
        # Verify states if requested
        if args.verify and results['succeeded']:
            expected_state = 'available' if action == 'start' else 'stopped'
            succeeded_instance_ids = [r['DBInstanceIdentifier'] for r in results['succeeded']]
            
            logger.info(f"Verifying instance states, expecting: {expected_state}")
            verification_results = rds_ops.verify_instance_states(succeeded_instance_ids, expected_state)
            
            # Add verification results to reporter
            for result in verification_results['verified']:
                reporter.add_result(
                    account=account_name,
                    region=region,
                    resource_type='RDS Instance',
                    resource_id=result['DBInstanceIdentifier'],
                    previous_state='transitioning',
                    new_state=result['CurrentStatus'],
                    action=f'{action}_verify',
                    timestamp=result['Timestamp'],
                    status='Verified',
                    error=None
                )
            
            for result in verification_results['failed']:
                reporter.add_result(
                    account=account_name,
                    region=region,
                    resource_type='RDS Instance',
                    resource_id=result['DBInstanceIdentifier'],
                    previous_state='transitioning',
                    new_state='verification_failed',
                    action=f'{action}_verify',
                    timestamp=result['Timestamp'],
                    status='Failed',
                    error=result.get('Error')
                )
    
    return len(instances)

def main():
    """Main entry point."""
    try:
        # Parse arguments
        args = parse_args()
        
        # Load configuration with proper paths
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.ini')
        accounts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'accounts.json')
        
        config_manager = ConfigManager(config_file, accounts_file)
        
        # Set up logging with enhanced config
        log_config = config_manager.get_log_config()
        setup_logging(log_config['level'], log_config['file'])
        
        logger = logging.getLogger(__name__)
        logger.info("Starting RDS Scheduler")
        logger.info(f"Action: {args.action}, Target: {args.target}, Dry Run: {args.dry_run}")
        
        # Get configuration values using enhanced methods
        region = config_manager.get_region(args.region)
        tag_key, tag_value = config_manager.get_tag_config()
        
        # Override with command line arguments if provided
        if args.tag_key:
            tag_key = args.tag_key
        if args.tag_value:
            tag_value = args.tag_value
        
        logger.info(f"Using region: {region}, tag filter: {tag_key}={tag_value}")
        
        # Initialize components
        rds_ops = RDSOperations(region, dry_run=args.dry_run)
        reporter = Reporter()
        
        # Get accounts to process using enhanced method
        if args.account:
            accounts = config_manager.get_accounts([args.account])
        else:
            accounts = config_manager.get_accounts()
        
        if not accounts:
            logger.error(f"No accounts found to process")
            return 1
        
        total_processed = 0
        
        # Process each account
        for account in accounts:
            account_region = account.get('region', region)
            logger.info(f"Processing account: {account['name']} in region: {account_region}")
            
            # Update RDS operations for account region if different
            if account_region != region:
                rds_ops = RDSOperations(account_region, dry_run=args.dry_run)
            
            # Process Aurora clusters
            if args.target in ['clusters', 'both']:
                try:
                    clusters = rds_ops.find_tagged_clusters(tag_key, tag_value)
                    processed = process_aurora_clusters(rds_ops, clusters, args.action, args, account, account_region, reporter)
                    total_processed += processed
                except RDSOperationError as e:
                    logger.error(f"Error processing Aurora clusters in account {account['name']}: {str(e)}")
                    continue
            
            # Process standalone RDS instances
            if args.target in ['instances', 'both']:
                try:
                    instances = rds_ops.find_tagged_instances(tag_key, tag_value)
                    processed = process_rds_instances(rds_ops, instances, args.action, args, account, account_region, reporter)
                    total_processed += processed
                except RDSOperationError as e:
                    logger.error(f"Error processing RDS instances in account {account['name']}: {str(e)}")
                    continue
        
        logger.info(f"Total resources processed: {total_processed}")
        
        # Generate reports
        if reporter.results:
            logger.info("Generating reports")
            
            csv_report = reporter.generate_csv_report()
            json_report = reporter.generate_json_report()
            table_report = reporter.generate_table_report()
            html_report = reporter.generate_html_report()
            
            logger.info(f"Reports generated: {csv_report}, {json_report}, {html_report}")
            
            # Send notification using enhanced SNS notifier
            sns_topic_arn = config_manager.get_sns_topic_arn()
            if sns_topic_arn:
                try:
                    notifier = SNSNotifier(sns_topic_arn, region)
                    
                    # Generate summary for notification
                    summary = f"RDS Scheduler completed for {args.target}.\nTotal resources processed: {total_processed}"
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
            
        logger.info("RDS Scheduler completed successfully")
        return 0
        
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        
        # Try to send failure notification
        try:
            config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.ini')
            accounts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'accounts.json')
            config_manager = ConfigManager(config_file, accounts_file)
            
            sns_topic_arn = config_manager.get_sns_topic_arn()
            if sns_topic_arn:
                region = config_manager.get_region()
                notifier = SNSNotifier(sns_topic_arn, region)
                notifier.send_failure_notification(getattr(args, 'action', 'unknown'), str(e))
        except:
            pass  # Don't fail if failure notification also fails
            
        return 1

if __name__ == '__main__':
    sys.exit(main()) 