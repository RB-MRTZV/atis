# EKS Cluster Autoscaler Management

## Overview

This document explains how the EKS scheduler handles **cluster autoscaler conflicts** - a critical issue that would otherwise prevent any actual cost savings during node scaling operations.

## ⚠️ The Problem

### Cluster Autoscaler Conflicts
Without proper autoscaler management, the following scenario occurs:

1. **Manual Scale Down**: EKS scheduler scales node groups to `min=0, desired=0`
2. **Autoscaler Interference**: Cluster autoscaler detects "insufficient nodes" for pending pods
3. **Automatic Scale Up**: Autoscaler immediately scales nodes back up to maintain minimum counts
4. **Result**: **NO COST SAVINGS** - nodes never actually terminate

## ✅ The Solution

### Comprehensive Autoscaler Management
The EKS scheduler now includes **complete cluster lifecycle management** with enhanced safety features:

```
SCALE DOWN WORKFLOW:
1. Configure kubectl for cluster access
2. 🔒 DISABLE cluster autoscaler (scale to 0 replicas)
3. Store autoscaler configuration for restoration
4. 🆕 GRACEFUL POD EVICTION with PDB compliance
5. Scale node groups to 0 (min=0, desired=0, max>=1)
6. Nodes terminate successfully ✅

SCALE UP WORKFLOW:  
1. Configure kubectl for cluster access
2. 🆕 BOOTSTRAP VALIDATION (prevent deadlocks)
3. Scale node groups to desired configuration
4. 🆕 WEBHOOK READINESS check (Kyverno, OPA, Istio)
5. 🆕 DEPENDENCY VALIDATION (service startup order)
6. 🔓 RESTORE cluster autoscaler (original replicas)
7. Normal autoscaling resumes ✅
```

## 🔧 Implementation Details

### Enhanced Components
The scheduler now includes multiple safety and management components:

#### 1. Autoscaler Detection
```python
# Searches for autoscaler in these locations:
search_targets = [
    ('kube-system', 'cluster-autoscaler'),
    ('kube-system', 'cluster-autoscaler-aws-cluster-autoscaler'),
    ('cluster-autoscaler', 'cluster-autoscaler'),
    ('kube-system', 'aws-cluster-autoscaler')
]
```

#### 2. Pod Management (NEW)
```python
# pod_manager.py - Graceful eviction
- Lists nodes in each node group
- Cordons nodes to prevent new scheduling
- Respects PodDisruptionBudgets
- Evicts pods with configurable grace periods
- Force-terminates stuck pods after timeout
```

#### 3. Bootstrap Validation (NEW)
```python
# bootstrap_validator.py - Deadlock prevention
- Validates minimum nodes for system pods
- Checks CoreDNS, kube-proxy requirements
- Ensures adequate resources for critical pods
- Prevents unrecoverable cluster states
```

#### 4. Webhook Management (NEW)
```python
# webhook_manager.py - Admission controller handling
- Detects all webhook types (Kyverno, OPA, Istio, etc.)
- Validates webhook endpoints are ready
- Handles webhook failures gracefully
- Provides detailed readiness reports
```

#### 5. Dependency Management (NEW)
```python
# dependency_manager.py - Service orchestration
- Builds service dependency graphs
- Validates startup order (DB -> Cache -> App)
- Ensures dependencies are met before proceeding
- Handles circular dependencies
```

### State Management
Autoscaler state is preserved using local JSON files:

```json
{
  "namespace": "kube-system",
  "deployment_name": "cluster-autoscaler", 
  "original_replicas": 1,
  "stored_at": "2025-05-29T14:00:49.499Z"
}
```

### kubectl Integration
The scheduler executes kubectl commands via subprocess:

- **Cluster Configuration**: `aws eks update-kubeconfig --region <region> --name <cluster>`
- **Disable Autoscaler**: `kubectl scale deployment cluster-autoscaler -n kube-system --replicas=0`
- **Restore Autoscaler**: `kubectl scale deployment cluster-autoscaler -n kube-system --replicas=1`
- **Node Operations**: `kubectl cordon/uncordon <node>` (NEW)
- **Pod Eviction**: `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data` (NEW)
- **Webhook Checks**: `kubectl get validatingwebhookconfigurations` (NEW)
- **Service Readiness**: `kubectl get pods -A --field-selector status.phase!=Running` (NEW)

## 🚀 Usage Examples

### Manual Execution

```bash
# Scale down with autoscaler management
python3 main.py --action stop --cluster production-cluster --dry-run

# Scale up with autoscaler restoration  
python3 main.py --action start --cluster production-cluster --min-nodes 2 --dry-run
```

### GitLab CI Integration

