# EKS Scheduler Code Analysis Report

## Overview
This report analyzes potential errors and issues in the EKS scheduler codebase, focusing on hardcoded values, assumptions, and error handling patterns that could cause failures.

## Critical Issues Found

### 1. webhook_manager.py

#### Hardcoded Service Names (Lines 228, 258)
- **Line 228**: `kubectl get endpoints kyverno-svc-metrics -n kyverno`
  - Assumes Kyverno service is named exactly "kyverno-svc-metrics"
  - Assumes Kyverno is installed in "kyverno" namespace
  - **Impact**: Will fail if Kyverno is installed with different service names or in different namespace

- **Line 258**: `kubectl get endpoints aws-load-balancer-webhook-service -n kube-system`
  - Assumes AWS LB Controller webhook service is named exactly "aws-load-balancer-webhook-service"
  - **Impact**: Will fail if service has different name (common variations: "aws-load-balancer-webhook", "aws-lb-webhook-service")

#### Hardcoded Deployment Mappings (Lines 75-87)
- Hardcoded mapping of webhook names to deployment names:
  - `aws-load-balancer` → `aws-load-balancer-controller`
  - `kyverno` → `kyverno-admission-controller`
  - `cert-manager` → `cert-manager`
  - `istio` → `istiod`
- **Impact**: Will fail to identify correct deployments if they use non-standard names

#### Missing Error Handling
- **Line 278**: Falls back to checking deployment if webhook service not found, but only for AWS LB Controller
- Other webhook types don't have this fallback mechanism

### 2. pod_manager.py

#### Hardcoded Node Label Selector (Line 61)
- `eks.amazonaws.com/nodegroup={node_group_name}`
- **Impact**: Assumes EKS standard labeling; won't work with custom-labeled nodes or non-EKS Kubernetes clusters

#### Hardcoded kubectl Timeout (Line 35)
- Fixed 120-second timeout for kubectl commands
- Should use configurable timeout from config_manager

#### DaemonSet Detection Limitation (Line 110)
- Only checks `ownerReferences` for DaemonSet kind
- **Impact**: May miss pods managed by higher-level controllers (e.g., Helm releases that create DaemonSets)

### 3. bootstrap_validator.py

#### Hardcoded System Pod Requirements (Lines 19-42)
- Assumes specific deployment names:
  - `coredns` (not `kube-dns` or custom DNS)
  - `aws-load-balancer-controller` (exact name)
  - `cluster-autoscaler` (exact name)
  - `ebs-csi-controller` (not `aws-ebs-csi-driver`)
  - `metrics-server` (exact name)
  - `cloudwatch-agent` (exact name)
  - `external-dns` (exact name)
  - Kyverno controllers with specific names
- **Impact**: Will report failures if deployments use different names

#### Hardcoded Namespaces (Lines 20-41)
- Assumes specific namespaces:
  - `kube-system` for core components
  - `amazon-cloudwatch` for CloudWatch
  - `external-dns` for external DNS
  - `kyverno` for Kyverno
  - `snapshot-controller` for snapshot controller
- **Impact**: Will fail to find deployments in non-standard namespaces

#### DNS Test Command Issue (Lines 224-226)
- Uses `kubectl run` with `-it` flag which requires TTY
- **Impact**: Will fail in non-interactive environments (CI/CD pipelines)

### 4. dependency_manager.py

#### Hardcoded Service Names and Namespaces (Lines 19-89)
Similar issues as bootstrap_validator.py with hardcoded assumptions:
- Specific deployment names for all services
- Specific namespace assignments
- **Impact**: Won't work with customized deployments

#### Namespace Creation Not Handled (Lines 179-181, 221-223)
- Logs "not found" as info and returns True (considers missing as "ready")
- **Impact**: May incorrectly report success when namespaces don't exist

### 5. config/config.ini

#### Webhook Names Configuration (Line 28)
- Lists specific webhook names that may not match actual deployments
- No validation that these webhooks actually exist
- **Impact**: Silent failures when webhook names don't match

#### Fixed Deployment Names (Line 21)
- `cluster-autoscaler` as the only option
- **Impact**: Won't work with alternative autoscaler deployments

## Recommendations

### 1. Make Service/Deployment Names Configurable
- Add configuration sections for each component's expected names
- Allow namespace overrides for all components
- Example:
  ```ini
  [kyverno]
  namespace = kyverno
  webhook_service = kyverno-svc-metrics
  admission_controller = kyverno-admission-controller
  
  [aws_lb_controller]
  namespace = kube-system
  webhook_service = aws-load-balancer-webhook-service
  deployment = aws-load-balancer-controller
  ```

### 2. Implement Service Discovery
- Instead of hardcoded names, use label selectors:
  ```python
  # Find Kyverno webhook service by label
  kubectl get endpoints -l app.kubernetes.io/name=kyverno -n kyverno
  ```

### 3. Add Existence Checks Before Operations
- Verify namespaces exist before checking deployments
- Verify webhook configurations exist before trying to modify them
- Add dry-run validation for all kubectl commands

### 4. Improve Error Messages
- When a hardcoded resource isn't found, suggest what might be wrong:
  ```python
  self.logger.error(f"Kyverno webhook service 'kyverno-svc-metrics' not found in namespace 'kyverno'. "
                    f"Please verify Kyverno is installed and check the actual service name with: "
                    f"kubectl get svc -n kyverno")
  ```

### 5. Add Flexibility for Non-EKS Environments
- Make node label selectors configurable
- Add support for generic Kubernetes clusters
- Allow custom node selector labels

### 6. Fix Interactive Command Issues
- Remove `-it` flags from automated kubectl commands
- Use `--rm --restart=Never` without `-it` for pod runs

### 7. Implement Timeout Configuration
- Use configured timeouts consistently across all modules
- Add per-operation timeout overrides where needed

### 8. Add Webhook Auto-Discovery
- Implement logic to discover webhooks by labels or annotations
- Support regex patterns for webhook matching
- Example:
  ```python
  # Find all webhooks with certain labels
  kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations \
    -l managed-by=eks-scheduler -o json
  ```

## Summary

The main issues stem from hardcoded assumptions about:
1. Service and deployment names
2. Namespace locations
3. Label structures
4. Component existence

These assumptions make the scheduler brittle and environment-specific. The code would benefit from:
- More configuration options
- Service discovery mechanisms
- Better error handling and messaging
- Validation before operations
- Support for non-standard deployments

The code is well-structured but needs flexibility improvements to work reliably across different EKS configurations and deployment patterns.