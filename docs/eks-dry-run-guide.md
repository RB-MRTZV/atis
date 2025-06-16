# EKS Dry-Run Guide

## Overview

The EKS scheduler includes comprehensive dry-run functionality to ensure you can safely test operations without making any actual changes to your AWS infrastructure.

## How Dry-Run Works

### What Gets Prevented

When `--dry-run` is enabled, **NO** actual AWS API calls are made:

1. **No EKS API Calls**: No actual node group scaling operations
2. **No State File Changes**: No state files are written or modified
3. **No AWS Resource Modifications**: Zero impact on your infrastructure
4. **No kubectl Commands**: No pod evictions or node operations
5. **No Webhook Interactions**: No admission controller calls

### What Still Happens

During dry-run mode, the scheduler will:

1. **Log All Actions**: Shows exactly what would be done
2. **Generate Reports**: Creates reports with `[DRY RUN]` indicators
3. **Validate Configurations**: Checks cluster names and parameters
4. **Simulate State Management**: Shows what state would be stored/retrieved
5. **Simulate Pod Eviction**: Shows which pods would be drained
6. **Simulate Bootstrap Checks**: Validates minimum node requirements
7. **Simulate Webhook Validation**: Shows webhook readiness checks
8. **Simulate Dependency Checks**: Shows service startup validation

## Using Dry-Run

### Command Line Usage

```bash
# Test scaling down a cluster
python eks-scheduler/src/main.py --action stop --cluster production-cluster --dry-run

# Test scaling up with specific min nodes
python eks-scheduler/src/main.py --action start --cluster production-cluster --min-nodes 2 --dry-run

# Test with specific region
python eks-scheduler/src/main.py --action stop --cluster dev-cluster --region us-west-2 --dry-run
```

### GitLab CI Usage

```bash
# Use the dry-run-all job to test all services
# This includes EKS dry-run testing

# Or use flexible-eks job with ACTION variable
# Set ACTION=stop or ACTION=start when triggering
```

## Dry-Run Output Examples

### Scale Down Dry-Run (Enhanced)

```
2024-01-15 10:30:00 - eks_operations - INFO - EKS Operations initialized in DRY RUN mode - no actual changes will be made
2024-01-15 10:30:00 - eks_operations - INFO - [DRY RUN] Would configure kubectl for cluster production-cluster
2024-01-15 10:30:00 - eks_operations - INFO - [DRY RUN] Would disable cluster autoscaler
2024-01-15 10:30:00 - pod_manager - INFO - [DRY RUN] Would list nodes in node group mock-nodegroup-1
2024-01-15 10:30:00 - pod_manager - INFO - [DRY RUN] Would cordon 3 nodes to prevent new pod scheduling
2024-01-15 10:30:00 - pod_manager - INFO - [DRY RUN] Would check PodDisruptionBudgets before eviction
2024-01-15 10:30:00 - pod_manager - INFO - [DRY RUN] Would evict 45 pods with grace period 30s
2024-01-15 10:30:00 - pod_manager - INFO - [DRY RUN] Would wait for pod termination
2024-01-15 10:30:00 - eks_operations - INFO - [DRY RUN] Would scale node group mock-nodegroup-1 to min=0, max=1, desired=0
2024-01-15 10:30:00 - state_manager - INFO - [DRY RUN] Would store original configuration: min=2, max=10, desired=3
```

### Scale Up Dry-Run (Enhanced)

```
2024-01-15 10:35:00 - eks_operations - INFO - [DRY RUN] Would scale up cluster production-cluster
2024-01-15 10:35:00 - bootstrap_validator - INFO - [DRY RUN] Would validate bootstrap requirements for 2 nodes
2024-01-15 10:35:00 - bootstrap_validator - INFO - [DRY RUN] Would check system pod requirements: CoreDNS, kube-proxy
2024-01-15 10:35:00 - bootstrap_validator - INFO - [DRY RUN] Bootstrap validation: PASS - 2 nodes sufficient
2024-01-15 10:35:00 - state_manager - INFO - [DRY RUN] Would retrieve stored configs: min=2, max=10, desired=3
2024-01-15 10:35:00 - eks_operations - INFO - [DRY RUN] Would scale node group to min=2, max=10, desired=3
2024-01-15 10:35:00 - webhook_manager - INFO - [DRY RUN] Would check admission webhooks readiness
2024-01-15 10:35:00 - webhook_manager - INFO - [DRY RUN] Would validate: kyverno, cert-manager, istio webhooks
2024-01-15 10:35:00 - dependency_manager - INFO - [DRY RUN] Would validate service dependencies
2024-01-15 10:35:00 - dependency_manager - INFO - [DRY RUN] Would check: database -> cache -> application order
2024-01-15 10:35:00 - eks_operations - INFO - [DRY RUN] Would restore cluster autoscaler
```

## Report Output

### CSV Report (Dry-Run)
```csv
Account,Region,Cluster,PreviousState,NewState,Action,Timestamp,Status,Error
default,ap-southeast-2,production-cluster,"min=2, max=10, desired=3",dry_run_scaled_down,stop,2024-01-15T10:30:00,DryRun,
```

