import boto3
import logging

class SNSNotifier:
    def __init__(self, topic_arn, region):
        self.logger = logging.getLogger(__name__)
        self.topic_arn = topic_arn
        self.sns_client = boto3.client('sns', region_name=region)

    def send_notification(self, subject, message):
        try:
            response = self.sns_client.publish(
                TopicArn=self.topic_arn,
                Subject=subject,
                Message=message
            )
            self.logger.info(f"SNS notification sent: {response['MessageId']}")
            return response
        except Exception as e:
            self.logger.error(f"Failed to send SNS notification: {str(e)}")
            return None 