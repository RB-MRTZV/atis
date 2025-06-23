# EKS Scheduler

A sophisticated EKS cluster scheduler for cost optimization through automated scaling of node groups, with production-grade safety features including pod lifecycle management, webhook validation, and dependency orchestration.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)
- [Known Issues and Limitations](#known-issues-and-limitations)

## Overview

The EKS Scheduler provides automated scaling operations for Amazon EKS clusters, allowing you to scale down clusters during off-hours and scale them back up when needed. It includes sophisticated safety mechanisms to ensure zero-downtime operations.

## Features

- **Automated Node Group Scaling**: Scale EKS managed node groups to zero or specified minimum nodes
- **State Management**: Preserves original node group configurations for accurate restoration
- **Pod Lifecycle Management**: 
  - Graceful pod eviction with PodDisruptionBudget compliance
  - Node cordoning before scaling down
  - Configurable grace periods
- **Webhook Management**:
  - Automatic detection and management of admission webhooks
  - Prevents deployment failures during scale-up
  - Configurable webhook handling
- **Bootstrap Validation**:
  - Ensures critical system pods are ready before proceeding
  - Prevents deadlock scenarios when scaling from zero
- **Dependency Orchestration**:
  - Manages service startup order
  - Validates dependencies between services
- **Cluster Autoscaler Integration**: 
  - Automatically disables/enables cluster autoscaler during operations
  - Prevents conflicts with manual scaling
- **Comprehensive Reporting**: CSV, JSON, and table format reports
- **Dry-Run Mode**: Test operations without making changes
- **Multi-Region Support**: Process clusters across AWS regions

## Prerequisites

### Required Software

- Python 3.8+
- kubectl configured with appropriate cluster access
- AWS CLI v2 configured with credentials
- boto3 Python library

### Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "eks:DescribeCluster",
        "eks:ListClusters",
        "eks:DescribeNodegroup",
        "eks:ListNodegroups",
        "eks:UpdateNodegroupConfig",
        "eks:UpdateNodegroupVersion",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:UpdateAutoScalingGroup",
        "ec2:DescribeInstances",
        "iam:GetRole",
        "iam:PassRole",
        "sns:Publish"
      ],
      "Resource": "*"
    }
  ]
}
```

### Kubernetes RBAC Permissions

The user/role running the scheduler needs the following Kubernetes permissions:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: eks-scheduler
rules:
- apiGroups: [""]
  resources: ["nodes", "pods", "namespaces"]
  verbs: ["get", "list", "patch"]
- apiGroups: ["apps"]
  resources: ["deployments", "daemonsets", "replicasets"]
  verbs: ["get", "list", "patch"]
- apiGroups: [""]
  resources: ["pods/eviction"]
  verbs: ["create"]
- apiGroups: ["policy"]
  resources: ["poddisruptionbudgets"]
  verbs: ["get", "list"]
- apiGroups: ["admissionregistration.k8s.io"]
  resources: ["validatingwebhookconfigurations", "mutatingwebhookconfigurations"]
  verbs: ["get", "list", "patch"]
- apiGroups: [""]
  resources: ["endpoints", "services"]
  verbs: ["get", "list"]
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourepo/atis.git
cd atis/eks-scheduler
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure AWS credentials:
```bash
aws configure
```

4. Verify kubectl access:
```bash
kubectl get nodes
```

## Configuration

### Main Configuration File: `config/config.ini`

```ini
[aws]
region = ap-southeast-2

[sns]
topic_arn = arn:aws:sns:region:account:topic-name

[logging]
level = INFO
file = 

[exclusions]
# Comma-separated list of cluster names to exclude from scaling
excluded_clusters = production-critical,payment-processing

[autoscaler]
# Name of the cluster autoscaler deployment
# Find it: kubectl get deployments -n kube-system | grep autoscaler
deployment_name = cluster-autoscaler

[webhooks]
# Webhook names to manage during scaling
# Format: webhook-name:namespace (namespace optional)
webhook_names = aws-load-balancer-webhook:kube-system,kyverno-policy-webhook

[timeouts]
# All values in seconds
webhook_timeout = 60
drain_timeout = 300
pod_grace_period = 30
bootstrap_validation_timeout = 600
dependency_startup_timeout = 300
kubectl_timeout = 120
aws_cli_timeout = 60
webhook_validation_timeout = 300
```

### Important Configuration Considerations

1. **Autoscaler Deployment Name**: 
   - Must match your actual deployment name
   - Common variations: `cluster-autoscaler`, `cluster-autoscaler-aws`, `aws-cluster-autoscaler`

2. **Webhook Names**:
   - Must match actual webhook configuration names
   - Use `kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations` to find

3. **Timeout Values**:
   - Adjust based on your cluster size and workload characteristics
   - Larger clusters may need longer timeouts

## Usage

### Basic Commands

```bash
# Scale down a cluster (managed node groups to 0)
python src/main.py --action stop --cluster my-cluster --region ap-southeast-2

# Scale up a cluster (restore original sizes or minimum nodes)
python src/main.py --action start --cluster my-cluster --min-nodes 2 --region ap-southeast-2

# Dry run mode (no actual changes)
python src/main.py --action stop --cluster my-cluster --dry-run

