# src/config_manager.py
import os
import configparser
import logging
from pathlib import Path

class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass

class ConfigManager:
    """Manages configuration for the EC2 scheduler."""
    
    def __init__(self, config_file="ec2-scheduler/config/config.ini"):
        """Initialize the configuration manager.
        
        Args:
            config_file (str): Path to the config.ini file
        """
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        self.config = None
        self.load_config()
        
    def load_config(self):
        """Load configuration from config file."""
        try:
            self.config = configparser.ConfigParser()
            
            # Check if config file exists, if not create with defaults
            if not Path(self.config_file).exists():
                self.logger.warning(f"Config file {self.config_file} not found, creating with defaults")
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                
                self.config['DEFAULT'] = {
                    'default_region': 'ap-southeast-2',
                    'tag_key': 'scheduled',
                    'tag_value': 'enabled',
                    'asg_tag_key': 'asg-managed',
                    'asg_tag_value': 'enabled',
                    'sns_topic_arn': os.environ.get('SNS_TOPIC_ARN', '')
                }
                
                self.config['LOGGING'] = {
                    'log_level': 'INFO',
                    'log_file': 'ec2-scheduler.log'
                }
                
                with open(self.config_file, 'w') as f:
                    self.config.write(f)
            else:
                self.config.read(self.config_file)
                
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
            
    def get_region(self, region=None):
        """Get the AWS region to use.
        
        Args:
            region (str): Optional region to override configuration
            
        Returns:
            str: AWS region
        """
        if region:
            return region
            
        env_region = os.environ.get('AWS_DEFAULT_REGION')
        if env_region:
            return env_region
            
        config_region = self.config.get('DEFAULT', 'default_region', fallback='ap-southeast-2')
        return config_region
        
    def get_tag_config(self):
        """Get the tag configuration.
        
        Returns:
            tuple: (tag_key, tag_value)
        """
        tag_key = self.config.get('DEFAULT', 'tag_key', fallback='scheduled')
        tag_value = self.config.get('DEFAULT', 'tag_value', fallback='enabled')
        return tag_key, tag_value
    
    def get_asg_tag_config(self):
        """Get the ASG tag configuration.
        
        Returns:
            tuple: (asg_tag_key, asg_tag_value)
        """
        asg_tag_key = self.config.get('DEFAULT', 'asg_tag_key', fallback='asg-managed')
        asg_tag_value = self.config.get('DEFAULT', 'asg_tag_value', fallback='enabled')
        return asg_tag_key, asg_tag_value
        
    def get_sns_topic_arn(self):
        """Get the SNS topic ARN.
        
        Returns:
            str: SNS topic ARN
        """
        # First check environment
        sns_arn = os.environ.get('SNS_TOPIC_ARN')
        if sns_arn:
            return sns_arn
            
        # Then check config
        return self.config.get('DEFAULT', 'sns_topic_arn', fallback=None)
        
    def get_log_config(self):
        """Get logging configuration.
        
        Returns:
            dict: Logging configuration
        """
        return {
            'level': self.config.get('LOGGING', 'log_level', fallback='INFO'),
            'file': self.config.get('LOGGING', 'log_file', fallback='ec2-scheduler.log')
        }