```yaml
eks-stop:
  stage: compute-stop
  script:
    - cd eks-scheduler/src
    - python3 main.py --action stop --cluster $EKS_CLUSTER_NAME
  variables:
    EKS_CLUSTER_NAME: "production-cluster"
  artifacts:
    paths: ["eks-scheduler/state/"]
    expire_in: 1 week

eks-start:
  stage: compute-start  
  script:
    - cd eks-scheduler/src
    - python3 main.py --action start --cluster $EKS_CLUSTER_NAME --min-nodes $MIN_NODES
  variables:
    EKS_CLUSTER_NAME: "production-cluster"
    MIN_NODES: "2"
  dependencies: ["eks-stop"]
```

## 📊 Logging and Monitoring

### Detailed Operation Logs

```
Scale Down:
2025-05-29 14:00:49 - INFO - Disabling cluster autoscaler to prevent scaling conflicts...
2025-05-29 14:00:49 - INFO - Found cluster autoscaler: cluster-autoscaler in kube-system (replicas: 1, ready: 1)
2025-05-29 14:00:49 - INFO - Successfully disabled cluster autoscaler
2025-05-29 14:00:49 - INFO - Scaling down 2 node groups in cluster test-cluster

Scale Up:
2025-05-29 14:00:55 - INFO - Scaling up 2 node groups in cluster test-cluster  
2025-05-29 14:00:55 - INFO - Restoring cluster autoscaler...
2025-05-29 14:00:55 - INFO - Successfully restored cluster autoscaler to 1 replicas
```

### Operation Results
Each node group operation includes autoscaler management status:

```json
{
  "NodeGroupName": "worker-nodes-1",
  "Status": "Success", 
  "AutoscalerManaged": "success",
  "PreviousState": "min=2, max=10, desired=3",
  "CurrentState": "scaled_down"
}
```

## 🛡️ Error Handling

### Autoscaler Management Failures
- **Not Found**: Continues with node scaling, logs warning
- **Disable Failed**: Continues with node scaling, logs warning about potential conflicts  
- **Restore Failed**: Logs error, preserves state file for manual intervention

### kubectl Failures
- **Configuration Failed**: Aborts operation with clear error message
- **Command Timeout**: 60-second timeout with proper error reporting
- **Permission Issues**: Clear error messages for IAM/RBAC problems

## 🔒 Security Requirements

### IAM Permissions
The scheduler requires standard EKS permissions plus kubectl access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListNodegroups", 
        "eks:DescribeNodegroup",
        "eks:UpdateNodegroupConfig"
      ],
      "Resource": "*"
    }
  ]
}
```

### Kubernetes RBAC
The kubectl commands require appropriate cluster permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: eks-scheduler
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "patch", "update"]
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  verbs: ["get", "patch", "update"]
```

## 🧪 Dry Run Testing

### Safe Testing
All autoscaler management operations support dry-run mode:

```bash
# Test complete workflow without changes
python3 main.py --action stop --cluster test-cluster --dry-run
python3 main.py --action start --cluster test-cluster --min-nodes 2 --dry-run
```

### Mock Operations
In dry-run mode, the scheduler simulates:
- Autoscaler detection and state storage
- kubectl command execution
- State file management
- Complete workflow validation

## 📈 Benefits

### Cost Optimization
✅ **Actual node termination** - no more autoscaler conflicts  
✅ **Guaranteed cost savings** during off-hours  
✅ **Seamless restoration** for business hours

### Operational Excellence  
✅ **Zero manual intervention** required  
✅ **GitLab CI integration** with state persistence  
✅ **Comprehensive logging** and error handling  
✅ **Production-ready** with dry-run testing

## 🔄 State Persistence

### GitLab CI Artifacts
State files are preserved between pipeline stages:

```yaml
artifacts:
  paths: 
    - "eks-scheduler/state/"
  expire_in: 1 week
```

### File Structure
```
state/
├── production-cluster_nodegroups.json    # Node group configurations
├── production-cluster_autoscaler.json    # Autoscaler configuration  
└── staging-cluster_nodegroups.json       # Multiple clusters supported
```

## 🚨 Troubleshooting

### Common Issues

**kubectl not found:**
```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
```

**kubeconfig access denied:**
```bash
# Verify EKS access
aws eks describe-cluster --region us-west-2 --name your-cluster
aws eks update-kubeconfig --region us-west-2 --name your-cluster
```

**Autoscaler not found:**
- Check deployment name: `kubectl get deployments -A | grep -i autoscaler`
- Verify namespace: `kubectl get deployments -n kube-system`
- Review search targets in code if using custom deployment names

**State file persistence:**
- Verify GitLab CI artifacts are configured
- Check state directory permissions
- Review artifact download in dependent jobs

## 📚 Related Documentation

- [EKS Operations Guide](eks-operations.md)
- [State Management](state-management.md) 
- [GitLab CI Integration](gitlab-ci-integration.md)
- [AWS Permissions](aws-permissions.md) 