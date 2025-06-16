import boto3
import logging
import subprocess
import json
import time
from datetime import datetime, timedelta

class BootstrapValidatorError(Exception):
    pass

class BootstrapValidator:
    def __init__(self, dry_run=False):
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        self.validation_timeout = 600  # 10 minutes timeout for bootstrap validation
        
        # Critical system pods that must be ready before other workloads
        self.critical_system_pods = {
            'kube-system': {
                'coredns': {'min_replicas': 2, 'deployment': 'coredns'},
                'aws-load-balancer-controller': {'min_replicas': 1, 'deployment': 'aws-load-balancer-controller'},  
                'cluster-autoscaler': {'min_replicas': 1, 'deployment': 'cluster-autoscaler'},
                'ebs-csi-controller': {'min_replicas': 1, 'deployment': 'ebs-csi-controller'},
                'metrics-server': {'min_replicas': 1, 'deployment': 'metrics-server'}
            },
            'amazon-cloudwatch': {
                'cloudwatch-agent': {'min_replicas': 1, 'deployment': 'cloudwatch-agent'}
            },
            'external-dns': {
                'external-dns': {'min_replicas': 1, 'deployment': 'external-dns'}
            },
            'kyverno': {
                'kyverno-admission-controller': {'min_replicas': 1, 'deployment': 'kyverno-admission-controller'},
                'kyverno-background-controller': {'min_replicas': 1, 'deployment': 'kyverno-background-controller'},
                'kyverno-cleanup-controller': {'min_replicas': 1, 'deployment': 'kyverno-cleanup-controller'},
                'kyverno-reports-controller': {'min_replicas': 1, 'deployment': 'kyverno-reports-controller'}
            },
            'snapshot-controller': {
                'snapshot-controller': {'min_replicas': 1, 'deployment': 'snapshot-controller'}
            }
        }
        
        # Minimum nodes required for system workloads
        self.min_nodes_for_system = 2
        
        if self.dry_run:
            self.logger.info("Bootstrap Validator initialized in DRY RUN mode")

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

    def get_cluster_nodes(self):
        """Get all cluster nodes and their status."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would get cluster nodes")
                return [
                    {'name': 'mock-node-1', 'status': 'Ready', 'schedulable': True},
                    {'name': 'mock-node-2', 'status': 'Ready', 'schedulable': True}
                ]
            
            command = ['kubectl', 'get', 'nodes', '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    nodes_data = json.loads(stdout)
                    nodes = []
                    
                    for item in nodes_data.get('items', []):
                        node_name = item['metadata']['name']
                        
                        # Check node status
                        conditions = item.get('status', {}).get('conditions', [])
                        ready_condition = next((c for c in conditions if c['type'] == 'Ready'), None)
                        node_ready = ready_condition and ready_condition['status'] == 'True'
                        
                        # Check if node is schedulable (not cordoned)
                        schedulable = not item.get('spec', {}).get('unschedulable', False)
                        
                        nodes.append({
                            'name': node_name,
                            'status': 'Ready' if node_ready else 'NotReady',
                            'schedulable': schedulable
                        })
                    
                    self.logger.info(f"Found {len(nodes)} nodes in cluster")
                    return nodes
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse nodes JSON: {str(e)}")
                    return []
            else:
                self.logger.error(f"Failed to get cluster nodes: {stderr}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting cluster nodes: {str(e)}")
            return []

    def validate_minimum_nodes(self, min_nodes_required):
        """Validate that cluster has minimum number of ready and schedulable nodes."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would validate minimum {min_nodes_required} nodes are available")
                return True
            
            nodes = self.get_cluster_nodes()
            
            # Count ready and schedulable nodes
            ready_schedulable_nodes = [
                node for node in nodes 
                if node['status'] == 'Ready' and node['schedulable']
            ]
            
            ready_count = len(ready_schedulable_nodes)
            
            self.logger.info(f"Found {ready_count} ready and schedulable nodes "
                           f"(minimum required: {min_nodes_required})")
            
            if ready_count < min_nodes_required:
                self.logger.error(f"Insufficient nodes for bootstrap: {ready_count} < {min_nodes_required}")
                return False
            
            # Also check against system minimum
            if ready_count < self.min_nodes_for_system:
                self.logger.error(f"Insufficient nodes for system workloads: {ready_count} < {self.min_nodes_for_system}")
                return False
            
            self.logger.info(f"Node count validation passed: {ready_count} nodes available")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating minimum nodes: {str(e)}")
            return False

    def check_deployment_ready(self, deployment_name, namespace, min_replicas=1):
        """Check if a deployment is ready with minimum replicas."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would check deployment {deployment_name} in {namespace}")
                return True
            
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
                # Deployment might not exist yet
                if "not found" in stderr.lower():
                    self.logger.info(f"Deployment {deployment_name} in {namespace} not found (optional)")
                    return True  # Consider optional deployments as "ready"
                else:
                    self.logger.warning(f"Failed to get deployment {deployment_name}: {stderr}")
                    return False
                
        except Exception as e:
            self.logger.error(f"Error checking deployment {deployment_name} readiness: {str(e)}")
            return False

    def check_coredns_ready(self):
        """Special check for CoreDNS as it's critical for cluster DNS resolution."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would check CoreDNS readiness")
                return True
            
            # Check CoreDNS deployment
            if not self.check_deployment_ready('coredns', 'kube-system', min_replicas=2):
                self.logger.error("CoreDNS deployment is not ready")
                return False
            
            # Test DNS resolution
            test_command = [
                'kubectl', 'run', 'dns-test', '--image=busybox:1.35', '--rm', '-it', '--restart=Never',
                '--', 'nslookup', 'kubernetes.default.svc.cluster.local'
            ]
            
            self.logger.info("Testing DNS resolution...")
            success, stdout, stderr = self._run_kubectl_command(test_command)
            
            if success and 'kubernetes.default.svc.cluster.local' in stdout:
                self.logger.info("DNS resolution test passed")
                return True
            else:
                self.logger.warning(f"DNS resolution test failed: {stderr}")
                # Don't fail bootstrap just for DNS test failure, deployment check is more reliable
                return True
                
        except Exception as e:
            self.logger.error(f"Error checking CoreDNS readiness: {str(e)}")
            return False

    def validate_system_pods_ready(self, timeout=600):
        """Validate that all critical system pods are ready."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would validate system pods ready (timeout: {timeout}s)")
                return True
            
            self.logger.info(f"Validating system pods are ready (timeout: {timeout}s)...")
            
            start_time = datetime.now()
            timeout_time = start_time + timedelta(seconds=timeout)
            
            while datetime.now() < timeout_time:
                all_ready = True
                not_ready_pods = []
                
                # Check each critical system pod
                for namespace, pods in self.critical_system_pods.items():
                    for pod_name, config in pods.items():
                        deployment_name = config['deployment']
                        min_replicas = config['min_replicas']
                        
                        if not self.check_deployment_ready(deployment_name, namespace, min_replicas):
                            all_ready = False
                            not_ready_pods.append(f"{namespace}/{deployment_name}")
                
                if all_ready:
                    self.logger.info("All critical system pods are ready")
                    
                    # Special check for CoreDNS
                    if self.check_coredns_ready():
                        self.logger.info("System pod validation completed successfully")
                        return True
                    else:
                        self.logger.warning("CoreDNS check failed, but continuing...")
                        return True  # Don't fail the entire bootstrap for CoreDNS
                else:
                    self.logger.info(f"Waiting for system pods to be ready: {not_ready_pods}")
                    time.sleep(15)
            
            # Timeout reached
            self.logger.error(f"Timeout waiting for system pods to be ready after {timeout} seconds")
            return False
            
        except Exception as e:
            self.logger.error(f"Error validating system pods ready: {str(e)}")
            return False

    def check_node_taints_and_tolerations(self):
        """Check for node taints that might prevent system pods from scheduling."""
        try:
            if self.dry_run:
                self.logger.info("[DRY RUN] Would check node taints and tolerations")
                return True
            
            command = ['kubectl', 'get', 'nodes', '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    nodes_data = json.loads(stdout)
                    tainted_nodes = []
                    
                    for item in nodes_data.get('items', []):
                        node_name = item['metadata']['name']
                        taints = item.get('spec', {}).get('taints', [])
                        
                        # Check for problematic taints
                        blocking_taints = []
                        for taint in taints:
                            taint_key = taint.get('key', '')
                            taint_effect = taint.get('effect', '')
                            
                            # Skip known acceptable taints
                            if taint_key.startswith('node.kubernetes.io/'):
                                continue
                                
                            if taint_effect in ['NoSchedule', 'NoExecute']:
                                blocking_taints.append(f"{taint_key}:{taint_effect}")
                        
                        if blocking_taints:
                            tainted_nodes.append({
                                'node': node_name,
                                'taints': blocking_taints
                            })
                    
                    if tainted_nodes:
                        self.logger.warning(f"Found nodes with potentially blocking taints: {tainted_nodes}")
                        # Don't fail bootstrap, just warn
                        return True
                    else:
                        self.logger.info("No blocking node taints found")
                        return True
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse nodes JSON for taint check: {str(e)}")
                    return True  # Don't fail bootstrap for this
            else:
                self.logger.warning(f"Failed to get nodes for taint check: {stderr}")
                return True  # Don't fail bootstrap for this
                
        except Exception as e:
            self.logger.error(f"Error checking node taints: {str(e)}")
            return True  # Don't fail bootstrap for this

    def validate_bootstrap_requirements(self, cluster_name, min_nodes):
        """Comprehensive bootstrap validation."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would validate bootstrap requirements for {cluster_name} with {min_nodes} minimum nodes")
                return True
            
            self.logger.info(f"Validating bootstrap requirements for cluster {cluster_name}")
            
            # Step 1: Validate minimum nodes
            if not self.validate_minimum_nodes(min_nodes):
                raise BootstrapValidatorError("Insufficient nodes for safe bootstrap")
            
            # Step 2: Check node taints
            if not self.check_node_taints_and_tolerations():
                self.logger.warning("Node taint validation had issues, but continuing...")
            
            # Step 3: Wait for system pods to be ready
            if not self.validate_system_pods_ready(timeout=self.validation_timeout):
                raise BootstrapValidatorError("System pods failed to become ready within timeout")
            
            self.logger.info(f"Bootstrap validation completed successfully for cluster {cluster_name}")
            return True
            
        except BootstrapValidatorError:
            raise
        except Exception as e:
            self.logger.error(f"Error during bootstrap validation: {str(e)}")
            raise BootstrapValidatorError(f"Bootstrap validation failed: {str(e)}")

    def get_bootstrap_status_summary(self):
        """Get a summary of bootstrap validation status."""
        try:
            if self.dry_run:
                return {
                    'total_nodes': 3,
                    'ready_nodes': 3,
                    'schedulable_nodes': 3,
                    'system_deployments_ready': 8,
                    'system_deployments_total': 8,
                    'bootstrap_ready': True
                }
            
            nodes = self.get_cluster_nodes()
            ready_nodes = [n for n in nodes if n['status'] == 'Ready']
            schedulable_nodes = [n for n in nodes if n['schedulable']]
            
            # Check system deployments
            ready_deployments = 0
            total_deployments = 0
            
            for namespace, pods in self.critical_system_pods.items():
                for pod_name, config in pods.items():
                    total_deployments += 1
                    if self.check_deployment_ready(config['deployment'], namespace, config['min_replicas']):
                        ready_deployments += 1
            
            bootstrap_ready = (len(schedulable_nodes) >= self.min_nodes_for_system and 
                             ready_deployments == total_deployments)
            
            return {
                'total_nodes': len(nodes),
                'ready_nodes': len(ready_nodes),
                'schedulable_nodes': len(schedulable_nodes),
                'system_deployments_ready': ready_deployments,
                'system_deployments_total': total_deployments,
                'bootstrap_ready': bootstrap_ready
            }
            
        except Exception as e:
            self.logger.error(f"Error getting bootstrap status summary: {str(e)}")
            return {
                'error': str(e)
            }

    def wait_for_nodes_ready(self, expected_node_count, timeout=300):
        """Wait for expected number of nodes to be ready and schedulable."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would wait for {expected_node_count} nodes to be ready")
                return True
            
            self.logger.info(f"Waiting for {expected_node_count} nodes to be ready (timeout: {timeout}s)")
            
            start_time = datetime.now()
            timeout_time = start_time + timedelta(seconds=timeout)
            
            while datetime.now() < timeout_time:
                nodes = self.get_cluster_nodes()
                ready_schedulable_nodes = [
                    node for node in nodes 
                    if node['status'] == 'Ready' and node['schedulable']
                ]
                
                ready_count = len(ready_schedulable_nodes)
                
                if ready_count >= expected_node_count:
                    self.logger.info(f"Required number of nodes are ready: {ready_count}/{expected_node_count}")
                    return True
                
                self.logger.info(f"Waiting for nodes to be ready: {ready_count}/{expected_node_count}")
                time.sleep(15)
            
            # Timeout reached
            nodes = self.get_cluster_nodes()
            ready_count = len([n for n in nodes if n['status'] == 'Ready' and n['schedulable']])
            self.logger.error(f"Timeout waiting for nodes to be ready: {ready_count}/{expected_node_count}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for nodes ready: {str(e)}")
            return False