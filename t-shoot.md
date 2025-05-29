## **Step-by-Step Troubleshooting for Kyverno and CloudWatch Deployments**

### **Step 1: Check Pod Status and Events**
```bash
# Check pod status in both namespaces
kubectl get pods -n kyverno
kubectl get pods -n amazon-cloudwatch

# Check for pending/failed pods and their events
kubectl describe pods -n kyverno
kubectl describe pods -n amazon-cloudwatch

# Look for specific error patterns
kubectl get events --sort-by='.lastTimestamp' -n kyverno
kubectl get events --sort-by='.lastTimestamp' -n amazon-cloudwatch
```

### **Step 2: Check Deployment Status**
```bash
# Check if deployments exist and their replica status
kubectl get deployments -n kyverno
kubectl get deployments -n amazon-cloudwatch

# Check deployment details for errors
kubectl describe deployment kyverno -n kyverno
kubectl describe deployment cloudwatch-agent -n amazon-cloudwatch

# Check ReplicaSets
kubectl get rs -n kyverno
kubectl get rs -n amazon-cloudwatch
```

### **Step 3: Check Node Resources and Scheduling**
```bash
# Check if nodes are ready and have resources
kubectl get nodes -o wide
kubectl describe nodes

# Check node resource utilization
kubectl top nodes

# Check if pods are stuck in Pending due to resource constraints
kubectl get pods -n kyverno -o wide
kubectl get pods -n amazon-cloudwatch -o wide
```

### **Step 4: Check Node Taints and Tolerations**
```bash
# Check if new nodes have taints that prevent scheduling
kubectl describe nodes | grep -A 5 "Taints:"

# Check if Kyverno/CloudWatch pods have proper tolerations
kubectl get deployment kyverno -n kyverno -o yaml | grep -A 10 "tolerations:"
kubectl get deployment cloudwatch-agent -n amazon-cloudwatch -o yaml | grep -A 10 "tolerations:"
```

### **Step 5: Check Node Selectors and Affinity**
```bash
# Check if deployments have node selectors that don't match new nodes
kubectl get deployment kyverno -n kyverno -o yaml | grep -A 5 "nodeSelector:"
kubectl get deployment cloudwatch-agent -n amazon-cloudwatch -o yaml | grep -A 5 "nodeSelector:"

# Check node labels
kubectl get nodes --show-labels
```

### **Step 6: Check Image Pull Issues**
```bash
# Check if pods are failing to pull images
kubectl describe pods -n kyverno | grep -A 5 "Failed"
kubectl describe pods -n amazon-cloudwatch | grep -A 5 "Failed"

# Check image pull secrets
kubectl get secrets -n kyverno
kubectl get secrets -n amazon-cloudwatch
```

### **Step 7: Check Dependencies (ConfigMaps, Secrets, RBAC)**
```bash
# Check if required ConfigMaps exist
kubectl get configmaps -n kyverno
kubectl get configmaps -n amazon-cloudwatch

# Check if required Secrets exist  
kubectl get secrets -n kyverno
kubectl get secrets -n amazon-cloudwatch

# Check ServiceAccounts and RBAC
kubectl get serviceaccount -n kyverno
kubectl get serviceaccount -n amazon-cloudwatch
kubectl auth can-i --as=system:serviceaccount:kyverno:kyverno create policies
```

## **Common Fixes Based on Root Cause**

### **Fix 1: Resource Constraints**
```bash
# If nodes don't have enough resources, check requests/limits
kubectl get deployment kyverno -n kyverno -o yaml | grep -A 10 "resources:"

# Reduce resource requests temporarily or add more nodes
kubectl patch deployment kyverno -n kyverno -p='{"spec":{"template":{"spec":{"containers":[{"name":"kyverno","resources":{"requests":{"memory":"128Mi","cpu":"100m"}}}]}}}}'
```

### **Fix 2: Node Taint Issues**
```bash
# If nodes have taints, add tolerations to deployments
kubectl patch deployment kyverno -n kyverno -p='{"spec":{"template":{"spec":{"tolerations":[{"key":"node.kubernetes.io/not-ready","operator":"Exists","effect":"NoExecute"},{"key":"node.kubernetes.io/unreachable","operator":"Exists","effect":"NoExecute"}]}}}}'
```

### **Fix 3: Node Selector Issues**
```bash
# Remove restrictive node selectors if they don't match new nodes
kubectl patch deployment kyverno -n kyverno -p='{"spec":{"template":{"spec":{"nodeSelector":null}}}}'
kubectl patch deployment cloudwatch-agent -n amazon-cloudwatch -p='{"spec":{"template":{"spec":{"nodeSelector":null}}}}'
```

### **Fix 4: Force Pod Recreation**
```bash
# Delete pods to force recreation on new nodes
kubectl delete pods -n kyverno --all
kubectl delete pods -n amazon-cloudwatch --all

# Or restart deployments
kubectl rollout restart deployment/kyverno -n kyverno
kubectl rollout restart deployment/cloudwatch-agent -n amazon-cloudwatch
```

### **Fix 5: Priority Class Issues**
```bash
# Check if pods are waiting due to priority issues
kubectl get priorityclasses

# Check if deployments have priority classes that prevent scheduling
kubectl get deployment kyverno -n kyverno -o yaml | grep priorityClassName
```

## **Quick Diagnostic Script**

```bash
#!/bin/bash
NAMESPACES=("kyverno" "amazon-cloudwatch")

echo "=== EKS System Deployment Troubleshooting ==="
echo "Cluster: $(kubectl config current-context)"
echo "Time: $(date)"
echo

for ns in "${NAMESPACES[@]}"; do
    echo "=== Namespace: $ns ==="
    
    echo "Deployments:"
    kubectl get deployments -n $ns
    echo
    
    echo "Pods:"
    kubectl get pods -n $ns -o wide
    echo
    
    echo "Recent Events:"
    kubectl get events --sort-by='.lastTimestamp' -n $ns | tail -5
    echo
    
    echo "Failed Pods Details:"
    kubectl get pods -n $ns --field-selector=status.phase!=Running -o name | while read pod; do
        echo "--- $pod ---"
        kubectl describe $pod -n $ns | grep -A 10 "Events:"
    done
    echo
done

echo "=== Node Status ==="
kubectl get nodes -o wide
echo

echo "=== Node Resources ==="
kubectl describe nodes | grep -A 5 "Allocated resources:"
```

## **Monitoring Recovery**

```bash
# Watch pods come online
watch kubectl get pods -n kyverno,amazon-cloudwatch

# Check logs once pods start
kubectl logs deployment/kyverno -n kyverno
kubectl logs deployment/cloudwatch-agent -n amazon-cloudwatch

# Verify functionality
kubectl get clusterpolicy  # Kyverno policies should be visible
kubectl get nodes | head -1; kubectl get nodes | grep -v NAME | wc -l  # Node count
```

**Most Likely Causes in Order:**
1. **Node taints** from new instances
2. **Resource constraints** - new nodes not enough capacity
3. **Node selectors** - hardcoded to old node labels
4. **Deployment stuck** - needs manual restart

Start with **Steps 1-4** as they cover 90% of the issues. The fix is usually forcing pod recreation or adjusting node selectors/tolerations.
