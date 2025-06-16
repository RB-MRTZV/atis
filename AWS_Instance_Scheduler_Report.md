# AWS Instance Scheduler - Comprehensive Project Report

## Executive Summary

The AWS Instance Scheduler is a sophisticated, production-ready multi-service resource scheduler designed for cost optimization and automated AWS resource management. This comprehensive system manages EC2 instances, EKS clusters, RDS instances, and Aurora PostgreSQL clusters with advanced features including state management, phased execution, and comprehensive dry-run capabilities.

**Key Statistics:**
- **Total Python Files**: 22
- **Total Lines of Code**: 5,662+
- **Schedulers**: 3 (EC2, EKS, RDS)
- **Supported Services**: 6 (EC2, ASG, EKS, RDS, Aurora PostgreSQL, SNS)
- **Documentation Files**: 7 comprehensive guides

## 1. Project Overview and Purpose

### Primary Objectives
- **Cost Optimization**: Automated shutdown/startup of AWS resources during off-hours
- **Resource Management**: Centralized control of compute and database resources
- **Risk Mitigation**: Comprehensive dry-run testing and state management
- **Operational Efficiency**: GitLab CI/CD integration with phased execution
- **Multi-Service Support**: Unified interface for diverse AWS services

### Target Use Cases
- Development/staging environment cost reduction
- Weekend/holiday resource shutdown
- Maintenance window automation
- Compliance with resource governance policies
- Emergency resource management

## 2. Architecture and Components

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWS Instance Scheduler                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ EC2 Scheduler│  │ EKS Scheduler│  │ RDS Scheduler│          │
│  │              │  │              │  │              │          │
│  │ • EC2        │  │ • Node Groups│  │ • RDS        │          │
│  │ • ASG        │  │ • Autoscaler │  │ • Aurora     │          │
│  │ • State Mgmt │  │ • kubectl    │  │ • PostgreSQL │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    Shared Components                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Config Mgmt  │  │ Reporting    │  │ SNS Notifier │          │
│  │ • INI Files  │  │ • CSV/JSON   │  │ • Success    │          │
│  │ • Accounts   │  │ • HTML/Table │  │ • Failure    │          │
│  │ • Tags       │  │ • Artifacts  │  │ • Alerts     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Standardized Scheduler Architecture

Each scheduler follows identical patterns:
- `src/main.py` - Main orchestrator with argument parsing
- `src/*_operations.py` - Core AWS operations with dry-run support
- `src/config_manager.py` - Configuration management
- `src/reporting.py` - Report generation (CSV/JSON/HTML/table)
- `src/sns_notifier.py` - SNS notifications
- `config/config.ini` - Service configuration
- `config/accounts.json` - Account definitions
- `tests/` - Unit test coverage

### Service-Specific Components

#### EC2 Scheduler (`ec2-scheduler/`)
- **EC2 Operations**: Instance start/stop with state verification
- **ASG Operations**: Auto Scaling Group management with process suspension
- **Force Stop**: Emergency shutdown capabilities
- **Multi-Account**: Cross-account resource management
- **Test Coverage**: Comprehensive unit tests

#### EKS Scheduler (`eks-scheduler/`) - **ENHANCED**
- **Node Group Scaling**: Managed node group scaling with AWS constraint compliance
- **Autoscaler Management**: Sophisticated conflict resolution with cluster autoscaler
- **State Management**: JSON-based state persistence with GitLab CI artifacts
- **kubectl Integration**: Seamless EKS cluster access via AWS CLI
- **Dry-Run Excellence**: No AWS API calls during testing
- **Pod Lifecycle Management**: Graceful pod eviction with PDB compliance
- **Bootstrap Validation**: Prevents deadlock scenarios during scale-up
- **Webhook Intelligence**: Handles admission controllers and webhooks
- **Dependency Orchestration**: Ensures correct service startup order

#### RDS Scheduler (`rds-scheduler/`)
- **Aurora PostgreSQL**: Full cluster lifecycle management
- **Standalone RDS**: Instance management independent of clusters
- **Target Selection**: Flexible targeting (clusters/instances/both)
- **Verification**: Configurable timeouts for state verification
- **Engine filtering**: Aurora PostgreSQL focus with extensibility

## 3. Key Features and Capabilities

### 3.1 Advanced Dry-Run System
- **Zero Impact Testing**: No AWS API calls during dry-run
- **Realistic Simulation**: Mock data with representative scenarios
- **Clear Indicators**: `[DRY RUN]` prefixes throughout logs
- **Full Reporting**: Complete report generation in dry-run mode

