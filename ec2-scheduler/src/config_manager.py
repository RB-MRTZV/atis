# src/config_manager.py
import os
import json
import configparser
import logging
from pathlib import Path

class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass

class ConfigManager:
    """Manages configuration for the EC2 scheduler."""
    
    def __init__(self, config_file="ec2-scheduler/config/config.ini", accounts_file="ec2-scheduler/config/accounts.json"):
        """Initialize the configuration manager.
        
        Args:
            config_file (str): Path to the config.ini file
            accounts_file (str): Path to the accounts.json file
        """
        self.logger = logging.getLogger(__name__)
        self.config_file = config_file
        self.accounts_file = accounts_file
        self.config = None
        self.accounts = []
        self.load_config()
        self.load_accounts()
        
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
            
    def load_accounts(self):
        """Load accounts from accounts file or environment."""
        try:
            # First check if accounts are provided in environment
            accounts_env = os.environ.get('AWS_ACCOUNTS')
            if accounts_env:
                try:
                    self.accounts = json.loads(accounts_env)
                    self.logger.info(f"Loaded {len(self.accounts)} accounts from environment")
                    return
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse AWS_ACCOUNTS environment variable, falling back to file")
            
            # Check if accounts file exists, if not create with placeholder
            if not Path(self.accounts_file).exists():
                self.logger.warning(f"Accounts file {self.accounts_file} not found, creating placeholder")
                os.makedirs(os.path.dirname(self.accounts_file), exist_ok=True)
                
                placeholder_accounts = {
                    "accounts": [
                        {
                            "name": "example",
                            "account_id": "123456789012"
                        }
                    ]
                }
                
                with open(self.accounts_file, 'w') as f:
                    json.dump(placeholder_accounts, f, indent=2)
                    
                self.accounts = placeholder_accounts['accounts']
            else:
                with open(self.accounts_file, 'r') as f:
                    self.accounts = json.load(f).get('accounts', [])
                    
            self.logger.info(f"Loaded {len(self.accounts)} accounts from file")
                
        except Exception as e:
            self.logger.error(f"Failed to load accounts: {str(e)}")
            raise ConfigurationError(f"Failed to load accounts: {str(e)}")
            
    def get_accounts(self, account_names=None):
        """Get accounts to process.
        
        Args:
            account_names (list): Optional list of account names to filter by
            
        Returns:
            list: List of account dictionaries
        """
        if not account_names:
            return self.accounts
            
        filtered_accounts = [acc for acc in self.accounts if acc['name'] in account_names]
        if not filtered_accounts:
            self.logger.warning(f"No accounts found matching {account_names}")
        return filtered_accounts
        
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