#!/usr/bin/env python3

from kubernetes import client, config
from kubernetes.client.rest import ApiException
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KubernetesResourceLister:
    def __init__(self):
        """Initialize Kubernetes client with appropriate configuration."""
        try:
            # Try to load in-cluster config first (if running inside a pod)
            config.load_incluster_config()
            logger.info("Using in-cluster configuration")
        except config.ConfigException:
            try:
                # Fall back to kubeconfig file
                config.load_kube_config()
                logger.info("Using kubeconfig file")
            except config.ConfigException as e:
                logger.error(f"Could not configure kubernetes client: {e}")
                sys.exit(1)
        
        # Initialize API clients
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
    
    def list_namespaces(self):
        """List all namespaces in the cluster."""
        try:
            logger.info("Fetching namespaces...")
            namespaces = self.v1.list_namespace()
            
            print("\n" + "="*50)
            print("NAMESPACES")
            print("="*50)
            print(f"{'NAME':<30} {'STATUS':<15} {'AGE'}")
            print("-" * 50)
            
            for ns in namespaces.items:
                age = self._calculate_age(ns.metadata.creation_timestamp)
                status = ns.status.phase if ns.status.phase else "Unknown"
                print(f"{ns.metadata.name:<30} {status:<15} {age}")
            
            return [ns.metadata.name for ns in namespaces.items]
            
        except ApiException as e:
            logger.error(f"Error listing namespaces: {e}")
            return []
    
    def list_deployments(self, namespace=None):
        """List deployments in specified namespace or all namespaces."""
        try:
            if namespace:
                logger.info(f"Fetching deployments in namespace: {namespace}")
                deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
            else:
                logger.info("Fetching deployments from all namespaces...")
                deployments = self.apps_v1.list_deployment_for_all_namespaces()
            
            print("\n" + "="*80)
            print("DEPLOYMENTS")
            print("="*80)
            print(f"{'NAMESPACE':<20} {'NAME':<25} {'READY':<10} {'UP-TO-DATE':<10} {'AVAILABLE':<10} {'AGE'}")
            print("-" * 80)
            
            for deploy in deployments.items:
                ns = deploy.metadata.namespace
                name = deploy.metadata.name
                ready = f"{deploy.status.ready_replicas or 0}/{deploy.status.replicas or 0}"
                up_to_date = deploy.status.updated_replicas or 0
                available = deploy.status.available_replicas or 0
                age = self._calculate_age(deploy.metadata.creation_timestamp)
                
                print(f"{ns:<20} {name:<25} {ready:<10} {up_to_date:<10} {available:<10} {age}")
            
            return deployments.items
            
        except ApiException as e:
            logger.error(f"Error listing deployments: {e}")
            return []
    
    def list_pods(self, namespace=None):
        """List pods in specified namespace or all namespaces."""
        try:
            if namespace:
                logger.info(f"Fetching pods in namespace: {namespace}")
                pods = self.v1.list_namespaced_pod(namespace=namespace)
            else:
                logger.info("Fetching pods from all namespaces...")
                pods = self.v1.list_pod_for_all_namespaces()
            
            print("\n" + "="*90)
            print("PODS")
            print("="*90)
            print(f"{'NAMESPACE':<20} {'NAME':<35} {'READY':<8} {'STATUS':<15} {'RESTARTS':<10} {'AGE'}")
            print("-" * 90)
            
            for pod in pods.items:
                ns = pod.metadata.namespace
                name = pod.metadata.name
                
                # Calculate ready containers
                ready_containers = 0
                total_containers = len(pod.status.container_statuses) if pod.status.container_statuses else 0
                if pod.status.container_statuses:
                    ready_containers = sum(1 for cs in pod.status.container_statuses if cs.ready)
                ready_str = f"{ready_containers}/{total_containers}"
                
                status = pod.status.phase
                
                # Calculate total restarts
                restarts = 0
                if pod.status.container_statuses:
                    restarts = sum(cs.restart_count for cs in pod.status.container_statuses)
                
                age = self._calculate_age(pod.metadata.creation_timestamp)
                
                print(f"{ns:<20} {name:<35} {ready_str:<8} {status:<15} {restarts:<10} {age}")
            
            return pods.items
            
        except ApiException as e:
            logger.error(f"Error listing pods: {e}")
            return []
    
    def _calculate_age(self, creation_timestamp):
        """Calculate age of resource from creation timestamp."""
        if not creation_timestamp:
            return "Unknown"
        
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        age_delta = now - creation_timestamp
        
        days = age_delta.days
        hours, remainder = divmod(age_delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d"
        elif hours > 0:
            return f"{hours}h"
        else:
            return f"{minutes}m"
    
    def get_cluster_info(self):
        """Get basic cluster information."""
        try:
            # Get cluster version
            version_info = self.v1.get_code()
            logger.info(f"Connected to Kubernetes cluster version: {version_info.git_version}")
            
            # Get node information
            nodes = self.v1.list_node()
            logger.info(f"Cluster has {len(nodes.items)} node(s)")
            
        except ApiException as e:
            logger.error(f"Error getting cluster info: {e}")

def main():
    """Main function to demonstrate usage."""
    lister = KubernetesResourceLister()
    
    # Get cluster information
    lister.get_cluster_info()
    
    # List all resources
    namespaces = lister.list_namespaces()
    lister.list_deployments()
    lister.list_pods()
    
    # Example: List resources in specific namespace
    if 'default' in namespaces:
        print("\n" + "="*60)
        print("RESOURCES IN 'default' NAMESPACE ONLY")
        print("="*60)
        lister.list_deployments(namespace='default')
        lister.list_pods(namespace='default')

if __name__ == "__main__":
    main()