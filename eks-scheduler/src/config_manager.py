import configparser
import json
import os
import logging
from pathlib import Path

class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass

class ConfigManager:
    """Manages configuration for the EKS scheduler."""
    
    def __init__(self, config_file=None, accounts_file=None):
        """Initialize the configuration manager.
        
        Args:
            config_file (str, optional): Path to the config.ini file
            accounts_file (str, optional): Path to the accounts.json file
        """
        self.logger = logging.getLogger(__name__)
        
        # Set default paths - try relative to script location first
        script_dir = Path(__file__).parent
        
        if config_file is None:
            # Try multiple possible locations
            possible_configs = [
                script_dir / '../config/config.ini',
                'eks-scheduler/config/config.ini',
                'config/config.ini',
                '../config/config.ini'
            ]
            config_file = self._find_existing_file(possible_configs, 'config.ini')
            
        if accounts_file is None:
            # Try multiple possible locations
            possible_accounts = [
                script_dir / '../config/accounts.json',
                'eks-scheduler/config/accounts.json',
                'config/accounts.json',
                '../config/accounts.json'
            ]
            accounts_file = self._find_existing_file(possible_accounts, 'accounts.json')
        
        self.config_file = str(config_file)
        self.accounts_file = str(accounts_file)
        self.config = None
        self.accounts = None
        
        self.load_config()
        self.load_accounts()
    
    def _find_existing_file(self, possible_paths, filename):
        """Find the first existing file from a list of possible paths.
        
        Args:
            possible_paths (list): List of possible file paths
            filename (str): Name of the file for error messages
            
        Returns:
            str: Path to the existing file
            
        Raises:
            ConfigurationError: If no file is found
        """
        for path in possible_paths:
            if Path(path).exists():
                self.logger.info(f"Found {filename} at: {path}")
                return str(path)
        
        self.logger.error(f"Could not find {filename} in any of these locations: {possible_paths}")
        raise ConfigurationError(f"Could not find {filename} in any expected location")

    def load_config(self):
        """Load configuration from config file."""
        try:
            self.config = configparser.ConfigParser()
            
            if not Path(self.config_file).exists():
                self.logger.warning(f"Config file {self.config_file} not found, creating with defaults")
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                
                # Create default configuration
                self.config['aws'] = {
                    'region': 'us-west-2',
                    'tag_key': 'Schedule',
                    'tag_value': 'enabled'
                }
                
                self.config['eks'] = {
                    'default_min_nodes': '1',
                    'max_scale_down_nodes': '0'
                }
                
                self.config['sns'] = {
                    'topic_arn': ''
                }
                
                self.config['logging'] = {
                    'level': 'INFO',
                    'file': 'eks-scheduler.log'
                }
                
                with open(self.config_file, 'w') as f:
                    self.config.write(f)
                    
                self.logger.info(f"Created default config file: {self.config_file}")
            else:
                self.config.read(self.config_file)
                self.logger.info(f"Loaded config from {self.config_file}")
                
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {str(e)}")
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")

    def load_accounts(self):
        """Load accounts from accounts file."""
        try:
            if not Path(self.accounts_file).exists():
                self.logger.warning(f"Accounts file {self.accounts_file} not found, creating placeholder")
                os.makedirs(os.path.dirname(self.accounts_file), exist_ok=True)
                
                # Create placeholder accounts file
                placeholder_accounts = [
                    {
                        "name": "default",
                        "region": "us-west-2",
                        "description": "Default account"
                    }
                ]
                
                with open(self.accounts_file, 'w') as f:
                    json.dump(placeholder_accounts, f, indent=2)
                    
                self.accounts = placeholder_accounts
                self.logger.info(f"Created placeholder accounts file: {self.accounts_file}")
            else:
                with open(self.accounts_file, 'r') as f:
                    self.accounts = json.load(f)
                self.logger.info(f"Loaded {len(self.accounts)} accounts from {self.accounts_file}")
                
        except Exception as e:
            self.logger.error(f"Failed to load accounts: {str(e)}")
            raise ConfigurationError(f"Failed to load accounts: {str(e)}")

    def get(self, section, key, fallback=None):
        """Get a configuration value.
        
        Args:
            section (str): Configuration section
            key (str): Configuration key
            fallback: Default value if key not found
            
        Returns:
            str: Configuration value
        """
        try:
            return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError):
            self.logger.warning(f"Configuration key [{section}] {key} not found, using fallback: {fallback}")
            return fallback

    def get_accounts(self):
        """Get all accounts.
        
        Returns:
            list: List of account dictionaries
        """
        return self.accounts if self.accounts else []
    
    def get_account_by_name(self, account_name):
        """Get account by name.
        
        Args:
            account_name (str): Account name to find
            
        Returns:
            dict: Account dictionary or None if not found
        """
        if not self.accounts:
            return None
            
        for account in self.accounts:
            if account.get('name') == account_name:
                return account
        return None 