### 3.2 EKS Autoscaler Conflict Resolution
- **Automatic Detection**: Scans multiple namespaces for autoscaler deployments
- **Safe Disable/Restore**: Preserves original replica counts
- **State Persistence**: JSON files with timestamped configurations
- **Guaranteed Savings**: Prevents autoscaler from fighting scaling operations

### 3.3 Comprehensive State Management
- **EKS State Files**: Node group and autoscaler configurations
- **GitLab CI Artifacts**: 7-day persistence between jobs
- **Recovery Mechanisms**: Graceful handling of missing state files
- **Intelligent Restoration**: Respects min-nodes parameter overrides

### 3.4 Multi-Format Reporting
- **CSV**: Structured data for analysis and metrics
- **JSON**: Machine-readable API responses
- **HTML**: Rich web-based reports with styling
- **Table**: Human-readable console output
- **Artifacts**: GitLab CI integration with 1-week retention

### 3.5 Phased Execution Model
```
validate → compute-stop → compute-start → database-stop → database-start → report
```
- **Compute Tier**: EC2, ASG, EKS (Phase 1)
- **Database Tier**: RDS, Aurora PostgreSQL (Phase 2)
- **Dependencies**: Database operations wait for compute completion

## 4. Technical Implementation Details

### 4.1 Configuration Management
- **INI Format**: Standard configuration files with sections
- **Environment Variables**: Override support for flexible deployment
- **Multi-Account**: JSON-based account definitions
- **Validation**: Startup configuration validation with error handling

### 4.2 AWS Integration
- **Boto3 Clients**: Consistent AWS SDK usage across services
- **Pagination**: Proper handling of large result sets
- **Error Handling**: Custom exception classes with specific error types
- **Retry Logic**: Transient failure handling with exponential backoff

### 4.3 kubectl Integration (EKS)
- **AWS CLI**: Direct integration for kubeconfig management
- **Subprocess Execution**: Python 3.6+ compatible subprocess calls
- **Timeout Handling**: 60-second timeout for kubectl operations
- **Error Capture**: Comprehensive stdout/stderr capture

### 4.4 State Management (EKS)
```json
{
  "worker-group-1": {
    "original_min_size": 2,
    "original_max_size": 10,
    "original_desired_size": 3,
    "stored_at": "2025-05-29T16:23:42.500Z"
  }
}
```

### 4.5 Error Handling Patterns
- **Custom Exceptions**: Service-specific error classes
- **SNS Notifications**: Failure alerts with detailed context
- **Graceful Degradation**: Continue processing on non-critical errors
- **Comprehensive Logging**: Timestamped logs with context

## 5. Configuration and Setup

### 5.1 Prerequisites
- Python 3.7+
- AWS CLI configured with appropriate permissions
- Required packages: `boto3`, `tabulate`, `pytest`, `awscli`
- kubectl (for EKS operations)

### 5.2 Configuration Files

#### EC2 Scheduler Configuration
```ini
[DEFAULT]
default_region = ap-southeast-2
tag_key = scheduled
tag_value = enabled
sns_topic_arn = arn:aws:sns:ap-southeast-2:123456789012:ec2-scheduler-notifications

[LOGGING]
log_level = INFO
log_file = ec2-scheduler.log
```

#### EKS Scheduler Configuration
```ini
[aws]
region = us-west-2

[sns]
topic_arn = arn:aws:sns:us-west-2:123456789012:eks-scheduler-notifications

[logging]
level = INFO
file = 
```

#### RDS Scheduler Configuration
```ini
[aws]
region = ap-southeast-2
tag_key = Schedule
tag_value = enabled

[sns]
topic_arn = arn:aws:sns:ap-southeast-2:123456789012:rds-scheduler-notifications

[rds]
engine_filter = aurora-postgresql
cluster_verification_timeout = 600
instance_verification_timeout = 300
cluster_check_interval = 30
instance_check_interval = 15
```

### 5.3 Required IAM Permissions

