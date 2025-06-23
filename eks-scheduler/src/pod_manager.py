import boto3
import logging
import subprocess
import json
import time
from datetime import datetime, timedelta

class PodManagerError(Exception):
    pass

class PodManager:
    def __init__(self, dry_run=False, config_manager=None):
        self.logger = logging.getLogger(__name__)
        self.dry_run = dry_run
        self.config_manager = config_manager
        self.drain_timeout = config_manager.get_timeout('drain_timeout', 300) if config_manager else 300  # 5 minutes default timeout
        self.grace_period = config_manager.get_timeout('pod_grace_period', 30) if config_manager else 30    # 30 seconds grace period for pod termination
        
        if self.dry_run:
            self.logger.info("Pod Manager initialized in DRY RUN mode")

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

    def get_nodes_in_nodegroup(self, node_group_name):
        """Get all nodes belonging to a specific node group."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would get nodes for node group {node_group_name}")
                return ["mock-node-1", "mock-node-2"]
            
            # Get node label from config or use EKS default
            node_label = self.config_manager.get('services', 'node_group_label', 'eks.amazonaws.com/nodegroup') if self.config_manager else 'eks.amazonaws.com/nodegroup'
            
            # Get nodes with the node group label
            command = [
                'kubectl', 'get', 'nodes', 
                '-l', f'{node_label}={node_group_name}',
                '-o', 'jsonpath={.items[*].metadata.name}'
            ]
            
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success and stdout.strip():
                nodes = stdout.strip().split()
                self.logger.info(f"Found {len(nodes)} nodes in node group {node_group_name}: {nodes}")
                return nodes
            else:
                self.logger.warning(f"No nodes found for node group {node_group_name}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting nodes for node group {node_group_name}: {str(e)}")
            raise PodManagerError(f"Error getting nodes: {str(e)}")

    def get_pods_on_node(self, node_name):
        """Get all pods running on a specific node."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would get pods on node {node_name}")
                return [
                    {"name": "mock-pod-1", "namespace": "default"},
                    {"name": "coredns-abc123", "namespace": "kube-system"}
                ]
            
            command = [
                'kubectl', 'get', 'pods', '--all-namespaces',
                '--field-selector', f'spec.nodeName={node_name}',
                '-o', 'json'
            ]
            
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    pod_data = json.loads(stdout)
                    pods = []
                    
                    for item in pod_data.get('items', []):
                        # Skip pods that are already terminating or succeeded/failed
                        phase = item.get('status', {}).get('phase', '')
                        if phase in ['Succeeded', 'Failed']:
                            continue
                            
                        # Skip daemonset pods (they'll be recreated automatically)
                        owner_refs = item.get('metadata', {}).get('ownerReferences', [])
                        is_daemonset = any(ref.get('kind') == 'DaemonSet' for ref in owner_refs)
                        
                        pods.append({
                            'name': item['metadata']['name'],
                            'namespace': item['metadata']['namespace'],
                            'phase': phase,
                            'is_daemonset': is_daemonset,
                            'owner_refs': owner_refs
                        })
                    
                    self.logger.info(f"Found {len(pods)} pods on node {node_name}")
                    return pods
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse pod JSON: {str(e)}")
                    return []
            else:
                self.logger.warning(f"Failed to get pods on node {node_name}: {stderr}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting pods on node {node_name}: {str(e)}")
            raise PodManagerError(f"Error getting pods: {str(e)}")

    def check_pod_disruption_budgets(self, namespace, pod_name):
        """Check if pod is protected by PodDisruptionBudget."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would check PDB for pod {pod_name} in {namespace}")
                return False
            
            # Get all PDBs in the namespace
            command = ['kubectl', 'get', 'pdb', '-n', namespace, '-o', 'json']
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                try:
                    pdb_data = json.loads(stdout)
                    
                    # Get pod labels
                    pod_command = ['kubectl', 'get', 'pod', pod_name, '-n', namespace, '-o', 'json']
                    pod_success, pod_stdout, _ = self._run_kubectl_command(pod_command)
                    
                    if pod_success:
                        pod_info = json.loads(pod_stdout)
                        pod_labels = pod_info.get('metadata', {}).get('labels', {})
                        
                        # Check if any PDB matches this pod
                        for pdb in pdb_data.get('items', []):
                            selector = pdb.get('spec', {}).get('selector', {}).get('matchLabels', {})
                            
                            # Check if all selector labels match pod labels
                            if all(pod_labels.get(k) == v for k, v in selector.items()):
                                self.logger.info(f"Pod {pod_name} is protected by PDB {pdb['metadata']['name']}")
                                return True
                                
                except json.JSONDecodeError:
                    pass
                    
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking PDB for pod {pod_name}: {str(e)}")
            return False

    def cordon_node(self, node_name):
        """Cordon a node to prevent new pods from being scheduled."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would cordon node {node_name}")
                return True
            
            command = ['kubectl', 'cordon', node_name]
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                self.logger.info(f"Successfully cordoned node {node_name}")
                return True
            else:
                self.logger.error(f"Failed to cordon node {node_name}: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error cordoning node {node_name}: {str(e)}")
            return False

    def drain_node(self, node_name, force=False):
        """Drain a node by evicting all pods."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would drain node {node_name}")
                return True
            
            self.logger.info(f"Draining node {node_name}...")
            
            # First cordon the node
            if not self.cordon_node(node_name):
                self.logger.warning(f"Failed to cordon node {node_name}, continuing with drain")
            
            # Build drain command
            command = [
                'kubectl', 'drain', node_name,
                '--ignore-daemonsets',
                '--delete-emptydir-data',
                f'--timeout={self.drain_timeout}s',
                f'--grace-period={self.grace_period}'
            ]
            
            if force:
                command.append('--force')
            
            success, stdout, stderr = self._run_kubectl_command(command)
            
            if success:
                self.logger.info(f"Successfully drained node {node_name}")
                return True
            else:
                self.logger.error(f"Failed to drain node {node_name}: {stderr}")
                
                # If initial drain failed and not forced, try with force
                if not force and "cannot delete Pods not managed by" in stderr:
                    self.logger.warning(f"Retrying drain of {node_name} with --force")
                    return self.drain_node(node_name, force=True)
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error draining node {node_name}: {str(e)}")
            return False

    def wait_for_pods_termination(self, node_name, timeout=300):
        """Wait for all pods on a node to terminate."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would wait for pods on {node_name} to terminate")
                return True
            
            start_time = datetime.now()
            timeout_time = start_time + timedelta(seconds=timeout)
            
            self.logger.info(f"Waiting for pods on {node_name} to terminate (timeout: {timeout}s)")
            
            while datetime.now() < timeout_time:
                pods = self.get_pods_on_node(node_name)
                
                # Filter out daemonset pods (they're expected to remain)
                non_daemonset_pods = [p for p in pods if not p.get('is_daemonset', False)]
                
                if not non_daemonset_pods:
                    self.logger.info(f"All non-daemonset pods terminated on {node_name}")
                    return True
                
                self.logger.debug(f"Still waiting for {len(non_daemonset_pods)} pods to terminate on {node_name}")
                time.sleep(10)
            
            # Timeout reached
            remaining_pods = [p for p in self.get_pods_on_node(node_name) if not p.get('is_daemonset', False)]
            self.logger.warning(f"Timeout waiting for pods to terminate on {node_name}. "
                              f"Remaining non-daemonset pods: {len(remaining_pods)}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error waiting for pod termination on {node_name}: {str(e)}")
            return False

    def drain_node_group(self, node_group_name):
        """Drain all nodes in a node group."""
        try:
            self.logger.info(f"Starting drain operation for node group {node_group_name}")
            
            nodes = self.get_nodes_in_nodegroup(node_group_name)
            
            if not nodes:
                self.logger.info(f"No nodes found in node group {node_group_name}")
                return True
            
            results = []
            
            # Drain each node
            for node_name in nodes:
                self.logger.info(f"Draining node {node_name} from node group {node_group_name}")
                
                drain_success = self.drain_node(node_name)
                
                if drain_success:
                    # Wait for pods to terminate
                    termination_success = self.wait_for_pods_termination(node_name)
                    
                    results.append({
                        'node': node_name,
                        'drain_success': drain_success,
                        'termination_success': termination_success,
                        'status': 'success' if termination_success else 'partial'
                    })
                else:
                    results.append({
                        'node': node_name,
                        'drain_success': drain_success,
                        'termination_success': False,
                        'status': 'failed'
                    })
            
            # Summary
            successful_drains = sum(1 for r in results if r['status'] == 'success')
            total_nodes = len(results)
            
            self.logger.info(f"Node group {node_group_name} drain summary: "
                           f"{successful_drains}/{total_nodes} nodes drained successfully")
            
            return successful_drains == total_nodes, results
            
        except Exception as e:
            self.logger.error(f"Error draining node group {node_group_name}: {str(e)}")
            raise PodManagerError(f"Error draining node group: {str(e)}")

    def uncordon_nodes_in_nodegroup(self, node_group_name):
        """Uncordon all nodes in a node group after scaling up."""
        try:
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would uncordon nodes in node group {node_group_name}")
                return True
            
            nodes = self.get_nodes_in_nodegroup(node_group_name)
            
            if not nodes:
                self.logger.info(f"No nodes found in node group {node_group_name}")
                return True
            
            success_count = 0
            
            for node_name in nodes:
                command = ['kubectl', 'uncordon', node_name]
                success, stdout, stderr = self._run_kubectl_command(command)
                
                if success:
                    self.logger.info(f"Successfully uncordoned node {node_name}")
                    success_count += 1
                else:
                    self.logger.error(f"Failed to uncordon node {node_name}: {stderr}")
            
            self.logger.info(f"Uncordoned {success_count}/{len(nodes)} nodes in node group {node_group_name}")
            return success_count == len(nodes)
            
        except Exception as e:
            self.logger.error(f"Error uncordoning nodes in node group {node_group_name}: {str(e)}")
            return False