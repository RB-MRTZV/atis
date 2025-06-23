#!/usr/bin/env python3
"""
Configuration validation script for EKS Scheduler.
Checks for common configuration issues and validates cluster setup.
"""

import subprocess
import json
import sys
import os
import configparser
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config_manager import ConfigManager

class ConfigValidator:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.config_manager = ConfigManager()
        
    def run_kubectl_command(self, command):
        """Execute kubectl command and return result."""
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=30
            )
            return result.returncode == 0, result.stdout, result.stderr
        except Exception as e:
            return False, "", str(e)
    
    def check_kubectl_access(self):
        """Check if kubectl is configured and can access cluster."""
        print("🔍 Checking kubectl access...")
        success, stdout, stderr = self.run_kubectl_command(['kubectl', 'cluster-info'])
        
        if not success:
            self.issues.append("❌ kubectl cannot access cluster. Run: aws eks update-kubeconfig --name <cluster-name>")
            return False
        
        print("✅ kubectl access verified")
        return True
    
    def check_autoscaler_deployment(self):
        """Check if configured autoscaler deployment exists."""
        print("\n🔍 Checking cluster autoscaler...")
        
        deployment_name = self.config_manager.get_autoscaler_deployment_name()
        if not deployment_name:
            print("⚠️  No autoscaler configured (this is OK if not using autoscaler)")
            return True
        
        # Search for autoscaler in common namespaces
        namespaces = ['kube-system', 'cluster-autoscaler']
        found = False
        
        for ns in namespaces:
            success, stdout, _ = self.run_kubectl_command([
                'kubectl', 'get', 'deployment', deployment_name, '-n', ns, '-o', 'name'
            ])
            if success:
                print(f"✅ Found autoscaler '{deployment_name}' in namespace '{ns}'")
                found = True
                break
        
        if not found:
            self.warnings.append(f"⚠️  Autoscaler deployment '{deployment_name}' not found. Update config or use: kubectl get deployments -A | grep autoscaler")
        
        return True
    
    def check_webhooks(self):
        """Check if configured webhooks exist."""
        print("\n🔍 Checking webhooks...")
        
        webhook_configs = self.config_manager.get_webhook_names()
        if not webhook_configs:
            print("⚠️  No webhooks configured (this is OK if not using admission webhooks)")
            return True
        
        # Get all webhooks
        success, stdout, _ = self.run_kubectl_command([
            'kubectl', 'get', 'validatingwebhookconfigurations,mutatingwebhookconfigurations', '-o', 'json'
        ])
        
        if not success:
            self.warnings.append("⚠️  Cannot list webhooks. Check RBAC permissions.")
            return True
        
        try:
            data = json.loads(stdout)
            existing_webhooks = set()
            
            for item in data.get('items', []):
                existing_webhooks.add(item['metadata']['name'])
            
            # Check each configured webhook
            for webhook_name, namespace in webhook_configs:
                if webhook_name not in existing_webhooks:
                    # Check if it's a partial match
                    partial_matches = [w for w in existing_webhooks if webhook_name in w or w in webhook_name]
                    if partial_matches:
                        self.warnings.append(f"⚠️  Webhook '{webhook_name}' not found exactly, but found similar: {partial_matches}")
                    else:
                        self.warnings.append(f"⚠️  Webhook '{webhook_name}' not found. Use: kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations")
                else:
                    print(f"✅ Found webhook '{webhook_name}'")
        
        except json.JSONDecodeError:
            self.warnings.append("⚠️  Failed to parse webhook data")
        
        return True
    
    def check_node_groups(self):
        """Check if EKS node groups exist and use expected labels."""
        print("\n🔍 Checking node groups...")
        
        node_label = self.config_manager.get('services', 'node_group_label', 'eks.amazonaws.com/nodegroup')
        
        # Check if any nodes have the expected label
        success, stdout, _ = self.run_kubectl_command([
            'kubectl', 'get', 'nodes', '-l', node_label, '-o', 'name'
        ])
        
        if success and stdout.strip():
            node_count = len(stdout.strip().split('\n'))
            print(f"✅ Found {node_count} nodes with label '{node_label}'")
        else:
            self.warnings.append(f"⚠️  No nodes found with label '{node_label}'. Check if using self-managed nodes.")
        
        return True
    
    def check_excluded_clusters(self):
        """Display excluded clusters."""
        print("\n🔍 Checking cluster exclusions...")
        
        excluded = self.config_manager.get_excluded_clusters()
        if excluded:
            print(f"ℹ️  Excluded clusters: {', '.join(excluded)}")
        else:
            print("✅ No clusters excluded")
        
        return True
    
    def check_timeouts(self):
        """Check if timeout values are reasonable."""
        print("\n🔍 Checking timeout configurations...")
        
        timeouts = {
            'webhook_timeout': (30, 300, "webhook validation"),
            'drain_timeout': (60, 1800, "node drain"),
            'pod_grace_period': (10, 300, "pod termination"),
            'bootstrap_validation_timeout': (300, 3600, "bootstrap validation"),
            'dependency_startup_timeout': (60, 1800, "service startup"),
            'kubectl_timeout': (30, 300, "kubectl commands"),
            'aws_cli_timeout': (30, 300, "AWS CLI commands")
        }
        
        for timeout_name, (min_val, max_val, description) in timeouts.items():
            value = self.config_manager.get_timeout(timeout_name, 60)
            if value < min_val:
                self.warnings.append(f"⚠️  {timeout_name} ({value}s) seems too low for {description}. Consider >= {min_val}s")
            elif value > max_val:
                self.warnings.append(f"⚠️  {timeout_name} ({value}s) seems too high for {description}. Consider <= {max_val}s")
            else:
                print(f"✅ {timeout_name}: {value}s")
        
        return True
    
    def check_critical_deployments(self):
        """Check if critical system deployments exist."""
        print("\n🔍 Checking critical system deployments...")
        
        critical_deployments = [
            ('coredns', 'kube-system'),
            ('metrics-server', 'kube-system'),
            ('aws-load-balancer-controller', 'kube-system'),
        ]
        
        for deployment, namespace in critical_deployments:
            success, _, _ = self.run_kubectl_command([
                'kubectl', 'get', 'deployment', deployment, '-n', namespace, '-o', 'name'
            ])
            
            if success:
                print(f"✅ Found {deployment} in {namespace}")
            else:
                self.warnings.append(f"⚠️  Critical deployment '{deployment}' not found in {namespace}")
        
        return True
    
    def validate(self):
        """Run all validation checks."""
        print("EKS Scheduler Configuration Validator")
        print("=" * 50)
        
        # Check kubectl access first
        if not self.check_kubectl_access():
            print("\n❌ Cannot proceed without kubectl access")
            return False
        
        # Run other checks
        self.check_autoscaler_deployment()
        self.check_webhooks()
        self.check_node_groups()
        self.check_excluded_clusters()
        self.check_timeouts()
        self.check_critical_deployments()
        
        # Summary
        print("\n" + "=" * 50)
        print("Validation Summary")
        print("=" * 50)
        
        if self.issues:
            print("\n❌ Critical Issues:")
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print("\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"  {warning}")
        
        if not self.issues and not self.warnings:
            print("\n✅ All checks passed!")
        
        return len(self.issues) == 0

def main():
    """Main entry point."""
    validator = ConfigValidator()
    
    try:
        success = validator.validate()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Validation error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()