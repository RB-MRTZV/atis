# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive multi-service AWS resource scheduler for cost optimization. It supports EC2 instances, EKS clusters, RDS instances, and Aurora PostgreSQL clusters with sophisticated state management, phased execution, and comprehensive dry-run capabilities.

## Architecture

The project is organized into three main schedulers with standardized architecture:

- **ec2-scheduler/**: EC2 instances and Auto Scaling Groups (ASG)
- **eks-scheduler/**: EKS cluster node group management with autoscaler conflict resolution
- **rds-scheduler/**: RDS instances and Aurora PostgreSQL clusters

Each scheduler follows identical patterns:
- `src/main.py` - Main orchestrator with argument parsing
- `src/*_operations.py` - Core AWS operations
- `src/config_manager.py` - Configuration management
- `src/reporting.py` - Report generation (CSV/JSON/table)
- `src/sns_notifier.py` - SNS notifications
- `config/config.ini` - Service configuration
- `config/accounts.json` - Account definitions

## Common Development Commands

### Testing
```bash
# Run unit tests for specific scheduler
cd ec2-scheduler/tests && python -m pytest
cd eks-scheduler/tests && python -m pytest
cd rds-scheduler/tests && python -m pytest

# Dry-run testing (always run before real operations)
python ec2-scheduler/src/main.py --action stop --target both --dry-run
python eks-scheduler/src/main.py --action stop --cluster production-cluster --dry-run --region ap-southeast-2
python rds-scheduler/src/main.py --action stop --target both --dry-run --region ap-southeast-2

# Test EKS enhanced features
python eks-scheduler/src/main.py --action stop --cluster production-cluster --dry-run  # Tests pod eviction
python eks-scheduler/src/main.py --action start --cluster production-cluster --min-nodes 2 --dry-run  # Tests bootstrap validation
```

### Running Individual Services
```bash
# EC2 scheduler
cd ec2-scheduler/src
python main.py --action stop --target both --verify

# EKS scheduler  
cd eks-scheduler/src
python main.py --action stop --cluster production-cluster --region ap-southeast-2

# RDS scheduler
cd rds-scheduler/src
python main.py --action stop --target both --verify --region ap-southeast-2
```

### Dependencies
```bash
# Install required packages
pip install boto3 tabulate pytest awscli
```

## Key Technical Details

### EKS Scheduler State Management
- Uses JSON files in `eks-scheduler/state/` for persistence
- GitLab CI artifacts preserve state between scale-down/scale-up jobs
- Critical files: `{cluster_name}_nodegroups.json`, `{cluster_name}_autoscaler.json`

### EKS Enhanced Features (Production-Grade)
The EKS scheduler includes sophisticated safety and management features:

#### Autoscaler Conflict Resolution
- Automatically detects and disables cluster autoscaler during scaling
- Prevents autoscaler from fighting manual scaling operations
- Restores autoscaler state after scaling up

#### Pod Lifecycle Management (NEW)
- Graceful pod eviction with PodDisruptionBudget compliance
- Node cordoning before scaling down
- Configurable grace periods and force termination
- Zero-downtime scaling operations

#### Bootstrap Validation (NEW)
- Prevents deadlock scenarios when scaling from zero nodes
- Validates minimum nodes for system pods (CoreDNS, kube-proxy)
- Ensures successful cluster recovery

#### Webhook Management (NEW)
- Detects and validates admission controllers
- Supports Kyverno, OPA Gatekeeper, Istio, Cert-Manager
- Prevents deployment failures during scale-up

#### Dependency Orchestration (NEW)
- Validates service startup order
- Ensures databases start before applications
- Handles service mesh dependencies
- Prevents cascading failures

### Configuration Files
- `config/config.ini` - AWS region, SNS topics, tag filters, timeouts
- `config/accounts.json` - Multi-account support
- Each scheduler has separate configuration but follows same structure

### GitLab CI Pipeline
- Uses phased execution: validate → compute-stop → compute-start → database-stop → database-start → report
- Compute tier (EC2/ASG/EKS) runs before database tier (RDS/Aurora)
- Extensive artifact preservation for EKS state files

### Dry-Run Capabilities
All schedulers support comprehensive dry-run mode:
- No AWS API calls made during dry-run
- Mock data simulation with realistic scenarios
- Clear `[DRY RUN]` indicators in logs
- Full report generation

### Error Handling Patterns
All schedulers use consistent error handling:
- Custom exception classes (*OperationError, ConfigurationError, etc.)
- SNS notifications for failures
- Comprehensive logging with timestamps
- Graceful degradation

## Development Patterns

### Adding New Features
1. Follow existing code patterns in similar scheduler
2. Maintain consistency across all three schedulers
3. Add dry-run support for any AWS operations
4. Include comprehensive error handling
5. Add unit tests following existing test structure
6. Update configuration files as needed

### EKS-Specific Patterns
1. **Component Separation**: Keep pod, webhook, bootstrap, and dependency logic in separate modules
2. **Dry-Run First**: All new features must support dry-run mode with mock data
3. **Safety Checks**: Add validation before any destructive operations
4. **State Preservation**: Store critical state before modifications
5. **Graceful Failures**: Handle errors without leaving cluster in broken state

### Configuration Management
- Use ConfigManager class for consistent config handling
- Support environment variable overrides
- Validate configurations at startup
- Use standard INI format with sections

### AWS Operations
- Always implement dry-run mode
- Use boto3 clients consistently
- Handle pagination for list operations
- Include retry logic for transient failures
- Log all AWS API calls

### State Management (EKS specific)
- Store original configurations before scaling down
- Use timestamped JSON files
- Implement cleanup after successful operations
- Handle missing state files gracefully

## Branch and Environment Information

- **Main branch**: `main`
- **Production branch**: `v1.1` (used for scheduled operations)
- **Test branches**: `v1.1.1` (used for flexible operations)
- **Default region**: `ap-southeast-2`
- **EKS cluster**: `production-cluster`

## Important Notes

- Always test with dry-run first
- EKS operations require kubectl and AWS CLI configured
- RDS scheduler supports both Aurora clusters and standalone instances via `--target` parameter
- All schedulers support multi-account operations
- GitLab CI pipeline includes AWS credentials (hardcoded for this environment)
- State files are critical for EKS operations - ensure artifacts are preserved

## Common Issues

- **EKS kubectl configuration**: Requires AWS CLI and proper IAM permissions
- **EKS state file missing**: Check GitLab CI artifacts from scale-down job
- **EKS pod eviction failures**: Check PodDisruptionBudgets and increase grace period
- **EKS bootstrap deadlock**: Ensure min-nodes parameter is sufficient for system pods
- **EKS webhook timeouts**: Some webhooks may take time to become ready after scale-up
- **RDS verification timeout**: Aurora clusters can take longer to start/stop
- **SNS permissions**: Ensure IAM policy includes sns:Publish for notification topics