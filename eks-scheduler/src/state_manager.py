import json
import logging
import os
from datetime import datetime
from pathlib import Path

class StateManager:
    """Manages state storage for EKS node group configurations using local files."""
    
    def __init__(self, state_dir='state', dry_run=False):
        self.logger = logging.getLogger(__name__)
        self.state_dir = Path(state_dir)
        self.dry_run = dry_run
        
        if not self.dry_run:
            self.state_dir.mkdir(exist_ok=True)
        else:
            self.logger.info("StateManager initialized in DRY RUN mode - no state files will be modified")
    
    def _get_state_file(self, cluster_name):
        """Get the state file path for a cluster."""
        return self.state_dir / f"{cluster_name}_nodegroups.json"
    
    def store_node_group_config(self, cluster_name, node_group_name, scaling_config):
        """Store the original node group configuration before scaling down."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would store config for {cluster_name}/{node_group_name}: "
                               f"min={scaling_config['minSize']}, max={scaling_config['maxSize']}, "
                               f"desired={scaling_config['desiredSize']}")
                return True
            
            state_file = self._get_state_file(cluster_name)
            
            # Load existing state or create new
            if state_file.exists():
                with open(state_file, 'r') as f:
                    cluster_state = json.load(f)
            else:
                cluster_state = {}
            
            # Store the configuration
            cluster_state[node_group_name] = {
                'original_min_size': scaling_config['minSize'],
                'original_max_size': scaling_config['maxSize'],
                'original_desired_size': scaling_config['desiredSize'],
                'stored_at': datetime.now().isoformat()
            }
            
            # Write back to file
            with open(state_file, 'w') as f:
                json.dump(cluster_state, f, indent=2)
            
            self.logger.info(f"Stored config for {cluster_name}/{node_group_name}: "
                           f"min={scaling_config['minSize']}, max={scaling_config['maxSize']}, "
                           f"desired={scaling_config['desiredSize']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store config for {cluster_name}/{node_group_name}: {str(e)}")
            return False
    
    def get_node_group_config(self, cluster_name, node_group_name):
        """Retrieve the original node group configuration for restoration."""
        try:
            if self.dry_run:
                # Return mock data for dry run
                mock_config = {
                    'minSize': 2,
                    'maxSize': 10,
                    'desiredSize': 3
                }
                self.logger.info(f"[DRY RUN] Would retrieve config for {cluster_name}/{node_group_name}: {mock_config}")
                return mock_config
            
            state_file = self._get_state_file(cluster_name)
            
            if not state_file.exists():
                self.logger.warning(f"No state file found for cluster {cluster_name}")
                return None
            
            with open(state_file, 'r') as f:
                cluster_state = json.load(f)
            
            if node_group_name in cluster_state:
                config_data = cluster_state[node_group_name]
                config = {
                    'minSize': config_data['original_min_size'],
                    'maxSize': config_data['original_max_size'],
                    'desiredSize': config_data['original_desired_size']
                }
                self.logger.info(f"Retrieved config for {cluster_name}/{node_group_name}: {config}")
                return config
            else:
                self.logger.warning(f"No stored config found for {cluster_name}/{node_group_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve config for {cluster_name}/{node_group_name}: {str(e)}")
            return None
    
    def get_all_cluster_configs(self, cluster_name):
        """Get all stored node group configs for a cluster."""
        try:
            if self.dry_run:
                # Return mock data for dry run
                mock_configs = {
                    'mock-nodegroup-1': {'minSize': 2, 'maxSize': 10, 'desiredSize': 3},
                    'mock-nodegroup-2': {'minSize': 1, 'maxSize': 5, 'desiredSize': 2}
                }
                self.logger.info(f"[DRY RUN] Would retrieve stored configs for cluster {cluster_name}: {mock_configs}")
                return mock_configs
            
            state_file = self._get_state_file(cluster_name)
            
            if not state_file.exists():
                self.logger.warning(f"No state file found for cluster {cluster_name}")
                return {}
            
            with open(state_file, 'r') as f:
                cluster_state = json.load(f)
            
            configs = {}
            for node_group_name, config_data in cluster_state.items():
                configs[node_group_name] = {
                    'minSize': config_data['original_min_size'],
                    'maxSize': config_data['original_max_size'],
                    'desiredSize': config_data['original_desired_size']
                }
            
            self.logger.info(f"Retrieved {len(configs)} stored configs for cluster {cluster_name}")
            return configs
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve cluster configs for {cluster_name}: {str(e)}")
            return {}
    
    def delete_node_group_config(self, cluster_name, node_group_name):
        """Delete stored configuration (optional cleanup)."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would delete stored config for {cluster_name}/{node_group_name}")
                return True
            
            state_file = self._get_state_file(cluster_name)
            
            if not state_file.exists():
                return True
            
            with open(state_file, 'r') as f:
                cluster_state = json.load(f)
            
            if node_group_name in cluster_state:
                del cluster_state[node_group_name]
                
                if cluster_state:
                    # Write back remaining configs
                    with open(state_file, 'w') as f:
                        json.dump(cluster_state, f, indent=2)
                else:
                    # Remove file if empty
                    state_file.unlink()
                
                self.logger.info(f"Deleted stored config for {cluster_name}/{node_group_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete config for {cluster_name}/{node_group_name}: {str(e)}")
            return False
    
    def _get_autoscaler_state_file(self, cluster_name):
        """Get the autoscaler state file path for a cluster."""
        return self.state_dir / f"{cluster_name}_autoscaler.json"
    
    def store_autoscaler_config(self, cluster_name, namespace, deployment_name, original_replicas):
        """Store the original cluster autoscaler configuration before disabling."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would store autoscaler config for {cluster_name}: "
                               f"deployment={deployment_name}, namespace={namespace}, replicas={original_replicas}")
                return True
            
            state_file = self._get_autoscaler_state_file(cluster_name)
            
            autoscaler_state = {
                'namespace': namespace,
                'deployment_name': deployment_name,
                'original_replicas': original_replicas,
                'stored_at': datetime.now().isoformat()
            }
            
            # Write to file
            with open(state_file, 'w') as f:
                json.dump(autoscaler_state, f, indent=2)
            
            self.logger.info(f"Stored autoscaler config for {cluster_name}: "
                           f"deployment={deployment_name}, namespace={namespace}, replicas={original_replicas}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store autoscaler config for {cluster_name}: {str(e)}")
            return False
    
    def get_autoscaler_config(self, cluster_name):
        """Retrieve the original cluster autoscaler configuration for restoration."""
        try:
            if self.dry_run:
                # Return mock data for dry run
                mock_config = {
                    'namespace': 'kube-system',
                    'deployment_name': 'cluster-autoscaler',
                    'original_replicas': 1
                }
                self.logger.info(f"[DRY RUN] Would retrieve autoscaler config for {cluster_name}: {mock_config}")
                return mock_config
            
            state_file = self._get_autoscaler_state_file(cluster_name)
            
            if not state_file.exists():
                self.logger.warning(f"No autoscaler state file found for cluster {cluster_name}")
                return None
            
            with open(state_file, 'r') as f:
                autoscaler_state = json.load(f)
            
            self.logger.info(f"Retrieved autoscaler config for {cluster_name}: "
                           f"deployment={autoscaler_state['deployment_name']}, "
                           f"namespace={autoscaler_state['namespace']}, "
                           f"replicas={autoscaler_state['original_replicas']}")
            return autoscaler_state
                
        except Exception as e:
            self.logger.error(f"Failed to retrieve autoscaler config for {cluster_name}: {str(e)}")
            return None
    
    def clear_autoscaler_config(self, cluster_name):
        """Delete stored autoscaler configuration after successful restoration."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would delete autoscaler config for {cluster_name}")
                return True
            
            state_file = self._get_autoscaler_state_file(cluster_name)
            
            if state_file.exists():
                state_file.unlink()
                self.logger.info(f"Cleared autoscaler config for {cluster_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear autoscaler config for {cluster_name}: {str(e)}")
            return False

    def list_state_files(self):
        """List all state files (useful for debugging)."""
        if self.dry_run:
            self.logger.info("[DRY RUN] Would list state files")
            return []
        
        nodegroup_files = list(self.state_dir.glob("*_nodegroups.json"))
        autoscaler_files = list(self.state_dir.glob("*_autoscaler.json"))
        
        return {
            'nodegroup_files': nodegroup_files,
            'autoscaler_files': autoscaler_files,
            'total_files': len(nodegroup_files) + len(autoscaler_files)
        } 