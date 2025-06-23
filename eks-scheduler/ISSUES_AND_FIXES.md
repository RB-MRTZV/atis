# EKS Scheduler - Issues Found and Fixes Applied

## Summary

This document outlines the critical issues found in the EKS scheduler and the fixes that have been applied.

## Critical Issues Found

### 1. Hardcoded Service Names

**Problem**: Multiple files contained hardcoded Kubernetes service and deployment names that may not match actual deployments.

**Files Affected**:
- `webhook_manager.py`: Hardcoded `kyverno-svc-metrics` and `aws-load-balancer-webhook-service`
- `bootstrap_validator.py`: Hardcoded system pod deployment names
- `dependency_manager.py`: Hardcoded service names and namespaces

**Impact**: The scheduler would fail with cryptic errors when services don't exist with expected names.

### 2. Non-Configurable Node Labels

**Problem**: `pod_manager.py` hardcoded the EKS node label `eks.amazonaws.com/nodegroup`.

**Impact**: Won't work with self-managed node groups or non-EKS Kubernetes clusters.

### 3. Interactive kubectl Commands

**Problem**: `bootstrap_validator.py` used `-it` flags in kubectl commands.

**Impact**: Commands fail in non-interactive environments like CI/CD pipelines.

### 4. Fixed Timeout Values

**Problem**: `pod_manager.py` used a fixed 120-second timeout instead of configurable values.

**Impact**: Large clusters or slow networks could experience timeout failures.

### 5. Poor Error Handling

**Problem**: Services assumed to exist without checking, leading to unclear error messages.

**Impact**: Difficult to diagnose configuration issues.

## Fixes Applied

### 1. Enhanced Configuration Support

**Created `config.ini.example`** with:
- Comprehensive documentation for each setting
- New `[services]` section for overriding service names
- Better default values and examples

### 2. Service Discovery Improvements

**Updated `webhook_manager.py`**:
- Added service existence checks before querying endpoints
- Fallback to alternative service names
- Configurable service names via config
- Better error messages when services not found

### 3. Configurable Components

**Updated `pod_manager.py`**:
- Made kubectl timeout configurable
- Made node label configurable for non-EKS environments

**Updated `bootstrap_validator.py`**:
- Removed interactive flags from kubectl commands
- Made timeouts configurable

### 4. Created Validation Script

**New `scripts/validate_config.py`**:
- Checks kubectl access
- Validates autoscaler deployment exists
- Verifies webhook configurations
- Checks timeout values are reasonable
- Identifies missing critical deployments

### 5. Comprehensive Documentation

**Created `README.md`** with:
- Detailed troubleshooting guide
- Common issues and solutions
- Configuration examples
- Architecture overview
- RBAC requirements

## Remaining Considerations

### 1. Service Discovery
While we've made service names configurable, a future improvement would be to implement dynamic service discovery using label selectors.

### 2. Multi-Cluster Support
The current implementation processes one cluster at a time. Consider using external orchestration for multiple clusters.

### 3. Monitoring Integration
Consider adding Prometheus metrics or CloudWatch integration for better observability.

## How to Validate Your Configuration

1. Run the validation script:
```bash
cd eks-scheduler
python scripts/validate_config.py
```

2. Test with dry-run:
```bash
python src/main.py --action stop --cluster your-cluster --dry-run
```

3. Check logs for warnings about missing services or configurations.

## Configuration Checklist

Before running the scheduler:

- [ ] Verify kubectl access: `kubectl get nodes`
- [ ] Find autoscaler name: `kubectl get deployments -A | grep autoscaler`
- [ ] List webhooks: `kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations`
- [ ] Update `config.ini` with correct service names
- [ ] Test with `--dry-run` first
- [ ] Review timeout values for your cluster size

## Emergency Recovery

If scaling operations fail:

1. **Nodes stuck in cordoned state**:
   ```bash
   kubectl uncordon <node-name>
   ```

2. **Autoscaler disabled**:
   ```bash
   kubectl scale deployment cluster-autoscaler -n kube-system --replicas=1
   ```

3. **Webhooks in wrong state**:
   ```bash
   kubectl patch validatingwebhookconfiguration <webhook-name> --type='json' -p='[{"op": "replace", "path": "/webhooks/0/failurePolicy", "value": "Fail"}]'
   ```