### JSON Report (Dry-Run)
```json
{
  "results": [
    {
      "account": "default",
      "region": "ap-southeast-2", 
      "cluster_name": "production-cluster",
      "previous_state": "min=2, max=10, desired=3",
      "new_state": "dry_run_scaled_down",
      "action": "stop",
      "timestamp": "2024-01-15T10:30:00",
      "status": "DryRun",
      "error": ""
    }
  ]
}
```

## Safety Features

### Mock Data

During dry-run, the system uses realistic mock data:

- **Node Groups**: `['mock-nodegroup-1', 'mock-nodegroup-2']`
- **Scaling Config**: `{minSize: 2, maxSize: 10, desiredSize: 3}`
- **State Storage**: Mock configurations that simulate real scenarios

### Clear Indicators

All dry-run operations are clearly marked:

- **Log Messages**: Prefixed with `[DRY RUN]`
- **Report Status**: Shows `DryRun` instead of `Success`
- **State Indicators**: `dry_run_scaled_down` / `dry_run_scaled_up`

### No Side Effects

Guaranteed no impact on:

- ✅ EKS clusters remain unchanged
- ✅ Node groups keep current scaling
- ✅ State files are not modified
- ✅ No AWS charges incurred
- ✅ No autoscaler disruption
- ✅ No pod evictions or disruptions
- ✅ No webhook interactions
- ✅ No bootstrap operations

## Best Practices

### 1. Always Test First

```bash
# Before any real operation, run dry-run
python eks-scheduler/src/main.py --action stop --cluster production-cluster --dry-run

# Review the output carefully
# Check that the cluster name is correct
# Verify the scaling configurations look right
# Ensure min-nodes parameter is what you expect
```

### 2. Validate Parameters

```bash
# Test different scenarios
python eks-scheduler/src/main.py --action start --cluster production-cluster --min-nodes 1 --dry-run
python eks-scheduler/src/main.py --action start --cluster production-cluster --min-nodes 3 --dry-run

# Compare the outputs to understand the impact
```

### 3. Check Reports

```bash
# After dry-run, check the generated reports
ls reports/
cat reports/eks_operations_*.csv
cat reports/eks_operations_*.json
```

### 4. GitLab CI Testing

```bash
# Use the dry-run-all job before scheduling
# This tests all services including EKS
# Review job artifacts and logs
```

## Troubleshooting Dry-Run

### Common Issues

#### 1. Cluster Not Found (Even in Dry-Run)
```
Error: Cluster 'wrong-name' not found
```
**Solution**: Even in dry-run, cluster names are validated. Use correct cluster name.

#### 2. No Mock Data Shown
```
No node groups found for cluster
```
**Solution**: Check that dry-run mode is properly enabled. Look for initialization message.

#### 3. Real API Calls During Dry-Run
```
Actual AWS API calls being made
```
**Solution**: Ensure `--dry-run` flag is passed and EKS Operations shows dry-run initialization.

### Verification Checklist

Before running real operations, verify dry-run shows:

- ✅ `[DRY RUN]` prefixes in all log messages
- ✅ `DryRun` status in reports
- ✅ Mock node group names (`mock-nodegroup-*`)
- ✅ No actual AWS API calls in logs
- ✅ State manager shows dry-run mode

## Integration with GitLab CI

### Dry-Run Jobs

The GitLab CI includes these dry-run capabilities:

```yaml
# Individual dry-run testing
dry-run-all:
  script:
    - python eks-scheduler/src/main.py --action $ACTION --cluster $EKS_CLUSTER_NAME --dry-run

# Flexible dry-run with custom parameters  
flexible-eks:
  # When ACTION is set, includes dry-run testing
```

### Scheduled Dry-Run

Consider adding scheduled dry-run jobs to regularly validate configurations:

```yaml
# Weekly dry-run validation
weekly-dry-run:
  schedule: "0 9 * * 1"  # Monday 9 AM
  script:
    - python eks-scheduler/src/main.py --action stop --cluster $EKS_CLUSTER_NAME --dry-run
    - python eks-scheduler/src/main.py --action start --cluster $EKS_CLUSTER_NAME --min-nodes $MIN_NODES --dry-run
```

## Summary

The enhanced EKS dry-run functionality provides:

1. **Complete Safety**: Zero AWS infrastructure impact
2. **Full Simulation**: Shows exactly what would happen
3. **Comprehensive Logging**: Detailed operation preview
4. **Report Generation**: Documented simulation results
5. **State Management Testing**: Validates configuration storage/retrieval
6. **Pod Eviction Preview**: Shows which pods would be drained
7. **Bootstrap Validation**: Confirms safe recovery from zero nodes
8. **Webhook Testing**: Validates admission controller readiness
9. **Dependency Checking**: Ensures correct service startup order

Always use dry-run before implementing new EKS scheduling operations or when testing configuration changes. The enhanced dry-run mode now covers all critical safety features including pod management, bootstrap validation, and service dependencies. 