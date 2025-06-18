import boto3
import logging
import subprocess
import json
import time
from datetime import datetime, timedelta

class DependencyManagerError(Exception):
    pass

class DependencyManager:
    def __init__(self, dry_run=False, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        self.config_manager = config_manager
        self.startup_timeout = config_manager.get_timeout('dependency_startup_timeout', 300) if config_manager else 300  # 5 minutes timeout for each dependency tier
        
        # Define dependency tiers - services must start in this order
        self.dependency_tiers = [
            # Tier 1: Core Kubernetes components (must be first)
            {
                'name': 'core-kubernetes',
                'description': 'Core Kubernetes system components',
                'services': [
                    {'name': 'coredns', 'namespace': 'kube-system', 'type': 'deployment', 'min_replicas': 2, 'critical': True},
                    {'name': 'kube-proxy', 'namespace': 'kube-system', 'type': 'daemonset', 'critical': True}
                ]
            },
            
            # Tier 2: Storage and networking infrastructure
            {
                'name': 'infrastructure',
                'description': 'Storage and networking infrastructure',
                'services': [
                    {'name': 'ebs-csi-controller', 'namespace': 'kube-system', 'type': 'deployment', 'min_replicas': 1, 'critical': True},
                    {'name': 'aws-load-balancer-controller', 'namespace': 'kube-system', 'type': 'deployment', 'min_replicas': 1, 'critical': True},
                    {'name': 'vpc-cni', 'namespace': 'kube-system', 'type': 'daemonset', 'critical': True}
                ]
            },
            
            # Tier 3: Cluster management and autoscaling
            {
                'name': 'cluster-management',
                'description': 'Cluster management and autoscaling',
                'services': [
                    {'name': 'cluster-autoscaler', 'namespace': 'kube-system', 'type': 'deployment', 'min_replicas': 1, 'critical': True},
                    {'name': 'metrics-server', 'namespace': 'kube-system', 'type': 'deployment', 'min_replicas': 1, 'critical': True}
                ]
            },
            
            # Tier 4: Admission controllers and policy enforcement
            {
                'name': 'admission-control',
                'description': 'Admission controllers and policy enforcement',
                'services': [
                    {'name': 'kyverno-admission-controller', 'namespace': 'kyverno', 'type': 'deployment', 'min_replicas': 1, 'critical': True},
                    {'name': 'kyverno-background-controller', 'namespace': 'kyverno', 'type': 'deployment', 'min_replicas': 1, 'critical': False},
                    {'name': 'kyverno-cleanup-controller', 'namespace': 'kyverno', 'type': 'deployment', 'min_replicas': 1, 'critical': False},
                    {'name': 'kyverno-reports-controller', 'namespace': 'kyverno', 'type': 'deployment', 'min_replicas': 1, 'critical': False}
                ]
            },
            
            # Tier 5: Observability and monitoring
            {
                'name': 'observability',
                'description': 'Observability and monitoring services',
                'services': [
                    {'name': 'cloudwatch-agent', 'namespace': 'amazon-cloudwatch', 'type': 'deployment', 'min_replicas': 1, 'critical': False},
                    {'name': 'fluent-bit', 'namespace': 'amazon-cloudwatch', 'type': 'daemonset', 'critical': False}
                ]
            },
            
            # Tier 6: DNS and external services
            {
                'name': 'external-services',
                'description': 'DNS and external service management',
                'services': [
                    {'name': 'external-dns', 'namespace': 'external-dns', 'type': 'deployment', 'min_replicas': 1, 'critical': False}
                ]
            },
            
            # Tier 7: Storage management and snapshots
            {
                'name': 'storage-management',
                'description': 'Storage management and snapshot controllers',
                'services': [
                    {'name': 'snapshot-controller', 'namespace': 'snapshot-controller', 'type': 'deployment', 'min_replicas': 1, 'critical': False}
                ]
            }
        ]
        
        if self.dry_run:
            self.logger.info("Dependency Manager initialized in DRY RUN mode")

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
                timeout=120
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

    def check_service_ready(self, service_config):
        """Check if a specific service is ready."""
        try:
            service_name = service_config['name']
            namespace = service_config['namespace']
            service_type = service_config['type']
            min_replicas = service_config.get('min_replicas', 1)
            
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would check service {service_name} in {namespace}")
                return True
            
            if service_type == 'deployment':
                return self._check_deployment_ready(service_name, namespace, min_replicas)
            elif service_type == 'daemonset':
                return self._check_daemonset_ready(service_name, namespace)
            else:
                self.logger.warning(f"Unknown service type {service_type} for {service_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error checking service {service_config['name']} readiness: {str(e)}")
            return False

    def _check_deployment_ready(self, deployment_name, namespace, min_replicas=1):
        """Check if a deployment is ready."""
        try:
            command = ['kubectl', 'get', 'deployment', deployment_name, '-n', namespace, '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    deployment_data = json.loads(stdout)
                    status = deployment_data.get('status', {})
                    
                    replicas = status.get('replicas', 0)
                    ready_replicas = status.get('readyReplicas', 0)
                    available_replicas = status.get('availableReplicas', 0)
                    
                    # Check if deployment meets minimum requirements
                    is_ready = (ready_replicas >= min_replicas and 
                               available_replicas >= min_replicas and
                               ready_replicas == replicas)
                    
                    self.logger.debug(f"Deployment {deployment_name} in {namespace}: "
                                    f"{ready_replicas}/{replicas} ready, "
                                    f"{available_replicas} available (min required: {min_replicas})")
                    
                    return is_ready
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse deployment {deployment_name} JSON")
                    return False
            else:
                # Deployment might not exist
                if "not found" in stderr.lower():
                    self.logger.info(f"Deployment {deployment_name} in {namespace} not found (skipping)")
                    return True  # Consider missing optional deployments as "ready"
                else:
                    self.logger.warning(f"Failed to get deployment {deployment_name}: {stderr}")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error checking deployment {deployment_name} readiness: {str(e)}")
            return False

    def _check_daemonset_ready(self, daemonset_name, namespace):
        """Check if a daemonset is ready."""
        try:
            command = ['kubectl', 'get', 'daemonset', daemonset_name, '-n', namespace, '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    daemonset_data = json.loads(stdout)
                    status = daemonset_data.get('status', {})
                    
                    desired_number_scheduled = status.get('desiredNumberScheduled', 0)
                    number_ready = status.get('numberReady', 0)
                    number_available = status.get('numberAvailable', 0)
                    
                    # DaemonSet is ready if all desired pods are ready and available
                    is_ready = (desired_number_scheduled > 0 and 
                               number_ready == desired_number_scheduled and
                               number_available == desired_number_scheduled)
                    
                    self.logger.debug(f"DaemonSet {daemonset_name} in {namespace}: "
                                    f"{number_ready}/{desired_number_scheduled} ready, "
                                    f"{number_available} available")
                    
                    return is_ready
                    
                except json.JSONDecodeError:
                    self.logger.warning(f"Failed to parse daemonset {daemonset_name} JSON")
                    return False
            else:
                # DaemonSet might not exist
                if "not found" in stderr.lower():
                    self.logger.info(f"DaemonSet {daemonset_name} in {namespace} not found (skipping)")
                    return True  # Consider missing optional daemonsets as "ready"
                else:
                    self.logger.warning(f"Failed to get daemonset {daemonset_name}: {stderr}")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error checking daemonset {daemonset_name} readiness: {str(e)}")
            return False

    def wait_for_tier_ready(self, tier_config, timeout=None):
        """Wait for all services in a dependency tier to be ready."""
        try:
            if timeout is None:
                timeout = self.startup_timeout
                
            tier_name = tier_config['name']
            tier_description = tier_config['description']
            services = tier_config['services']
            
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would wait for tier '{tier_name}' to be ready")
                return True
            
            self.logger.info(f"Waiting for tier '{tier_name}' ({tier_description}) to be ready...")
            
            start_time = datetime.now()
            timeout_time = start_time + timedelta(seconds=timeout)
            
            while datetime.now() < timeout_time:
                all_ready = True
                not_ready_services = []
                
                for service in services:
                    if not self.check_service_ready(service):
                        all_ready = False
                        not_ready_services.append(f"{service['namespace']}/{service['name']}")
                        
                        # For critical services, be more verbose
                        if service.get('critical', False):
                            self.logger.info(f"Critical service not ready: {service['namespace']}/{service['name']}")
                
                if all_ready:
                    self.logger.info(f"Tier '{tier_name}' is ready - all services are healthy")
                    return True
                
                if not_ready_services:
                    self.logger.info(f"Waiting for services in tier '{tier_name}': {not_ready_services}")
                
                time.sleep(15)
            
            # Timeout reached
            self.logger.error(f"Timeout waiting for tier '{tier_name}' to be ready after {timeout} seconds")
            
            # Log which services are still not ready
            not_ready_critical = []
            not_ready_optional = []
            
            for service in services:
                if not self.check_service_ready(service):
                    service_name = f"{service['namespace']}/{service['name']}"
                    if service.get('critical', False):
                        not_ready_critical.append(service_name)
                    else:
                        not_ready_optional.append(service_name)
            
            if not_ready_critical:
                self.logger.error(f"Critical services not ready in tier '{tier_name}': {not_ready_critical}")
                return False
            elif not_ready_optional:
                self.logger.warning(f"Optional services not ready in tier '{tier_name}': {not_ready_optional}")
                # Continue even if optional services aren't ready
                return True
            else:
                # This shouldn't happen, but handle it
                self.logger.warning(f"Tier '{tier_name}' timeout but no services identified as not ready")
                return True
                
        except Exception as e:
            self.logger.error(f"Error waiting for tier {tier_config['name']} to be ready: {str(e)}")
            return False

    def validate_service_dependencies(self, timeout_per_tier=None):
        """Validate all service dependencies in the correct order."""
        try:
            if timeout_per_tier is None:
                timeout_per_tier = self.startup_timeout
                
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would validate service dependencies across {len(self.dependency_tiers)} tiers")
                return True
            
            self.logger.info(f"Validating service dependencies across {len(self.dependency_tiers)} tiers...")
            
            failed_tiers = []
            
            for i, tier in enumerate(self.dependency_tiers, 1):
                tier_name = tier['name']
                self.logger.info(f"Starting tier {i}/{len(self.dependency_tiers)}: {tier_name}")
                
                if self.wait_for_tier_ready(tier, timeout_per_tier):
                    self.logger.info(f"✓ Tier {i} '{tier_name}' completed successfully")
                else:
                    self.logger.error(f"✗ Tier {i} '{tier_name}' failed to become ready")
                    failed_tiers.append(tier_name)
                    
                    # Check if this tier contains critical services
                    has_critical_services = any(service.get('critical', False) for service in tier['services'])
                    
                    if has_critical_services:
                        self.logger.error(f"Tier '{tier_name}' contains critical services - stopping validation")
                        raise DependencyManagerError(f"Critical tier '{tier_name}' failed to become ready")
                    else:
                        self.logger.warning(f"Tier '{tier_name}' failed but contains no critical services - continuing")
            
            if failed_tiers:
                self.logger.warning(f"Some tiers failed but cluster is functional: {failed_tiers}")
            else:
                self.logger.info("All dependency tiers validated successfully")
            
            return True
            
        except DependencyManagerError:
            raise
        except Exception as e:
            self.logger.error(f"Error during service dependency validation: {str(e)}")
            raise DependencyManagerError(f"Service dependency validation failed: {str(e)}")

    def get_dependency_status_summary(self):
        """Get a summary of all dependency tier statuses."""
        try:
            if self.dry_run:
                return {
                    'total_tiers': len(self.dependency_tiers),
                    'ready_tiers': len(self.dependency_tiers),
                    'total_services': 15,
                    'ready_services': 15,
                    'critical_services_ready': 10,
                    'dependencies_satisfied': True
                }
            
            tier_status = []
            total_services = 0
            ready_services = 0
            critical_services_ready = 0
            total_critical_services = 0
            
            for tier in self.dependency_tiers:
                tier_services = tier['services']
                tier_ready_count = 0
                
                for service in tier_services:
                    total_services += 1
                    if service.get('critical', False):
                        total_critical_services += 1
                    
                    if self.check_service_ready(service):
                        ready_services += 1
                        tier_ready_count += 1
                        if service.get('critical', False):
                            critical_services_ready += 1
                
                is_tier_ready = tier_ready_count == len(tier_services)
                
                tier_status.append({
                    'name': tier['name'],
                    'ready': is_tier_ready,
                    'ready_services': tier_ready_count,
                    'total_services': len(tier_services)
                })
            
            ready_tiers = sum(1 for tier in tier_status if tier['ready'])
            dependencies_satisfied = (critical_services_ready == total_critical_services)
            
            return {
                'total_tiers': len(self.dependency_tiers),
                'ready_tiers': ready_tiers,
                'total_services': total_services,
                'ready_services': ready_services,
                'critical_services_ready': critical_services_ready,
                'total_critical_services': total_critical_services,
                'dependencies_satisfied': dependencies_satisfied,
                'tier_details': tier_status
            }
            
        except Exception as e:
            self.logger.error(f"Error getting dependency status summary: {str(e)}")
            return {
                'error': str(e)
            }

    def check_critical_path_ready(self):
        """Quick check if the critical path services are ready."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would check critical path readiness")
                return True
            
            critical_services = []
            
            # Collect all critical services across all tiers
            for tier in self.dependency_tiers:
                for service in tier['services']:
                    if service.get('critical', False):
                        critical_services.append(service)
            
            self.logger.info(f"Checking {len(critical_services)} critical services...")
            
            not_ready_critical = []
            
            for service in critical_services:
                if not self.check_service_ready(service):
                    not_ready_critical.append(f"{service['namespace']}/{service['name']}")
            
            if not_ready_critical:
                self.logger.error(f"Critical services not ready: {not_ready_critical}")
                return False
            else:
                self.logger.info("All critical services are ready")
                return True
                
        except Exception as e:
            self.logger.error(f"Error checking critical path readiness: {str(e)}")
            return False