# Notification only (send SNS without action)
python src/main.py --action stop --cluster my-cluster --notify-only
```

### Command Line Options

- `--action`: Required. Either `start` (scale up) or `stop` (scale down)
- `--cluster`: Required. Name of the EKS cluster to process
- `--region`: AWS region (defaults to config value)
- `--min-nodes`: Minimum nodes when scaling up (default: 1)
- `--dry-run`: Simulate actions without executing
- `--notify-only`: Send notifications without performing actions

### Example Workflows

#### Daily Cost Optimization
```bash
# Scale down at 7 PM
0 19 * * * cd /path/to/eks-scheduler && python src/main.py --action stop --cluster prod-cluster

# Scale up at 7 AM
0 7 * * * cd /path/to/eks-scheduler && python src/main.py --action start --cluster prod-cluster --min-nodes 3
```

#### Maintenance Window
```bash
# Before maintenance
python src/main.py --action stop --cluster staging-cluster

# After maintenance
python src/main.py --action start --cluster staging-cluster
```

## Architecture

### Component Overview

1. **main.py**: Entry point and orchestration
2. **eks_operations.py**: Core EKS operations and workflow management
3. **config_manager.py**: Configuration handling
4. **pod_manager.py**: Pod eviction and node management
5. **webhook_manager.py**: Admission webhook handling
6. **bootstrap_validator.py**: System pod validation
7. **dependency_manager.py**: Service dependency management
8. **state_manager.py**: Cluster state persistence
9. **reporting.py**: Report generation
10. **sns_notifier.py**: SNS notifications

### Scaling Workflow

#### Scale Down Process:
1. Configure kubectl for cluster access
2. Disable cluster autoscaler (if present)
3. Store current node group configurations
4. Cordon and drain nodes (with pod eviction)
5. Scale node groups to 0
6. Generate reports and send notifications

#### Scale Up Process:
1. Configure kubectl for cluster access
2. Restore node group configurations (or use minimum)
3. Wait for nodes to be ready
4. Validate critical system pods
5. Re-enable admission webhooks
6. Validate service dependencies
7. Re-enable cluster autoscaler
8. Generate reports and send notifications

## Troubleshooting

### Common Issues

#### 1. Webhook Validation Failures
**Problem**: Webhooks not ready after scale-up
```
Error: Webhook aws-load-balancer-webhook is not healthy
```

**Solutions**:
- Increase `webhook_validation_timeout` in config
- Check if webhook service names match configuration
- Verify webhook pods are scheduled on available nodes

#### 2. Bootstrap Validation Timeout
**Problem**: System pods not ready in time
```
Error: Timeout waiting for system pods to be ready
```

**Solutions**:
- Increase `bootstrap_validation_timeout`
- Ensure `--min-nodes` is sufficient for system pods
- Check for resource constraints on nodes

#### 3. Kubectl Command Failures
**Problem**: kubectl commands timing out or failing
```
Error: kubectl command timed out after 120 seconds
```

**Solutions**:
- Verify kubectl is properly configured: `aws eks update-kubeconfig`
- Check IAM permissions for EKS access
- Increase `kubectl_timeout` for large clusters

#### 4. Cluster Autoscaler Not Found
**Problem**: Cannot find cluster autoscaler deployment
```
Warning: Cluster autoscaler not found
```

**Solutions**:
- Update `deployment_name` in config to match actual name
- Use `kubectl get deployments -n kube-system | grep autoscaler`
- If not using autoscaler, this warning can be ignored

#### 5. Node Group Scaling Failures
**Problem**: Node group won't scale
```
Error: Failed to update node group configuration
```

**Solutions**:
- Check IAM permissions for UpdateNodegroupConfig
- Verify node group is in ACTIVE state
- Check AWS service limits for EC2 instances

### Debugging Commands

```bash
# Check cluster state
kubectl get nodes
kubectl get pods --all-namespaces

# Find deployment names
kubectl get deployments --all-namespaces | grep -E "(autoscaler|webhook|kyverno)"

# Check webhook configurations
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# View scheduler logs
python src/main.py --action stop --cluster my-cluster --dry-run 2>&1 | tee debug.log
```

## Known Issues and Limitations

### Current Limitations

1. **Hardcoded Service Names**: 
   - Some Kubernetes service names are hardcoded
   - May fail with non-standard deployments
   - Workaround: Modify config to match your deployment names

2. **EKS-Specific Node Labels**:
   - Relies on `eks.amazonaws.com/nodegroup` label
   - Won't work with self-managed node groups
   - Workaround: Use managed node groups only

3. **Single Cluster Operations**:
   - Processes one cluster at a time
   - No built-in parallelization
   - Workaround: Use external orchestration for multiple clusters

4. **Limited Service Discovery**:
   - Cannot auto-discover all webhook services
   - Requires manual configuration
   - Improvement planned for future versions

5. **Interactive Command Issues**:
   - Some kubectl commands use `-it` flags
   - Fails in non-interactive environments (CI/CD)
   - Fix planned in next release

### Planned Improvements

1. **Dynamic Service Discovery**: 
   - Auto-detect webhook services and deployments
   - Label-based service discovery

2. **Multi-Cluster Support**:
   - Process multiple clusters in parallel
   - Cluster group configurations

3. **Custom Node Selectors**:
   - Support for custom node labels
   - Self-managed node group support

4. **Enhanced Monitoring**:
   - Prometheus metrics export
   - CloudWatch metrics integration

5. **Webhook Service Mapping**:
   - Configurable webhook-to-service mappings
   - Auto-detection of webhook endpoints

## Contributing

Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see [LICENSE](../LICENSE) for details.