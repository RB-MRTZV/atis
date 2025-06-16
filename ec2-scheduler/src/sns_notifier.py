# src/sns_notifier.py
import boto3
import logging
import json
from datetime import datetime

class NotificationError(Exception):
    """Exception raised for notification errors."""
    pass

class SNSNotifier:
    """Handles SNS notifications."""
    
    def __init__(self, topic_arn, region):
        """Initialize SNS notifier.
        
        Args:
            topic_arn (str): SNS topic ARN
            region (str): AWS region
        """
        self.logger = logging.getLogger(__name__)
        self.topic_arn = topic_arn
        self.region = region
        
        if not topic_arn:
            self.logger.warning("SNS topic ARN not provided, notifications will be skipped")
            return
            
        self.sns_client = boto3.client('sns', region_name=region)
        
    def send_notification(self, subject, message):
        """Send an SNS notification.
        
        Args:
            subject (str): Notification subject
            message (str): Notification message
            
        Returns:
            bool: Success or failure
        """
        if not self.topic_arn:
            self.logger.warning("No SNS topic ARN configured, skipping notification")
            return False
            
        try:
            self.logger.info(f"Sending SNS notification to {self.topic_arn}")
            
            response = self.sns_client.publish(
                TopicArn=self.topic_arn,
                Subject=subject,
                Message=message
            )
            
            message_id = response.get('MessageId')
            self.logger.info(f"Notification sent, MessageId: {message_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {str(e)}")
            raise NotificationError(f"Failed to send notification: {str(e)}")
            
    def format_email_report(self, summary, table_report):
        """Format a report for email.
        
        Args:
            summary (str): Summary text
            table_report (str): Tabular report
            
        Returns:
            str: Formatted email message
        """
        return f"""
EC2 Scheduler Report

{summary}

Detailed Results:
{table_report}

This is an automated message from the EC2 Scheduler.
        """
