## **Root Cause: Kyverno Bootstrap Deadlock**

This is the **exact webhook bootstrap problem** we discussed earlier! Here's what's happening:

1. **Kyverno pods** need to start
2. **Webhook configurations** still exist and are trying to validate pod creation
3. **Kyverno service** has no endpoints (because pods aren't running)
4. **Webhook validation fails** → Pod creation blocked → Kyverno can't start

**Classic bootstrap deadlock scenario.**

## **Immediate Fix - Remove Webhook Configurations Temporarily**

### **Step 1: Remove Validating Webhooks**
```bash
# List current webhooks
kubectl get validatingwebhookconfigurations | grep kyverno

# Remove Kyverno validating webhooks
kubectl delete validatingwebhookconfigurations -l webhook=kyverno

# Or remove by name if label doesn't work
kubectl get validatingwebhookconfigurations | grep kyverno | awk '{print $1}' | xargs kubectl delete validatingwebhookconfigurations
```

### **Step 2: Remove Mutating Webhooks**
```bash
# List and remove mutating webhooks
kubectl get mutatingwebhookconfigurations | grep kyverno
kubectl delete mutatingwebhookconfigurations -l webhook=kyverno

# Or by name
kubectl get mutatingwebhookconfigurations | grep kyverno | awk '{print $1}' | xargs kubectl delete mutatingwebhookconfigurations
```

### **Step 3: Force Kyverno Pod Recreation**
```bash
# Delete stuck replicasets and pods
kubectl delete rs -n kyverno --all
kubectl delete pods -n kyverno --all

# Restart the deployment
kubectl rollout restart deployment/kyverno -n kyverno
```

### **Step 4: Watch Recovery**
```bash
# Monitor pods starting
watch kubectl get pods -n kyverno

# Check events
kubectl get events -n kyverno --sort-by='.lastTimestamp'
```

### **Step 5: Verify Webhook Recreation**
```bash
# After Kyverno pods are running, check if webhooks are recreated
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl get mutatingwebhookconfigurations | grep kyverno

# Check policies are working
kubectl get clusterpolicy
```

## **Why This Happened**

Even though your webhooks have `ownerReferences`, they **weren't deleted** when nodes scaled to 0. The webhook configurations survive in etcd (cluster data store) and remain active even when the backing service is unavailable.

## **Prevention for Future Scaling**

Add webhook cleanup to your scaling code:

```python
def cleanup_stuck_webhooks(self, cluster_name):
    """Clean up webhook configurations that might cause bootstrap issues."""
    try:
        if self.dry_run:
            self.logger.info("[DRY RUN] Would check and clean stuck webhooks")
            return
            
        # Check if Kyverno service has endpoints
        result = subprocess.run(
            ['kubectl', 'get', 'endpoints', 'kyverno-svc', '-n', 'kyverno', '-o', 'json'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if result.returncode == 0:
            endpoint_data = json.loads(result.stdout)
            if not endpoint_data.get('subsets'):  # No endpoints
                self.logger.warning("Kyverno service has no endpoints, cleaning webhooks")
                
                # Remove problematic webhooks
                subprocess.run(['kubectl', 'delete', 'validatingwebhookconfigurations', '-l', 'webhook=kyverno', '--ignore-not-found=true'])
                subprocess.run(['kubectl', 'delete', 'mutatingwebhookconfigurations', '-l', 'webhook=kyverno', '--ignore-not-found=true'])
                
    except Exception as e:
        self.logger.warning(f"Error cleaning webhooks: {e}")
```

## **Add to Scale-Up Process**

```python
def scale_up_cluster(self, cluster_name, min_nodes):
    # ... existing code ...
    
    # After configuring kubectl, before scaling nodes
    self.cleanup_stuck_webhooks(cluster_name)
    
    # ... rest of scaling code ...
```

## **One-Liner Emergency Fix**

```bash
# Emergency webhook cleanup
kubectl delete validatingwebhookconfigurations,mutatingwebhookconfigurations -l webhook=kyverno; kubectl delete pods -n kyverno --all
```

After running the webhook cleanup, Kyverno should start normally and recreate its webhooks automatically. This is the **bootstrap deadlock** we identified as a critical risk earlier - now you've experienced it firsthand!​​​​​​​​​​​​​​​​