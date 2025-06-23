import argparse
import logging
import os
import sys
from datetime import datetime

from config_manager import ConfigManager
from eks_operations import EKSOperations, EKSOperationError
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
    parser = argparse.ArgumentParser(description='EKS Cluster Scheduler')
    
    parser.add_argument('--action', choices=['start', 'stop'], required=True,
                        help='Action to perform on cluster (scale up/down managed node groups)')
    parser.add_argument('--cluster', required=True,
                        help='EKS cluster name to process')
    parser.add_argument('--min-nodes', type=int, default=1,
                        help='Minimum number of nodes when scaling up (default: 1)')
    parser.add_argument('--region', help='AWS region (defaults to config)')
    parser.add_argument('--account', help='Account name to process')
    parser.add_argument('--dry-run', action='store_true', help='Simulate actions without executing')
    parser.add_argument('--notify-only', action='store_true', help='Send notification without performing actions')
    
    return parser.parse_args()

def process_eks_cluster(eks_ops, cluster_name, min_nodes, action, args, account, region, reporter):
    """Process a single EKS cluster.
    
    Args:
        eks_ops: EKSOperations instance
        cluster_name: Name of cluster to process
        min_nodes: Minimum number of nodes for scaling up
        action: Action to perform (start/stop)
        args: Command line arguments
        account: Account information
        region: AWS region
        reporter: Reporter instance
        
    Returns:
        int: Number of node groups processed
    """
    logger = logging.getLogger(__name__)
    account_name = account['name'] if account else 'default'
    
    logger.info(f"Processing cluster {cluster_name} in account {account_name}")
    
    # Execute the requested action (dry-run is handled in EKSOperations)
    if not args.notify_only:
        try:
            if action == 'start':
                results = eks_ops.scale_up_cluster(cluster_name, min_nodes)
                expected_state = 'scaled_up'
            else:  # stop
                results = eks_ops.scale_down_cluster(cluster_name)
                expected_state = 'scaled_down'
            
            # Record results
            node_groups_processed = 0
            for result in results:
                reporter.add_result(
                    account=account_name,
                    region=region,
                    cluster_name=cluster_name,
                    previous_state=result.get('PreviousState', 'Unknown'),
                    new_state=result.get('CurrentState', expected_state),
                    action=action,
                    timestamp=result['Timestamp'],
                    status=result['Status'],
                    error=result.get('Error', '')
                )
                node_groups_processed += 1
                
            return node_groups_processed
                
        except EKSOperationError as e:
            logger.error(f"Error processing cluster {cluster_name}: {str(e)}")
            reporter.add_result(
                account=account_name,
                region=region,
                cluster_name=cluster_name,
                previous_state='Unknown',
                new_state='Unknown',
                action=action,
                timestamp=datetime.now().isoformat(),
                status='Failed',
                error=str(e)
            )
            return 0
    else:
        # Notify only mode
        logger.info(f"Notify only mode, would {action} cluster {cluster_name}")
        
        # Add entry for notify only
        reporter.add_result(
            account=account_name,
            region=region,
            cluster_name=cluster_name,
            previous_state='Unknown',
            new_state='[NOTIFY ONLY]',
            action=action,
            timestamp=datetime.now().isoformat(),
            status='Simulated'
        )
        return 1

def main():
    """Main entry point."""
    try:
        # Parse arguments first
        args = parse_args()
        
        # Load configuration with improved error handling
        try:
            config_manager = ConfigManager()  # Now uses automatic path detection
        except Exception as e:
            print(f"Failed to load configuration: {str(e)}")
            return 1
        
        # Set up logging using config
        log_level = config_manager.get('logging', 'level', fallback='INFO')
        log_file = config_manager.get('logging', 'file', fallback=None)
        setup_logging(log_level, log_file)
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting EKS Scheduler - action: {args.action}, cluster: {args.cluster}")
        
        # Get AWS region
        region = args.region or config_manager.get('aws', 'region', fallback='us-west-2')
        logger.info(f"Using AWS region: {region}")
        
        # Get account to process
        account = None
        if args.account:
            account = config_manager.get_account_by_name(args.account)
            if not account:
                logger.error(f"Account '{args.account}' not found in configuration")
                return 1
        else:
            # Use first account as default
            accounts = config_manager.get_accounts()
            account = accounts[0] if accounts else None
            
        if account:
            logger.info(f"Processing account: {account['name']}")
        else:
            logger.warning("No account configuration found, using defaults")
        
        # Log min nodes setting for scale up
        if args.action == 'start':
            logger.info(f"Minimum nodes for scale up: {args.min_nodes}")
        
        # Initialize reporter
        reporter = Reporter()
        
        # Initialize EKS operations
        eks_ops = EKSOperations(region, config_manager=config_manager, dry_run=args.dry_run)
        
        # Process the cluster
        total_processed = process_eks_cluster(
            eks_ops, args.cluster, args.min_nodes, args.action, args, account, region, reporter
        )
        
        logger.info(f"Processed {total_processed} node groups in cluster {args.cluster}")
                
        # Generate reports
        if reporter.results:
            logger.info("Generating reports")
            
            csv_report = reporter.generate_csv_report()
            json_report = reporter.generate_json_report()
            table_report = reporter.generate_table_report()
            
            logger.info(f"Reports generated: {csv_report}, {json_report}")
            
            # Send notification
            sns_topic_arn = config_manager.get('sns', 'topic_arn', fallback=None)
            if sns_topic_arn:
                try:
                    notifier = SNSNotifier(sns_topic_arn, region)
                    subject = f"EKS Scheduler Report - {args.action.upper()} - {args.cluster} - {datetime.now().strftime('%Y-%m-%d')}"
                    message = f"EKS Scheduler completed for cluster {args.cluster}.\n\n{table_report}"
                    notifier.send_notification(subject, message)
                    logger.info("Notification sent")
                except Exception as e:
                    logger.error(f"Failed to send notification: {str(e)}")
            else:
                logger.warning("No SNS topic ARN configured, skipping notification")
        else:
            logger.info("No resources processed, no reports generated")
            
        logger.info("EKS Scheduler completed successfully")
        return 0
        
    except Exception as e:
        # Set up basic logging if it failed earlier
        if 'logger' not in locals():
            logging.basicConfig(level=logging.ERROR)
            logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error: {str(e)}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main()) 