#### Complete IAM Policy (All Services)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EC2Permissions",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:DescribeInstanceStatus"
            ],
            "Resource": "*"
        },
        {
            "Sid": "AutoScalingPermissions",
            "Effect": "Allow",
            "Action": [
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:SuspendProcesses",
                "autoscaling:ResumeProcesses",
                "autoscaling:UpdateAutoScalingGroup",
                "autoscaling:CreateOrUpdateTags",
                "autoscaling:DeleteTags",
                "autoscaling:DescribeTags"
            ],
            "Resource": "*"
        },
        {
            "Sid": "EKSPermissions",
            "Effect": "Allow",
            "Action": [
                "eks:ListNodegroups",
                "eks:DescribeNodegroup",
                "eks:UpdateNodegroupConfig",
                "eks:DescribeCluster"
            ],
            "Resource": "*"
        },
        {
            "Sid": "RDSPermissions",
            "Effect": "Allow",
            "Action": [
                "rds:DescribeDBInstances",
                "rds:StartDBInstance",
                "rds:StopDBInstance",
                "rds:DescribeDBClusters",
                "rds:StartDBCluster",
                "rds:StopDBCluster",
                "rds:ListTagsForResource"
            ],
            "Resource": "*"
        },
        {
            "Sid": "SNSPermissions",
            "Effect": "Allow",
            "Action": ["sns:Publish"],
            "Resource": ["arn:aws:sns:*:*:*-scheduler-notifications"]
        }
    ]
}
```

## 6. Usage Examples

### 6.1 Command Line Usage

#### EC2 Scheduler
```bash
cd ec2-scheduler/src

# Dry-run testing (always first)
python main.py --action stop --target both --dry-run

# Stop tagged EC2 instances and ASGs with verification
python main.py --action stop --target both --verify

# Start with specific account
python main.py --action start --target ec2 --accounts production

# Force stop for emergency situations
python main.py --action stop --target ec2 --force
```

#### EKS Scheduler
```bash
cd eks-scheduler/src

# Dry-run testing
python main.py --action stop --cluster production-cluster --dry-run

# Scale down cluster node groups
python main.py --action stop --cluster production-cluster --region us-west-2

# Scale up with minimum 2 nodes
python main.py --action start --cluster production-cluster --min-nodes 2
```

#### RDS Scheduler
```bash
cd rds-scheduler/src

# Dry-run testing (both Aurora and RDS)
python main.py --action stop --target both --dry-run --region us-west-2

# Stop Aurora PostgreSQL clusters only
python main.py --action stop --target clusters --verify --region us-west-2

# Stop standalone RDS instances only
python main.py --action stop --target instances --verify --region us-west-2

