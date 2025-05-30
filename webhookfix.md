## **Prevention Strategy: Add Webhook Cleanup to Your Scaling Code**

### **Option 1: Add to Scale-Up Process (Recommended)**

Add this method to your `EKSOperations` class:

```python
def cleanup_kyverno_webhooks_if_stuck(self, cluster_name):
    """Clean up Kyverno webhooks if they're causing bootstrap deadlock."""
    try:
        if self.dry_run:
            self.logger.info("[DRY RUN] Would check and clean stuck Kyverno webhooks")
            return {'status': 'dry_run'}
        
        # Check if Kyverno pods are actually running
        cmd = ['kubectl', 'get', 'pods', '-n', 'kyverno', '--no-headers']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        running_pods = 0
        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            running_pods = len([line for line in lines if 'Running' in line])
        
        # Check if webhook configurations exist
        cmd = ['kubectl', 'get', 'validatingwebhookconfigurations', '--no-headers']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        kyverno_webhooks = []
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            kyverno_webhooks = [line.split()[0] for line in lines if 'kyverno' in line.lower()]
        
        # If webhooks exist but no running pods, clean up webhooks
        if kyverno_webhooks and running_pods == 0:
            self.logger.warning(f"Found {len(kyverno_webhooks)} Kyverno webhooks but {running_pods} running pods")
            self.logger.warning("Cleaning webhooks to prevent bootstrap deadlock")
            
            # Delete validating webhooks
            for webhook in kyverno_webhooks:
                subprocess.run(['kubectl', 'delete', 'validatingwebhookconfigurations', webhook, '--ignore-not-found=true'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            # Delete mutating webhooks
            cmd = ['kubectl', 'get', 'mutatingwebhookconfigurations', '--no-headers']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                mutating_webhooks = [line.split()[0] for line in lines if 'kyverno' in line.lower()]
                
                for webhook in mutating_webhooks:
                    subprocess.run(['kubectl', 'delete', 'mutatingwebhookconfigurations', webhook, '--ignore-not-found=true'],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            
            self.logger.info("Webhook cleanup completed")
            return {'status': 'cleaned', 'webhooks_removed': len(kyverno_webhooks)}
        
        elif kyverno_webhooks and running_pods > 0:
            self.logger.info(f"Kyverno webhooks exist and {running_pods} pods are running - no cleanup needed")
            return {'status': 'healthy'}
        
        else:
            self.logger.info("No Kyverno webhook cleanup needed")
            return {'status': 'no_action_needed'}
            
    except Exception as e:
        self.logger.error(f"Error checking/cleaning Kyverno webhooks: {str(e)}")
        return {'status': 'error', 'error': str(e)}
```

### **Option 2: Update Scale-Up Method**

Add the webhook cleanup to your `scale_up_cluster` method:

```python
def scale_up_cluster(self, cluster_name, min_nodes):
    """Scale up managed node groups with webhook cleanup."""
    results = []
    autoscaler_result = None
    
    try:
        # Step 1: Configure kubectl for cluster access
        if not self.configure_kubectl(cluster_name):
            raise EKSOperationError("Failed to configure kubectl for cluster access")
        
        # Step 2: Clean up stuck webhooks BEFORE scaling
        self.logger.info("Checking for stuck Kyverno webhooks...")
        webhook_cleanup_result = self.cleanup_kyverno_webhooks_if_stuck(cluster_name)
        
        if webhook_cleanup_result['status'] == 'cleaned':
            self.logger.info("Removed stuck webhooks to prevent bootstrap deadlock")
        
        # Step 3: Continue with existing scaling logic...
        # ... rest of your existing scale_up_cluster code ...
```

### **Option 3: Add to Scale-Down Process (Extra Safety)**

```python
def scale_down_cluster(self, cluster_name):
    """Scale down with webhook cleanup preparation."""
    # ... existing scale-down code ...
    
    # After successful scale-down, prepare for future scale-up
    try:
        if not self.dry_run:
            self.logger.info("Storing webhook cleanup flag for next scale-up")
            self.state_manager.store_webhook_cleanup_needed(cluster_name, True)
    except Exception as e:
        self.logger.warning(f"Could not store webhook cleanup flag: {e}")
    
    return results
```

### **Option 4: Scheduled Cleanup Job (Production)**

Create a separate cleanup script that runs periodically:

```python
#!/usr/bin/env python3
"""
Kyverno Webhook Cleanup Job
Run this as a cron job or scheduled task to prevent webhook deadlocks
"""

def cleanup_all_clusters():
    """Check all EKS clusters for webhook deadlocks."""
    eks_client = boto3.client('eks')
    
    try:
        clusters = eks_client.list_clusters()['clusters']
        
        for cluster_name in clusters:
            eks_ops = EKSOperations(region='us-west-2')  # Your region
            result = eks_ops.cleanup_kyverno_webhooks_if_stuck(cluster_name)
            
            if result['status'] == 'cleaned':
                print(f"Cleaned webhooks for cluster {cluster_name}")
                
    except Exception as e:
        print(f"Error in cleanup job: {e}")

if __name__ == "__main__":
    cleanup_all_clusters()
```

## **GitLab CI Integration**

Add webhook cleanup as a separate job:

```yaml
stages:
  - scale-down
  - scale-up
  - webhook-cleanup

scale_up:
  stage: scale-up
  script:
    - python scale.py --action=up --cluster=$CLUSTER_NAME --min-nodes=$MIN_NODES
  timeout: 25m

webhook_cleanup:
  stage: webhook-cleanup
  script:
    - python webhook_cleanup.py --cluster=$CLUSTER_NAME
  when: on_failure  # Run if scale-up fails
  allow_failure: true
```

## **Quick Prevention Check**

Add this one-liner to your scale-up script:

```bash
# Before running Python scale-up
kubectl get validatingwebhookconfigurations | grep kyverno | wc -l && kubectl get pods -n kyverno --no-headers | grep Running | wc -l || echo "Potential webhook deadlock - run cleanup"
```

## **Recommended Approach**

**For your immediate needs:**
- Add **Option 1** + **Option 2** to your existing code
- This automatically prevents the deadlock during every scale-up

**For production environments:**
- Add **Option 4** as a scheduled cleanup job
- Run it every hour or before/after scaling operations

**The key insight:** Webhook configurations survive in etcd even when pods are gone. Always check for this mismatch before scaling up nodes.​​​​​​​​​​​​​​​​