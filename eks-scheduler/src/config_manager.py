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
    
    def __init__(self, config_file=None):
        """Initialize the configuration manager.
        
        Args:
            config_file (str, optional): Path to the config.ini file
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
        
        self.config_file = str(config_file)
        self.config = None
        
        self.load_config()
    
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
                
                self.config['exclusions'] = {
                    'excluded_clusters': ''
                }
                
                self.config['autoscaler'] = {
                    'deployment_name': 'cluster-autoscaler'
                }
                
                self.config['webhooks'] = {
                    'webhook_names': 'aws-load-balancer-webhook:kube-system,kyverno-policy-webhook,kyverno-resource-webhook'
                }
                
                self.config['timeouts'] = {
                    'webhook_timeout': '60',
                    'drain_timeout': '300',
                    'pod_grace_period': '30',
                    'bootstrap_validation_timeout': '600',
                    'dependency_startup_timeout': '300',
                    'kubectl_timeout': '120',
                    'aws_cli_timeout': '60'
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

    def get_excluded_clusters(self):
        """Get list of excluded cluster names.
        
        Returns:
            list: List of cluster names to exclude
        """
        excluded_str = self.get('exclusions', 'excluded_clusters', '')
        if not excluded_str:
            return []
        return [cluster.strip() for cluster in excluded_str.split(',') if cluster.strip()]
    
    def get_autoscaler_deployment_name(self):
        """Get the name of the cluster autoscaler deployment.
        
        Returns:
            str: Autoscaler deployment name
        """
        return self.get('autoscaler', 'deployment_name', 'cluster-autoscaler')
    
    def get_webhook_names(self):
        """Get list of webhook names to manage.
        
        Returns:
            list: List of tuples (webhook_name, namespace) where namespace can be None
        """
        webhook_str = self.get('webhooks', 'webhook_names', '')
        if not webhook_str:
            return []
        
        webhooks = []
        for webhook in webhook_str.split(','):
            webhook = webhook.strip()
            if ':' in webhook:
                name, namespace = webhook.split(':', 1)
                webhooks.append((name.strip(), namespace.strip()))
            else:
                webhooks.append((webhook, None))
        return webhooks
    
    def get_timeout(self, timeout_name, default=None):
        """Get a timeout value from configuration.
        
        Args:
            timeout_name (str): Name of the timeout
            default (int): Default value if not found
            
        Returns:
            int: Timeout value in seconds
        """
        value = self.get('timeouts', timeout_name, str(default) if default else None)
        try:
            return int(value) if value else default
        except ValueError:
            self.logger.warning(f"Invalid timeout value for {timeout_name}: {value}, using default: {default}")
            return default

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

 