# Stop both with verification
python main.py --action stop --target both --verify --region us-west-2
```

### 6.2 GitLab CI Usage

#### Manual Operations
- `ec2-stop/start` - EC2 instance operations
- `asg-stop/start` - Auto Scaling Group operations
- `eks-scale-down/up` - EKS cluster scaling
- `rds-stop/start` - RDS and Aurora operations

#### Combined Operations
- `compute-stop-all` - Stops EC2, ASG, and EKS together
- `compute-start-all` - Starts EC2, ASG, and EKS together
- `database-stop/start` - RDS operations after compute tier

#### Flexible Operations
- `flexible-ec2` - Custom EC2/ASG parameters
- `flexible-eks` - Custom EKS cluster and min-nodes
- `flexible-rds` - Custom RDS target selection

#### Scheduled Operations
- `scheduled-shutdown` - Evening automated shutdown
- `scheduled-startup` - Morning automated startup

## 7. Current Status and Recent Changes

### 7.1 Project Maturity
- ✅ **EC2 Scheduler**: Production ready with comprehensive testing
- ✅ **EKS Scheduler**: **ENHANCED** - Production-grade with pod eviction, bootstrap validation, webhook management
- ✅ **RDS Scheduler**: Enhanced Aurora PostgreSQL support
- ✅ **GitLab CI Pipeline**: Phased execution with dependency management
- ✅ **Documentation**: Comprehensive guides and references

### 7.2 Recent Developments
- **EKS Autoscaler Management**: Sophisticated conflict resolution system
- **EKS Pod Eviction**: Graceful workload migration with PDB compliance
- **EKS Bootstrap Safety**: Deadlock prevention for zero-node recovery
- **EKS Webhook Support**: Admission controller awareness and validation
- **EKS Dependency Management**: Service startup order validation
- **RDS Aurora Support**: Full lifecycle management for PostgreSQL clusters
- **Dry-Run Enhancements**: Zero-impact testing across all services
- **State Management**: JSON-based persistence with GitLab CI artifacts
- **Reporting Improvements**: Multi-format outputs with HTML generation

### 7.3 Branch Structure
- **Main branch**: `main` (development)
- **Production branch**: `v1.1` (scheduled operations)
- **Test branch**: `v1.1.1` (flexible operations)
- **Current branch**: `v4` (active development)

### 7.4 Environment Configuration
- **Default region**: `ap-southeast-2`
- **EKS cluster**: `production-cluster`
- **Platform**: Linux 5.15.0-1055-aws
- **Python version**: 3.9+ recommended

## 8. Key Strengths and Innovations

### 8.1 EKS Production-Grade Enhancements
- **Autoscaler Conflict Resolution**: Prevents autoscaler from fighting manual operations
- **Graceful Pod Eviction**: Zero-downtime scaling with PDB compliance
- **Bootstrap Validation**: Prevents unrecoverable cluster states
- **Webhook Management**: Handles Kyverno, OPA, Istio, and custom webhooks
- **Dependency Orchestration**: Ensures services start in correct order
- **Result**: Enterprise-grade reliability for cost optimization workflows

### 8.2 Comprehensive Dry-Run System
- **Zero Risk**: No AWS API calls during testing
- **Realistic Simulation**: Mock data with representative scenarios
- **Complete Coverage**: All three schedulers support dry-run
- **Production Safety**: Test changes before deployment

### 8.3 Phased Execution Architecture
- **Dependency Management**: Database tier waits for compute tier
- **Cost Optimization**: Proper shutdown order for maximum savings
- **Risk Mitigation**: Controlled startup sequence
- **Operational Excellence**: GitLab CI integration with artifacts

### 8.4 Standardized Architecture
- **Consistency**: Identical patterns across all schedulers
- **Maintainability**: Common components and error handling
- **Extensibility**: Easy addition of new AWS services
- **Quality**: Unified testing and reporting strategies

## 9. Documentation Ecosystem

### 9.1 Comprehensive Guides
- **GitLab CI Management**: Complete CI/CD strategy and best practices
- **GitLab CI Quick Reference**: Quick reference for all jobs and variables
- **EKS Dry-Run Guide**: Comprehensive EKS dry-run safety guide
- **RDS Aurora Scheduler Guide**: Complete RDS and Aurora documentation
- **EKS Autoscaler Management**: Detailed autoscaler conflict resolution
- **Risk Assessment**: Mitigation strategies and best practices
- **AWS Cost Optimization**: Cost analysis and optimization strategies

### 9.2 Code Documentation
- **Inline Comments**: Comprehensive code documentation
- **Docstrings**: Python docstring standards
- **Type Hints**: Modern Python type annotations
- **README Files**: Service-specific documentation

## 10. Testing and Quality Assurance

### 10.1 Unit Testing
- **Test Coverage**: 22 Python files with comprehensive test cases
- **Mock Integration**: Boto3 mocking for AWS API calls
- **Error Scenarios**: Exception handling and edge cases
- **Continuous Integration**: Automated testing in GitLab CI

### 10.2 Dry-Run Testing
- **Pre-Production Validation**: Always test before real operations
- **Risk-Free Exploration**: Understand impact before changes
- **Report Generation**: Full reporting in dry-run mode
- **Confidence Building**: Validate configurations safely

## 11. Future Enhancements and Roadmap

### 11.1 Completed Enhancements
- ✅ **EKS Pod Management**: Graceful eviction with PDB compliance
- ✅ **EKS Bootstrap Safety**: Deadlock prevention mechanisms
- ✅ **EKS Webhook Support**: Full admission controller handling
- ✅ **EKS Dependencies**: Service startup order validation

### 11.2 Future Improvements
- **Multi-Cluster EKS**: Support for multiple EKS clusters
- **Enhanced Monitoring**: CloudWatch metrics integration
- **Cost Analytics**: Detailed cost savings reporting
- **External Webhooks**: Integration with external systems
- **Database Enhancements**: Support for additional RDS engines

### 11.2 Architectural Considerations
- **Microservices**: Individual service containerization
- **Event-Driven**: AWS EventBridge integration
- **Infrastructure as Code**: Terraform/CloudFormation templates
- **Multi-Region**: Cross-region resource management

## 12. Conclusion

The AWS Instance Scheduler represents a mature, production-ready solution for automated AWS resource management with a focus on cost optimization. With over 5,600 lines of Python code across 22 files, comprehensive documentation, and sophisticated features like EKS autoscaler conflict resolution, this system provides enterprise-grade capabilities for managing diverse AWS resources.

The project's strength lies in its standardized architecture, comprehensive dry-run capabilities, and phased execution model that ensures safe and efficient resource management. The extensive documentation and testing framework demonstrate a commitment to operational excellence and maintainability.

This system is particularly well-suited for organizations looking to optimize their AWS costs through automated resource scheduling while maintaining the flexibility and safety required for production environments.

---

**Report Generated**: June 16, 2025  
**Project Status**: Production Ready  
**Total LOC**: 5,662+  
**Schedulers**: 3 (EC2, EKS, RDS)  
**Supported Services**: EC2, ASG, EKS, RDS, Aurora PostgreSQL, SNS  
**Current Branch**: v4