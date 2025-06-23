import boto3
import logging
import subprocess
import json
from datetime import datetime
from state_manager import StateManager
from pod_manager import PodManager, PodManagerError
from webhook_manager import WebhookManager, WebhookManagerError
from bootstrap_validator import BootstrapValidator, BootstrapValidatorError
from dependency_manager import DependencyManager, DependencyManagerError

class EKSOperationError(Exception):
    pass

class EKSOperations:
    def __init__(self, region, config_manager=None, dry_run=False):
        self.logger = logging.getLogger(__name__)
        self.region = region
        self.dry_run = dry_run
        self.config_manager = config_manager
        self.eks_client = boto3.client('eks', region_name=region)
        self.state_manager = StateManager(dry_run=dry_run)
        
        # Initialize new management components
        self.pod_manager = PodManager(dry_run=dry_run)
        self.webhook_manager = WebhookManager(config_manager=config_manager, dry_run=dry_run)
        self.bootstrap_validator = BootstrapValidator(dry_run=dry_run)
        self.dependency_manager = DependencyManager(dry_run=dry_run)
        
        if self.dry_run:
            self.logger.info("EKS Operations initialized in DRY RUN mode - no actual changes will be made")

    def _run_kubectl_command(self, command):
        """Execute kubectl command via subprocess.
        
        Args:
            command (list): kubectl command as list of strings
            
        Returns:
            tuple: (success, stdout, stderr)
        """
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would run kubectl command: {' '.join(command)}")
                # Return mock success for dry run
                return True, "dry-run-output", ""
            
            self.logger.debug(f"Running kubectl command: {' '.join(command)}")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=60
            )
            
            success = result.returncode == 0
            if not success:
                self.logger.warning(f"kubectl command failed (exit {result.returncode}): {result.stderr}")
                
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error("kubectl command timed out after 60 seconds")
            return False, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"Error running kubectl command: {str(e)}")
            return False, "", str(e)

    def configure_kubectl(self, cluster_name):
        """Configure kubectl for EKS cluster access.
        
        Args:
            cluster_name (str): Name of the EKS cluster
            
        Returns:
            bool: True if configuration successful
        """
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would configure kubectl for cluster {cluster_name}")
                return True
            
            self.logger.info(f"Configuring kubectl for cluster {cluster_name}")
            
            # Update kubeconfig for EKS cluster using AWS CLI
            command = [
                'aws', 'eks', 'update-kubeconfig',
                '--region', self.region,
                '--name', cluster_name
            ]
            
            # Use subprocess.run directly for AWS CLI commands (not _run_kubectl_command)
            self.logger.debug(f"Running AWS CLI command: {' '.join(command)}")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=60
            )
            
            success = result.returncode == 0
            
            if success:
                self.logger.info(f"Successfully configured kubectl for cluster {cluster_name}")
                return True
            else:
                self.logger.error(f"Failed to configure kubectl: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("AWS CLI command timed out after 60 seconds")
            return False
        except Exception as e:
            self.logger.error(f"Error configuring kubectl for cluster {cluster_name}: {str(e)}")
            return False

    def check_cluster_autoscaler(self, cluster_name):
        """Check if cluster autoscaler exists and get its current state.
        
        Args:
            cluster_name (str): Name of the EKS cluster
            
        Returns:
            dict: {
                'exists': bool,
                'namespace': str,
                'deployment_name': str,
                'replicas': int,
                'ready_replicas': int
            }
        """
        # Common autoscaler deployment names and namespaces
        search_targets = [
            ('kube-system', 'cluster-autoscaler'),
            ('kube-system', 'cluster-autoscaler-aws-cluster-autoscaler'),
            ('cluster-autoscaler', 'cluster-autoscaler'),
            ('kube-system', 'aws-cluster-autoscaler')
        ]
        
        for namespace, deployment_name in search_targets:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would check for autoscaler deployment {deployment_name} in namespace {namespace}")
                    # Return mock autoscaler for dry run
                    return {
                        'exists': True,
                        'namespace': 'kube-system',
                        'deployment_name': 'cluster-autoscaler',
                        'replicas': 1,
                        'ready_replicas': 1
                    }
                
                # Check if deployment exists
                command = [
                    'kubectl', 'get', 'deployment', deployment_name,
                    '-n', namespace,
                    '-o', 'json'
                ]
                
                success, stdout, stderr = self._run_kubectl_command(command)
                
                if success:
                    try:
                        deployment_info = json.loads(stdout)
                        spec = deployment_info.get('spec', {})
                        status = deployment_info.get('status', {})
                        
                        result = {
                            'exists': True,
                            'namespace': namespace,
                            'deployment_name': deployment_name,
                            'replicas': spec.get('replicas', 0),
                            'ready_replicas': status.get('readyReplicas', 0)
                        }
                        
                        self.logger.info(f"Found cluster autoscaler: {deployment_name} in {namespace} "
                                       f"(replicas: {result['replicas']}, ready: {result['ready_replicas']})")
                        return result
                        
                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON response for deployment {deployment_name}")
                        continue
                        
            except Exception as e:
                self.logger.debug(f"Deployment {deployment_name} not found in {namespace}: {str(e)}")
                continue
        
        self.logger.info("No cluster autoscaler deployment found")
        return {
            'exists': False,
            'namespace': None,
            'deployment_name': None,
            'replicas': 0,
            'ready_replicas': 0
        }

    def manage_cluster_autoscaler(self, cluster_name, action='disable'):
        """Manage cluster autoscaler (disable/restore).
        
        Args:
            cluster_name (str): Name of the EKS cluster
            action (str): 'disable' or 'restore'
            
        Returns:
            dict: Operation result
        """
        try:
            if action == 'disable':
                # Check current autoscaler state
                autoscaler_info = self.check_cluster_autoscaler(cluster_name)
                
                if not autoscaler_info['exists']:
                    self.logger.info("No cluster autoscaler found, skipping disable operation")
                    return {'status': 'skipped', 'reason': 'autoscaler_not_found'}
                
                # Store original state
                if not self.dry_run:
                    self.state_manager.store_autoscaler_config(
                        cluster_name, 
                        autoscaler_info['namespace'],
                        autoscaler_info['deployment_name'],
                        autoscaler_info['replicas']
                    )
                
                # Scale autoscaler to 0 replicas
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would disable cluster autoscaler by scaling to 0 replicas")
                    return {'status': 'success', 'action': 'disabled', 'dry_run': True}
                else:
                    command = [
                        'kubectl', 'scale', 'deployment', autoscaler_info['deployment_name'],
                        '-n', autoscaler_info['namespace'],
                        '--replicas=0'
                    ]
                    
                    success, stdout, stderr = self._run_kubectl_command(command)
                    
                    if success:
                        self.logger.info(f"Successfully disabled cluster autoscaler")
                        return {'status': 'success', 'action': 'disabled'}
                    else:
                        self.logger.error(f"Failed to disable cluster autoscaler: {stderr}")
                        return {'status': 'failed', 'error': stderr}
            
            elif action == 'restore':
                # Get stored autoscaler configuration
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would restore cluster autoscaler to original replicas")
                    return {'status': 'success', 'action': 'restored', 'dry_run': True}
                
                stored_config = self.state_manager.get_autoscaler_config(cluster_name)
                
                if not stored_config:
                    self.logger.warning("No stored autoscaler configuration found, skipping restore")
                    return {'status': 'skipped', 'reason': 'no_stored_config'}
                
                # Restore autoscaler to original replica count
                command = [
                    'kubectl', 'scale', 'deployment', stored_config['deployment_name'],
                    '-n', stored_config['namespace'],
                    f"--replicas={stored_config['original_replicas']}"
                ]
                
                success, stdout, stderr = self._run_kubectl_command(command)
                
                if success:
                    self.logger.info(f"Successfully restored cluster autoscaler to {stored_config['original_replicas']} replicas")
                    # Clean up stored config after successful restore
                    self.state_manager.clear_autoscaler_config(cluster_name)
                    return {'status': 'success', 'action': 'restored', 'replicas': stored_config['original_replicas']}
                else:
                    self.logger.error(f"Failed to restore cluster autoscaler: {stderr}")
                    return {'status': 'failed', 'error': stderr}
            
            else:
                raise ValueError(f"Invalid action: {action}. Must be 'disable' or 'restore'")
                
        except Exception as e:
            self.logger.error(f"Error managing cluster autoscaler: {str(e)}")
            return {'status': 'failed', 'error': str(e)}

    def get_managed_node_groups(self, cluster_name):
        """Get managed node groups for a cluster."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would list node groups for cluster {cluster_name}")
                # Return mock data for dry run
                return ['mock-nodegroup-1', 'mock-nodegroup-2']
            
            response = self.eks_client.list_nodegroups(clusterName=cluster_name)
            return response.get('nodegroups', [])
        except Exception as e:
            self.logger.error(f"Error listing node groups for cluster {cluster_name}: {str(e)}")
            raise EKSOperationError(f"Error listing node groups: {str(e)}")

    def get_node_group_details(self, cluster_name, node_group_name):
        """Get details of a specific node group."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would describe node group {node_group_name}")
                # Return mock data for dry run
                return {
                    'scalingConfig': {
                        'minSize': 2,
                        'maxSize': 10,
                        'desiredSize': 3
                    }
                }
            
            response = self.eks_client.describe_nodegroup(
                clusterName=cluster_name,
                nodegroupName=node_group_name
            )
            return response['nodegroup']
        except Exception as e:
            self.logger.error(f"Error describing node group {node_group_name}: {str(e)}")
            raise EKSOperationError(f"Error describing node group: {str(e)}")

    def scale_node_group(self, cluster_name, node_group_name, desired_size, min_size, max_size):
        """Scale a managed node group with explicit min/max/desired values."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would scale node group {node_group_name} to min={min_size}, max={max_size}, desired={desired_size}")
                return {
                    'NodeGroupName': node_group_name,
                    'MinSize': min_size,
                    'MaxSize': max_size,
                    'DesiredSize': desired_size,
                    'Status': 'DryRun',
                    'Timestamp': datetime.now().isoformat(),
                    'UpdateId': 'dry-run-update-id'
                }
            
            # Validate AWS EKS constraints
            if max_size < 1:
                raise ValueError(f"maxSize must be at least 1, got {max_size}")
            
            self.logger.info(f"Scaling node group {node_group_name} to min={min_size}, max={max_size}, desired={desired_size}")
            
            response = self.eks_client.update_nodegroup_config(
                clusterName=cluster_name,
                nodegroupName=node_group_name,
                scalingConfig={
                    'minSize': min_size,
                    'maxSize': max_size,
                    'desiredSize': desired_size
                }
            )
            
            return {
                'NodeGroupName': node_group_name,
                'MinSize': min_size,
                'MaxSize': max_size,
                'DesiredSize': desired_size,
                'Status': 'Success',
                'Timestamp': datetime.now().isoformat(),
                'UpdateId': response['update']['id']
            }
            
        except Exception as e:
            self.logger.error(f"Error scaling node group {node_group_name}: {str(e)}")
            return {
                'NodeGroupName': node_group_name,
                'Status': 'Failed',
                'Error': str(e),
                'Timestamp': datetime.now().isoformat()
            }

    def scale_down_cluster(self, cluster_name):
        """Enhanced scale down with graceful pod draining and webhook management.
        
        This safely handles cluster scaling by:
        1. Configuring kubectl for cluster access
        2. Temporarily disabling critical webhooks to prevent bootstrap deadlocks
        3. Disabling cluster autoscaler (preventing scale-up interference)
        4. Gracefully draining all pods from nodes
        5. Scaling node groups to 0 (min=0, desired=0, max>=1 for AWS compliance)
        6. Storing original configurations for restoration
        """
        results = []
        autoscaler_result = None
        webhook_disable_result = None
        pod_drain_results = []
        
        try:
            # Step 1: Configure kubectl for cluster access
            self.logger.info("Step 1: Configuring kubectl access...")
            if not self.configure_kubectl(cluster_name):
                raise EKSOperationError("Failed to configure kubectl for cluster access")
            
            # Step 2: Disable critical webhooks to prevent bootstrap deadlocks
            self.logger.info("Step 2: Temporarily disabling critical webhooks...")
            try:
                webhook_disable_success = self.webhook_manager.disable_critical_webhooks()
                webhook_disable_result = 'success' if webhook_disable_success else 'failed'
                
                if webhook_disable_success:
                    self.logger.info("Critical webhooks disabled successfully")
                else:
                    self.logger.warning("Failed to disable some critical webhooks - continuing with caution")
            except WebhookManagerError as e:
                self.logger.warning(f"Webhook management error: {str(e)} - continuing with scale down")
                webhook_disable_result = 'error'
            
            # Step 3: Disable cluster autoscaler to prevent conflicts
            self.logger.info("Step 3: Disabling cluster autoscaler...")
            autoscaler_result = self.manage_cluster_autoscaler(cluster_name, action='disable')
            
            if autoscaler_result['status'] == 'failed':
                self.logger.warning(f"Failed to disable cluster autoscaler: {autoscaler_result.get('error', 'Unknown error')}")
                self.logger.warning("Proceeding with node scaling, but autoscaler may interfere")
            elif autoscaler_result['status'] == 'success':
                self.logger.info("Cluster autoscaler disabled successfully")
            else:
                self.logger.info(f"Autoscaler management: {autoscaler_result.get('reason', 'Unknown')}")
            
            # Step 4: Gracefully drain pods from all node groups
            self.logger.info("Step 4: Gracefully draining pods from node groups...")
            node_groups = self.get_managed_node_groups(cluster_name)
            
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would drain pods from {len(node_groups)} node groups")
            else:
                for node_group_name in node_groups:
                    try:
                        self.logger.info(f"Draining pods from node group: {node_group_name}")
                        drain_success, drain_details = self.pod_manager.drain_node_group(node_group_name)
                        pod_drain_results.append({
                            'node_group': node_group_name,
                            'success': drain_success,
                            'details': drain_details
                        })
                        
                        if not drain_success:
                            self.logger.warning(f"Pod draining partially failed for {node_group_name} - continuing with scale down")
                        else:
                            self.logger.info(f"Successfully drained pods from {node_group_name}")
                            
                    except PodManagerError as e:
                        self.logger.error(f"Pod draining error for {node_group_name}: {str(e)}")
                        pod_drain_results.append({
                            'node_group': node_group_name,
                            'success': False,
                            'error': str(e)
                        })
            
            # Step 5: Scale down node groups
            self.logger.info("Step 5: Scaling down node groups...")
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would scale down {len(node_groups)} node groups in cluster {cluster_name}")
            else:
                self.logger.info(f"Scaling down {len(node_groups)} node groups in cluster {cluster_name}")
            
            for node_group_name in node_groups:
                # Get current configuration and store it
                current_details = self.get_node_group_details(cluster_name, node_group_name)
                current_scaling_config = current_details['scalingConfig']
                
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Current config for {node_group_name}: "
                                   f"min={current_scaling_config['minSize']}, "
                                   f"max={current_scaling_config['maxSize']}, "
                                   f"desired={current_scaling_config['desiredSize']}")
                    self.logger.info(f"[DRY RUN] Would store original configuration and scale to 0")
                else:
                    self.logger.info(f"Current config for {node_group_name}: "
                                   f"min={current_scaling_config['minSize']}, "
                                   f"max={current_scaling_config['maxSize']}, "
                                   f"desired={current_scaling_config['desiredSize']}")
                    
                    # Store original configuration before scaling down
                    self.state_manager.store_node_group_config(
                        cluster_name, node_group_name, current_scaling_config
                    )
                
                # Scale to 0 nodes (min=0, desired=0, but keep max>=1 for AWS compliance)
                target_max = max(1, current_scaling_config['maxSize'])  # Ensure maxSize >= 1
                result = self.scale_node_group(cluster_name, node_group_name, 0, 0, target_max)
                result['PreviousState'] = f"min={current_scaling_config['minSize']}, max={current_scaling_config['maxSize']}, desired={current_scaling_config['desiredSize']}"
                result['CurrentState'] = 'scaled_down' if not self.dry_run else 'dry_run_scaled_down'
                result['AutoscalerManaged'] = autoscaler_result['status'] if autoscaler_result else 'unknown'
                result['WebhookManaged'] = webhook_disable_result
                result['PodsDrained'] = any(drain['success'] for drain in pod_drain_results if drain['node_group'] == node_group_name)
                results.append(result)
            
            self.logger.info(f"Scale down operation completed for cluster {cluster_name}")
            
        except EKSOperationError as e:
            self.logger.error(f"EKS operation error during scale down: {str(e)}")
            results.append({
                'NodeGroupName': 'Unknown',
                'Status': 'Failed',
                'Error': str(e),
                'Timestamp': datetime.now().isoformat(),
                'AutoscalerManaged': autoscaler_result['status'] if autoscaler_result else 'unknown',
                'WebhookManaged': webhook_disable_result,
                'PodsDrained': False
            })
        except Exception as e:
            self.logger.error(f"Unexpected error during scale down: {str(e)}")
            results.append({
                'NodeGroupName': 'Unknown',
                'Status': 'Failed',
                'Error': f"Unexpected error: {str(e)}",
                'Timestamp': datetime.now().isoformat(),
                'AutoscalerManaged': autoscaler_result['status'] if autoscaler_result else 'unknown',
                'WebhookManaged': webhook_disable_result,
                'PodsDrained': False
            })
            
        return results

    def scale_up_cluster(self, cluster_name, min_nodes):
        """Enhanced scale up with bootstrap validation, dependency management, and webhook restoration.
        
        This safely handles cluster scaling by:
        1. Configuring kubectl for cluster access
        2. Validating bootstrap requirements
        3. Scaling node groups to desired configuration
        4. Waiting for nodes to be ready
        5. Validating system pod dependencies
        6. Restoring cluster autoscaler
        7. Re-enabling critical webhooks
        8. Final validation of cluster readiness
        
        Args:
            cluster_name: Name of the EKS cluster
            min_nodes: Minimum number of nodes to set (from CI input)
        """
        results = []
        autoscaler_result = None
        webhook_enable_result = None
        bootstrap_validation_result = None
        dependency_validation_result = None
        
        try:
            # Step 1: Configure kubectl for cluster access
            self.logger.info("Step 1: Configuring kubectl access...")
            if not self.configure_kubectl(cluster_name):
                raise EKSOperationError("Failed to configure kubectl for cluster access")
            
            # Step 2: Validate bootstrap requirements
            self.logger.info("Step 2: Validating bootstrap requirements...")
            try:
                bootstrap_validation_result = self.bootstrap_validator.validate_bootstrap_requirements(cluster_name, min_nodes)
                self.logger.info("Bootstrap requirements validation passed")
            except BootstrapValidatorError as e:
                self.logger.error(f"Bootstrap validation failed: {str(e)}")
                # For scale-up, we want to continue even if some validations fail
                bootstrap_validation_result = False
                self.logger.warning("Continuing with scale-up despite bootstrap validation warnings")
            
            # Step 3: Scale up node groups
            self.logger.info("Step 3: Scaling up node groups...")
            node_groups = self.get_managed_node_groups(cluster_name)
            
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would scale up {len(node_groups)} node groups in cluster {cluster_name}")
                self.logger.info(f"[DRY RUN] Using minimum nodes: {min_nodes}")
            else:
                self.logger.info(f"Scaling up {len(node_groups)} node groups in cluster {cluster_name}")
                self.logger.info(f"Using minimum nodes: {min_nodes}")
            
            # Get stored configurations for the cluster
            if not self.dry_run:
                stored_configs = self.state_manager.get_all_cluster_configs(cluster_name)
            else:
                # Mock stored configs for dry run
                stored_configs = {
                    'mock-nodegroup-1': {'minSize': 2, 'maxSize': 10, 'desiredSize': 3},
                    'mock-nodegroup-2': {'minSize': 1, 'maxSize': 5, 'desiredSize': 2}
                }
                self.logger.info(f"[DRY RUN] Would load stored configurations: {stored_configs}")
            
            for node_group_name in node_groups:
                current_details = self.get_node_group_details(cluster_name, node_group_name)
                current_scaling_config = current_details['scalingConfig']
                
                # Determine target configuration
                if node_group_name in stored_configs:
                    # Use stored original configuration as base, but respect min_nodes
                    stored_config = stored_configs[node_group_name]
                    
                    # Use the higher of stored min or provided min_nodes
                    target_min = max(stored_config['minSize'], min_nodes)
                    target_max = stored_config['maxSize']
                    
                    # Set desired to the higher of stored desired or min_nodes
                    target_desired = max(stored_config['desiredSize'], min_nodes)
                    
                    # Ensure max is at least as large as desired
                    if target_max < target_desired:
                        target_max = target_desired
                    
                    if self.dry_run:
                        self.logger.info(f"[DRY RUN] Would restore {node_group_name} with min_nodes override: "
                                       f"stored(min={stored_config['minSize']}, max={stored_config['maxSize']}, desired={stored_config['desiredSize']}) "
                                       f"-> target(min={target_min}, max={target_max}, desired={target_desired})")
                    else:
                        self.logger.info(f"Restoring {node_group_name} with min_nodes override: "
                                       f"stored(min={stored_config['minSize']}, max={stored_config['maxSize']}, desired={stored_config['desiredSize']}) "
                                       f"-> target(min={target_min}, max={target_max}, desired={target_desired})")
                else:
                    # No stored config, use min_nodes as baseline
                    target_min = min_nodes
                    target_desired = min_nodes
                    # Set max to allow autoscaler to scale up (use reasonable default)
                    target_max = max(min_nodes * 3, 10)  # Allow 3x scaling or minimum 10 nodes
                    
                    if self.dry_run:
                        self.logger.warning(f"[DRY RUN] No stored config for {node_group_name}, would use defaults: "
                                          f"min={target_min}, max={target_max}, desired={target_desired}")
                    else:
                        self.logger.warning(f"No stored config for {node_group_name}, using defaults: "
                                          f"min={target_min}, max={target_max}, desired={target_desired}")
                
                result = self.scale_node_group(cluster_name, node_group_name, target_desired, target_min, target_max)
                result['PreviousState'] = f"min={current_scaling_config['minSize']}, max={current_scaling_config['maxSize']}, desired={current_scaling_config['desiredSize']}"
                result['CurrentState'] = 'scaled_up' if not self.dry_run else 'dry_run_scaled_up'
                results.append(result)
            
            # Step 4: Wait for nodes to be ready
            self.logger.info("Step 4: Waiting for nodes to be ready...")
            if not self.dry_run:
                # Calculate expected total nodes
                expected_nodes = sum(max(stored_configs.get(ng, {}).get('desiredSize', min_nodes), min_nodes) for ng in node_groups)
                
                if not self.bootstrap_validator.wait_for_nodes_ready(expected_nodes, timeout=600):
                    self.logger.warning("Timeout waiting for all nodes to be ready - continuing with limited nodes")
            
            # Step 5: Uncordon nodes (in case they were cordoned during drain)
            self.logger.info("Step 5: Uncordoning nodes...")
            for node_group_name in node_groups:
                try:
                    self.pod_manager.uncordon_nodes_in_nodegroup(node_group_name)
                except Exception as e:
                    self.logger.warning(f"Failed to uncordon nodes in {node_group_name}: {str(e)}")
            
            # Step 6: Validate system pod dependencies
            self.logger.info("Step 6: Validating system pod dependencies...")
            try:
                dependency_validation_result = self.dependency_manager.validate_service_dependencies(timeout_per_tier=300)
                self.logger.info("System pod dependency validation completed")
            except DependencyManagerError as e:
                self.logger.error(f"Dependency validation failed: {str(e)}")
                dependency_validation_result = False
                self.logger.warning("Some dependencies may not be ready, but continuing")
            
            # Step 7: Restore cluster autoscaler
            self.logger.info("Step 7: Restoring cluster autoscaler...")
            autoscaler_result = self.manage_cluster_autoscaler(cluster_name, action='restore')
            
            if autoscaler_result['status'] == 'success':
                self.logger.info("Cluster autoscaler restored successfully")
            elif autoscaler_result['status'] == 'failed':
                self.logger.warning(f"Failed to restore cluster autoscaler: {autoscaler_result.get('error', 'Unknown error')}")
            else:
                self.logger.info(f"Autoscaler restoration: {autoscaler_result.get('reason', 'Unknown')}")
            
            # Step 8: Re-enable critical webhooks
            self.logger.info("Step 8: Re-enabling critical webhooks...")
            try:
                webhook_enable_success = self.webhook_manager.enable_critical_webhooks()
                webhook_enable_result = 'success' if webhook_enable_success else 'failed'
                
                if webhook_enable_success:
                    self.logger.info("Critical webhooks re-enabled successfully")
                else:
                    self.logger.warning("Failed to re-enable some critical webhooks")
            except WebhookManagerError as e:
                self.logger.warning(f"Webhook re-enable error: {str(e)}")
                webhook_enable_result = 'error'
            
            # Step 9: Final validation of webhook readiness
            self.logger.info("Step 9: Final validation of webhook readiness...")
            if not self.dry_run:
                try:
                    if self.webhook_manager.validate_webhooks_ready(timeout=300):
                        self.logger.info("Webhook validation completed successfully")
                    else:
                        self.logger.warning("Some webhooks may not be fully ready")
                except Exception as e:
                    self.logger.warning(f"Webhook validation error: {str(e)}")
            
            # Add comprehensive status to all node group results
            for result in results:
                result['AutoscalerManaged'] = autoscaler_result['status'] if autoscaler_result else 'unknown'
                result['WebhookManaged'] = webhook_enable_result
                result['BootstrapValidated'] = bootstrap_validation_result
                result['DependenciesValidated'] = dependency_validation_result
            
            self.logger.info(f"Scale up operation completed for cluster {cluster_name}")
                
        except EKSOperationError as e:
            self.logger.error(f"EKS operation error during scale up: {str(e)}")
            results.append({
                'NodeGroupName': 'Unknown',
                'Status': 'Failed',
                'Error': str(e),
                'Timestamp': datetime.now().isoformat(),
                'AutoscalerManaged': autoscaler_result['status'] if autoscaler_result else 'unknown',
                'WebhookManaged': webhook_enable_result,
                'BootstrapValidated': bootstrap_validation_result,
                'DependenciesValidated': dependency_validation_result
            })
        except Exception as e:
            self.logger.error(f"Unexpected error during scale up: {str(e)}")
            results.append({
                'NodeGroupName': 'Unknown',
                'Status': 'Failed',
                'Error': f"Unexpected error: {str(e)}",
                'Timestamp': datetime.now().isoformat(),
                'AutoscalerManaged': autoscaler_result['status'] if autoscaler_result else 'unknown',
                'WebhookManaged': webhook_enable_result,
                'BootstrapValidated': bootstrap_validation_result,
                'DependenciesValidated': dependency_validation_result
            })
            
        return results

    def get_cluster_health_summary(self, cluster_name):
        """Get comprehensive cluster health summary including all components."""
        try:
            if self.dry_run:
                return {
                    'cluster_name': cluster_name,
                    'timestamp': datetime.now().isoformat(),
                    'overall_health': 'healthy',
                    'nodes': {'total': 3, 'ready': 3, 'schedulable': 3},
                    'system_pods': {'ready': 8, 'total': 8},
                    'webhooks': {'healthy': 4, 'total': 4},
                    'dependencies': {'satisfied': True},
                    'autoscaler': {'enabled': True, 'healthy': True}
                }
            
            self.logger.info(f"Gathering comprehensive health summary for cluster {cluster_name}")
            
            # Configure kubectl access
            if not self.configure_kubectl(cluster_name):
                return {
                    'cluster_name': cluster_name,
                    'timestamp': datetime.now().isoformat(),
                    'overall_health': 'error',
                    'error': 'Failed to configure kubectl access'
                }
            
            # Gather health data from all components
            bootstrap_status = self.bootstrap_validator.get_bootstrap_status_summary()
            webhook_status = self.webhook_manager.get_webhook_status_summary()
            dependency_status = self.dependency_manager.get_dependency_status_summary()
            autoscaler_status = self.check_cluster_autoscaler(cluster_name)
            
            # Determine overall health
            overall_health = 'healthy'
            
            if bootstrap_status.get('error') or webhook_status.get('error') or dependency_status.get('error'):
                overall_health = 'error'
            elif not bootstrap_status.get('bootstrap_ready', True) or not dependency_status.get('dependencies_satisfied', True):
                overall_health = 'degraded'
            elif bootstrap_status.get('schedulable_nodes', 0) < 2:
                overall_health = 'insufficient_capacity'
            
            return {
                'cluster_name': cluster_name,
                'timestamp': datetime.now().isoformat(),
                'overall_health': overall_health,
                'nodes': {
                    'total': bootstrap_status.get('total_nodes', 0),
                    'ready': bootstrap_status.get('ready_nodes', 0),
                    'schedulable': bootstrap_status.get('schedulable_nodes', 0)
                },
                'system_pods': {
                    'ready': bootstrap_status.get('system_deployments_ready', 0),
                    'total': bootstrap_status.get('system_deployments_total', 0)
                },
                'webhooks': {
                    'healthy_critical': webhook_status.get('healthy_critical_webhooks', 0),
                    'total_critical': webhook_status.get('total_critical_webhooks', 0),
                    'validating': webhook_status.get('validating_webhooks', 0),
                    'mutating': webhook_status.get('mutating_webhooks', 0),
                    'deployments_ready': webhook_status.get('critical_deployments_ready', False)
                },
                'dependencies': {
                    'satisfied': dependency_status.get('dependencies_satisfied', False),
                    'ready_tiers': dependency_status.get('ready_tiers', 0),
                    'total_tiers': dependency_status.get('total_tiers', 0),
                    'critical_services_ready': dependency_status.get('critical_services_ready', 0),
                    'total_critical_services': dependency_status.get('total_critical_services', 0)
                },
                'autoscaler': {
                    'exists': autoscaler_status.get('exists', False),
                    'ready_replicas': autoscaler_status.get('ready_replicas', 0),
                    'total_replicas': autoscaler_status.get('replicas', 0)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cluster health summary: {str(e)}")
            return {
                'cluster_name': cluster_name,
                'timestamp': datetime.now().isoformat(),
                'overall_health': 'error',
                'error': str(e)
            }

    def validate_cluster_ready_for_workloads(self, cluster_name):
        """Validate that cluster is ready to accept application workloads."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would validate cluster {cluster_name} readiness for workloads")
                return True
            
            self.logger.info(f"Validating cluster {cluster_name} readiness for application workloads...")
            
            # Get comprehensive health summary
            health = self.get_cluster_health_summary(cluster_name)
            
            if health.get('overall_health') == 'error':
                self.logger.error(f"Cluster health check failed: {health.get('error', 'Unknown error')}")
                return False
            
            # Check minimum requirements for workload deployment
            nodes = health.get('nodes', {})
            if nodes.get('schedulable', 0) < 2:
                self.logger.error(f"Insufficient schedulable nodes: {nodes.get('schedulable', 0)} < 2")
                return False
            
            # Check critical system pods
            system_pods = health.get('system_pods', {})
            if system_pods.get('ready', 0) < system_pods.get('total', 1) * 0.8:  # Allow 80% threshold
                self.logger.error(f"System pods not sufficiently ready: {system_pods.get('ready', 0)}/{system_pods.get('total', 0)}")
                return False
            
            # Check webhook health
            webhooks = health.get('webhooks', {})
            if not webhooks.get('deployments_ready', False):
                self.logger.warning("Webhook deployments not fully ready - workloads may have admission issues")
                # Don't fail for webhook issues, just warn
            
            # Check dependencies
            dependencies = health.get('dependencies', {})
            if not dependencies.get('satisfied', False):
                self.logger.warning("Service dependencies not fully satisfied - some features may be limited")
                # Don't fail for dependency issues, just warn
            
            self.logger.info(f"Cluster {cluster_name} is ready for application workloads")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating cluster readiness: {str(e)}")
            return False 