import boto3
import logging
import subprocess
import json
import time
from datetime import datetime, timedelta
from config_manager import ConfigManager

class WebhookManagerError(Exception):
    pass

class WebhookManager:
    def __init__(self, dry_run=False, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        
        # Initialize config manager if not provided
        if config_manager is None:
            config_manager = ConfigManager()
            config_manager.load_config()
        
        self.config_manager = config_manager
        
        # Get webhook timeout from config, default to 60 seconds
        self.webhook_timeout = self.config_manager.get_timeout('webhook_timeout', 60) if self.config_manager else 60
        
        # Get webhook configuration from config manager
        self.configured_webhooks = self._parse_webhook_config()
        
        if self.dry_run:
            self.logger.info("Webhook Manager initialized in DRY RUN mode")

    def _parse_webhook_config(self):
        """Parse webhook configuration from config manager.
        
        Returns:
            list: List of tuples (webhook_name, namespace)
        """
        if not self.config_manager:
            # Default webhooks if no config manager
            return [
                ('aws-load-balancer-webhook', 'kube-system'),
                ('kyverno-policy-webhook', None),
                ('kyverno-resource-webhook', None)
            ]
        
        return self.config_manager.get_webhook_names()
    
    def _is_configured_webhook(self, webhook_name):
        """Check if a webhook is in the configured list.
        
        Args:
            webhook_name (str): Name of the webhook to check
            
        Returns:
            bool: True if webhook is configured for management
        """
        for configured_name, namespace in self.configured_webhooks:
            if configured_name.lower() in webhook_name.lower():
                return True
        return False
    
    def _get_deployment_name_for_webhook(self, webhook_name):
        """Get the likely deployment name for a webhook.
        
        Args:
            webhook_name (str): Name of the webhook
            
        Returns:
            str: Likely deployment name or None
        """
        webhook_lower = webhook_name.lower()
        
        # Common webhook to deployment mappings
        if 'aws-load-balancer' in webhook_lower:
            return 'aws-load-balancer-controller'
        elif 'kyverno' in webhook_lower:
            if 'policy' in webhook_lower:
                return 'kyverno-admission-controller'
            elif 'resource' in webhook_lower:
                return 'kyverno-admission-controller'
            else:
                return 'kyverno-admission-controller'
        elif 'cert-manager' in webhook_lower:
            return 'cert-manager'
        elif 'istio' in webhook_lower:
            return 'istiod'
        else:
            # For unknown webhooks, try to derive deployment name
            # Remove common webhook suffixes
            for suffix in ['-webhook', '-validating-webhook-cfg', '-mutating-webhook-cfg']:
                if webhook_lower.endswith(suffix):
                    return webhook_name[:-len(suffix)]
            return webhook_name

    def _run_kubectl_command(self, command):
        """Execute kubectl command via subprocess."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would run kubectl command: {' '.join(command)}")
                return True, "dry-run-output", ""
            
            self.logger.debug(f"Running kubectl command: {' '.join(command)}")
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=self.config_manager.get_timeout('kubectl_timeout', 120) if self.config_manager else 120
            )
            
            success = result.returncode == 0
            if not success:
                self.logger.warning(f"kubectl command failed (exit {result.returncode}): {result.stderr}")
                
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error("kubectl command timed out after 120 seconds")
            return False, "", "Command timed out"
        except Exception as e:
            self.logger.error(f"Error running kubectl command: {str(e)}")
            return False, "", str(e)

    def get_validating_admission_webhooks(self):
        """Get all ValidatingAdmissionWebhook configurations."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would get ValidatingAdmissionWebhook configurations")
                return ['kyverno-policy-validating-webhook-cfg', 'kyverno-resource-validating-webhook-cfg']
            
            command = ['kubectl', 'get', 'validatingadmissionwebhooks', '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    webhook_data = json.loads(stdout)
                    webhooks = []
                    
                    for item in webhook_data.get('items', []):
                        webhook_name = item['metadata']['name']
                        webhook_info = {
                            'name': webhook_name,
                            'type': 'validating',
                            'webhooks': item.get('webhooks', [])
                        }
                        webhooks.append(webhook_info)
                    
                    self.logger.info(f"Found {len(webhooks)} ValidatingAdmissionWebhook configurations")
                    return webhooks
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse ValidatingAdmissionWebhook JSON: {str(e)}")
                    return []
            else:
                self.logger.warning(f"Failed to get ValidatingAdmissionWebhooks: {stderr}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting ValidatingAdmissionWebhooks: {str(e)}")
            return []

    def get_mutating_admission_webhooks(self):
        """Get all MutatingAdmissionWebhook configurations."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would get MutatingAdmissionWebhook configurations")
                return ['kyverno-policy-mutating-webhook-cfg', 'kyverno-resource-mutating-webhook-cfg']
            
            command = ['kubectl', 'get', 'mutatingadmissionwebhooks', '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    webhook_data = json.loads(stdout)
                    webhooks = []
                    
                    for item in webhook_data.get('items', []):
                        webhook_name = item['metadata']['name']
                        webhook_info = {
                            'name': webhook_name,
                            'type': 'mutating',
                            'webhooks': item.get('webhooks', [])
                        }
                        webhooks.append(webhook_info)
                    
                    self.logger.info(f"Found {len(webhooks)} MutatingAdmissionWebhook configurations")
                    return webhooks
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse MutatingAdmissionWebhook JSON: {str(e)}")
                    return []
            else:
                self.logger.warning(f"Failed to get MutatingAdmissionWebhooks: {stderr}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting MutatingAdmissionWebhooks: {str(e)}")
            return []

    def check_webhook_endpoint_health(self, webhook_info):
        """Check if webhook endpoint is healthy by testing connectivity."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would check health of webhook {webhook_info['name']}")
                return True
            
            webhook_name = webhook_info['name']
            
            # For Kyverno webhooks, check if the service endpoints are ready
            if 'kyverno' in webhook_name.lower():
                return self._check_kyverno_webhook_health()
            elif 'aws-load-balancer' in webhook_name.lower():
                return self._check_aws_lb_webhook_health()
            else:
                # Generic webhook health check - just verify the webhook exists
                self.logger.info(f"Generic webhook health check for {webhook_name} - assuming healthy if configured")
                return True
                
        except Exception as e:
            self.logger.error(f"Error checking webhook endpoint health for {webhook_info['name']}: {str(e)}")
            return False

    def _check_kyverno_webhook_health(self):
        """Check Kyverno webhook service health."""
        try:
            # Check if Kyverno webhook service has endpoints
            command = ['kubectl', 'get', 'endpoints', 'kyverno-svc-metrics', '-n', 'kyverno', '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    endpoint_data = json.loads(stdout)
                    subsets = endpoint_data.get('subsets', [])
                    
                    if subsets and any(subset.get('addresses') for subset in subsets):
                        self.logger.info("Kyverno webhook service has healthy endpoints")
                        return True
                    else:
                        self.logger.warning("Kyverno webhook service has no ready endpoints")
                        return False
                        
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse Kyverno service endpoints")
                    return False
            else:
                self.logger.warning(f"Failed to get Kyverno service endpoints: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking Kyverno webhook health: {str(e)}")
            return False

    def _check_aws_lb_webhook_health(self):
        """Check AWS Load Balancer Controller webhook health."""
        try:
            # Check if AWS LB Controller webhook service has endpoints
            command = ['kubectl', 'get', 'endpoints', 'aws-load-balancer-webhook-service', '-n', 'kube-system', '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    endpoint_data = json.loads(stdout)
                    subsets = endpoint_data.get('subsets', [])
                    
                    if subsets and any(subset.get('addresses') for subset in subsets):
                        self.logger.info("AWS Load Balancer Controller webhook service has healthy endpoints")
                        return True
                    else:
                        self.logger.warning("AWS Load Balancer Controller webhook service has no ready endpoints")
                        return False
                        
                except json.JSONDecodeError:
                    self.logger.warning("Failed to parse AWS LB Controller service endpoints")
                    return False
            else:
                # Webhook service might not exist, check if controller is running
                return self._check_deployment_ready('aws-load-balancer-controller', 'kube-system')
                
        except Exception as e:
            self.logger.error(f"Error checking AWS LB Controller webhook health: {str(e)}")
            return False

    def _check_deployment_ready(self, deployment_name, namespace):
        """Check if a deployment is ready."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would check if deployment {deployment_name} in {namespace} is ready")
                return True
            
            command = ['kubectl', 'get', 'deployment', deployment_name, '-n', namespace, '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    deployment_data = json.loads(stdout)
                    status = deployment_data.get('status', {})
                    
                    replicas = status.get('replicas', 0)
                    ready_replicas = status.get('readyReplicas', 0)
                    
                    is_ready = replicas > 0 and ready_replicas == replicas
                    
                    self.logger.info(f"Deployment {deployment_name} in {namespace}: "
                                   f"{ready_replicas}/{replicas} replicas ready")
                    
                    return is_ready
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse deployment {deployment_name} JSON")
                    return False
            else:
                self.logger.warning(f"Failed to get deployment {deployment_name}: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking deployment {deployment_name} readiness: {str(e)}")
            return False

    def disable_critical_webhooks(self):
        """Temporarily disable critical webhooks to prevent bootstrap deadlocks."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would disable critical webhooks")
                return True
            
            self.logger.info("Disabling critical webhooks to prevent bootstrap deadlocks...")
            
            disabled_webhooks = []
            
            # Get all validating webhooks
            validating_webhooks = self.get_validating_admission_webhooks()
            for webhook in validating_webhooks:
                if self._is_configured_webhook(webhook['name']):
                    if self._disable_webhook(webhook['name'], 'validatingadmissionwebhooks'):
                        disabled_webhooks.append(webhook['name'])
            
            # Get all mutating webhooks
            mutating_webhooks = self.get_mutating_admission_webhooks()
            for webhook in mutating_webhooks:
                if self._is_configured_webhook(webhook['name']):
                    if self._disable_webhook(webhook['name'], 'mutatingadmissionwebhooks'):
                        disabled_webhooks.append(webhook['name'])
            
            self.logger.info(f"Disabled {len(disabled_webhooks)} critical webhooks: {disabled_webhooks}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error disabling critical webhooks: {str(e)}")
            return False

    def _disable_webhook(self, webhook_name, webhook_type):
        """Disable a specific webhook by setting failurePolicy to Ignore."""
        try:
            # Get current webhook configuration
            command = ['kubectl', 'get', webhook_type, webhook_name, '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if not success:
                self.logger.warning(f"Failed to get webhook {webhook_name}: {stderr}")
                return False
            
            try:
                webhook_config = json.loads(stdout)
                
                # Set failurePolicy to Ignore for all webhooks in the configuration
                webhooks = webhook_config.get('webhooks', [])
                modified = False
                
                for webhook in webhooks:
                    if webhook.get('failurePolicy') != 'Ignore':
                        webhook['failurePolicy'] = 'Ignore'
                        modified = True
                
                if modified:
                    # Apply the modified configuration
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(webhook_config, f, indent=2)
                        temp_file = f.name
                    
                    apply_command = ['kubectl', 'apply', '-f', temp_file]
                    apply_success, apply_stdout, apply_stderr = self._run_kubectl_command(apply_command)
                    
                    # Clean up temp file
                    import os
                    os.unlink(temp_file)
                    
                    if apply_success:
                        self.logger.info(f"Successfully set failurePolicy to Ignore for webhook {webhook_name}")
                        return True
                    else:
                        self.logger.error(f"Failed to apply webhook configuration for {webhook_name}: {apply_stderr}")
                        return False
                else:
                    self.logger.info(f"Webhook {webhook_name} already has failurePolicy set to Ignore")
                    return True
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse webhook configuration for {webhook_name}: {str(e)}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error disabling webhook {webhook_name}: {str(e)}")
            return False

    def enable_critical_webhooks(self):
        """Re-enable critical webhooks after cluster is stable."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would re-enable critical webhooks")
                return True
            
            self.logger.info("Re-enabling critical webhooks...")
            
            enabled_webhooks = []
            
            # Get all validating webhooks
            validating_webhooks = self.get_validating_admission_webhooks()
            for webhook in validating_webhooks:
                if self._is_configured_webhook(webhook['name']):
                    if self._enable_webhook(webhook['name'], 'validatingadmissionwebhooks'):
                        enabled_webhooks.append(webhook['name'])
            
            # Get all mutating webhooks
            mutating_webhooks = self.get_mutating_admission_webhooks()
            for webhook in mutating_webhooks:
                if self._is_configured_webhook(webhook['name']):
                    if self._enable_webhook(webhook['name'], 'mutatingadmissionwebhooks'):
                        enabled_webhooks.append(webhook['name'])
            
            self.logger.info(f"Re-enabled {len(enabled_webhooks)} critical webhooks: {enabled_webhooks}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error re-enabling critical webhooks: {str(e)}")
            return False

    def _enable_webhook(self, webhook_name, webhook_type):
        """Enable a specific webhook by setting failurePolicy to Fail."""
        try:
            # Get current webhook configuration
            command = ['kubectl', 'get', webhook_type, webhook_name, '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if not success:
                self.logger.warning(f"Failed to get webhook {webhook_name}: {stderr}")
                return False
            
            try:
                webhook_config = json.loads(stdout)
                
                # Set failurePolicy to Fail for all webhooks in the configuration
                webhooks = webhook_config.get('webhooks', [])
                modified = False
                
                for webhook in webhooks:
                    if webhook.get('failurePolicy') != 'Fail':
                        webhook['failurePolicy'] = 'Fail'
                        modified = True
                
                if modified:
                    # Apply the modified configuration
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(webhook_config, f, indent=2)
                        temp_file = f.name
                    
                    apply_command = ['kubectl', 'apply', '-f', temp_file]
                    apply_success, apply_stdout, apply_stderr = self._run_kubectl_command(apply_command)
                    
                    # Clean up temp file
                    import os
                    os.unlink(temp_file)
                    
                    if apply_success:
                        self.logger.info(f"Successfully set failurePolicy to Fail for webhook {webhook_name}")
                        return True
                    else:
                        self.logger.error(f"Failed to apply webhook configuration for {webhook_name}: {apply_stderr}")
                        return False
                else:
                    self.logger.info(f"Webhook {webhook_name} already has failurePolicy set to Fail")
                    return True
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse webhook configuration for {webhook_name}: {str(e)}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error enabling webhook {webhook_name}: {str(e)}")
            return False

    def validate_webhooks_ready(self, timeout=None):
        """Validate that all critical webhooks are ready and healthy."""
        try:
            # Use provided timeout or get from config, default to 300 seconds
            if timeout is None:
                timeout = int(self.config_manager.get('eks', 'webhook_validation_timeout', fallback='300'))
            
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would validate webhooks ready (timeout: {timeout}s)")
                return True
            
            self.logger.info(f"Validating webhooks are ready (timeout: {timeout}s)...")
            
            start_time = datetime.now()
            timeout_time = start_time + timedelta(seconds=timeout)
            
            while datetime.now() < timeout_time:
                all_ready = True
                
                # Check configured webhook deployments 
                for webhook_name, namespace in self.configured_webhooks:
                    # Map webhook names to likely deployment names
                    deployment_name = self._get_deployment_name_for_webhook(webhook_name)
                    if deployment_name and namespace:
                        if not self._check_deployment_ready(deployment_name, namespace):
                            self.logger.info(f"Waiting for {deployment_name} in {namespace} to be ready...")
                            all_ready = False
                            break
                    
                    if not all_ready:
                        break
                
                if all_ready:
                    self.logger.info("All critical webhook deployments are ready")
                    
                    # Give a bit more time for webhooks to fully initialize
                    time.sleep(10)
                    
                    # Test webhook health
                    all_webhooks = self.get_validating_admission_webhooks() + self.get_mutating_admission_webhooks()
                    webhook_health = True
                    
                    for webhook in all_webhooks:
                        if self._is_configured_webhook(webhook['name']):
                            if not self.check_webhook_endpoint_health(webhook):
                                self.logger.warning(f"Webhook {webhook['name']} is not healthy")
                                webhook_health = False
                    
                    if webhook_health:
                        self.logger.info("All critical webhooks are ready and healthy")
                        return True
                
                time.sleep(15)
            
            # Timeout reached
            self.logger.error(f"Timeout waiting for webhooks to be ready after {timeout} seconds")
            return False
            
        except Exception as e:
            self.logger.error(f"Error validating webhooks ready: {str(e)}")
            return False

    def get_webhook_status_summary(self):
        """Get a summary of all webhook statuses."""
        try:
            if self.dry_run:
                return {
                    'validating_webhooks': 2,
                    'mutating_webhooks': 2,
                    'healthy_webhooks': 4,
                    'critical_deployments_ready': True
                }
            
            validating_webhooks = self.get_validating_admission_webhooks()
            mutating_webhooks = self.get_mutating_admission_webhooks()
            
            healthy_count = 0
            total_critical = 0
            
            all_webhooks = validating_webhooks + mutating_webhooks
            
            for webhook in all_webhooks:
                if self._is_configured_webhook(webhook['name']):
                    total_critical += 1
                    if self.check_webhook_endpoint_health(webhook):
                        healthy_count += 1
            
            # Check configured webhook deployments
            deployments_ready = True
            for webhook_name, namespace in self.configured_webhooks:
                deployment_name = self._get_deployment_name_for_webhook(webhook_name)
                if deployment_name and namespace:
                    if not self._check_deployment_ready(deployment_name, namespace):
                        deployments_ready = False
                        break
            
            return {
                'validating_webhooks': len(validating_webhooks),
                'mutating_webhooks': len(mutating_webhooks),
                'healthy_critical_webhooks': healthy_count,
                'total_critical_webhooks': total_critical,
                'critical_deployments_ready': deployments_ready
            }
            
        except Exception as e:
            self.logger.error(f"Error getting webhook status summary: {str(e)}")
            return {
                'error': str(e)
            }