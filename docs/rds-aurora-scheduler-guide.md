# RDS & Aurora PostgreSQL Scheduler Guide

## Overview

The RDS Scheduler provides comprehensive management for both standalone RDS instances and Aurora PostgreSQL clusters. It supports tag-based discovery, state verification, dry-run testing, and flexible target selection for cost optimization and automated resource management.

## Features

### ✅ Supported Resources
- **Aurora PostgreSQL Clusters** - Complete cluster start/stop operations
- **Standalone RDS Instances** - Individual database instance management
- **Mixed Environments** - Handle both resource types simultaneously

### ✅ Core Capabilities
- **Tag-based Discovery** - Filter resources using configurable tags
- **Target Selection** - Choose clusters, instances, or both
- **State Verification** - Confirm resources reach expected states
- **Comprehensive Dry-Run** - Test operations without making changes
- **Multi-Account Support** - Process multiple AWS accounts
- **Enhanced Reporting** - Detailed CSV, JSON, and table reports
- **SNS Notifications** - Automated alerts and summaries

## Configuration

### config.ini
```ini
[aws]
region = ap-southeast-2
tag_key = Schedule
tag_value = enabled

[sns]
topic_arn = arn:aws:sns:ap-southeast-2:123456789012:rds-scheduler-notifications

[logging]
level = INFO
file = rds-scheduler.log

[rds]
# Aurora PostgreSQL specific settings
engine_filter = aurora-postgresql
# Verification timeouts (in seconds)
cluster_verification_timeout = 600
instance_verification_timeout = 300
# Check intervals (in seconds)
cluster_check_interval = 30
instance_check_interval = 15
```

### accounts.json
```json
[
    {
        "name": "production",
        "region": "ap-southeast-2",
        "description": "Production environment"
    },
    {
        "name": "staging", 
        "region": "us-west-2",
        "description": "Staging environment"
    }
]
```

## Command Line Usage

### Basic Operations

#### Stop Operations
```bash
# Stop both Aurora clusters and RDS instances
python main.py --action stop --target both --verify --region ap-southeast-2

# Stop Aurora PostgreSQL clusters only
python main.py --action stop --target clusters --verify --region ap-southeast-2

# Stop standalone RDS instances only
python main.py --action stop --target instances --verify --region ap-southeast-2
```

#### Start Operations
```bash
# Start both Aurora clusters and RDS instances
python main.py --action start --target both --verify --region ap-southeast-2

# Start Aurora PostgreSQL clusters only
python main.py --action start --target clusters --verify --region ap-southeast-2

# Start standalone RDS instances only
python main.py --action start --target instances --verify --region ap-southeast-2
```

### Advanced Options

#### Dry-Run Testing
```bash
# Test stop operation without making changes
python main.py --action stop --target both --dry-run --region ap-southeast-2

# Test start operation for clusters only
python main.py --action start --target clusters --dry-run --region ap-southeast-2
```

#### Account-Specific Operations
```bash
# Process specific account only
python main.py --action stop --target both --account production --region ap-southeast-2

# Custom tag filtering
python main.py --action stop --target both --tag-key Environment --tag-value Production
```

#### Notification-Only Mode
```bash
# Send notifications without performing operations
python main.py --action start --target both --notify-only --region ap-southeast-2
```

### Complete Command Reference

```bash
python main.py [OPTIONS]

Required Arguments:
  --action {start,stop}         Action to perform on RDS resources

Optional Arguments:
  --target {clusters,instances,both}  Target resource type (default: both)
  --region REGION              AWS region (defaults to config)
  --account ACCOUNT            Account name to process
  --tag-key TAG_KEY            Tag key to filter resources (defaults to config)
  --tag-value TAG_VALUE        Tag value to filter resources (defaults to config)
  --dry-run                    Simulate actions without executing
  --verify                     Verify resource states after action
  --notify-only                Send notification without performing actions
```

## Resource Tagging

### Required Tags
Resources must be tagged with the configured tag key/value to be managed by the scheduler:

```bash
# Default tag configuration
Tag Key: Schedule
Tag Value: enabled
```

### Aurora Cluster Tagging
```bash
# Tag Aurora cluster
aws rds add-tags-to-resource \
  --resource-name arn:aws:rds:region:account:cluster:my-aurora-cluster \
  --tags Key=Schedule,Value=enabled
```

### RDS Instance Tagging
```bash
# Tag RDS instance
aws rds add-tags-to-resource \
  --resource-name arn:aws:rds:region:account:db:my-rds-instance \
  --tags Key=Schedule,Value=enabled
```

## Dry-Run Mode

### Features
- ❌ **No AWS API calls** for start/stop operations
- ✅ **Mock data simulation** with realistic Aurora and RDS responses
- ✅ **Complete workflow testing** including verification steps
- ✅ **Report generation** with dry-run indicators
- ✅ **Clear logging** with `[DRY RUN]` prefixes

### Example Dry-Run Output
```
2024-01-15 10:30:00 - rds_operations - INFO - RDS Operations initialized in DRY RUN mode - no actual changes will be made
2024-01-15 10:30:01 - rds_operations - INFO - [DRY RUN] Would search for tagged Aurora clusters
2024-01-15 10:30:01 - rds_operations - INFO - [DRY RUN] Would stop Aurora cluster: mock-aurora-cluster-1
2024-01-15 10:30:01 - rds_operations - INFO - [DRY RUN] Would verify cluster states: stopped
```

## State Verification

### Aurora Clusters
- **Default Timeout**: 600 seconds (10 minutes)
- **Check Interval**: 30 seconds
- **Expected States**: `available` (running), `stopped` (stopped)

### RDS Instances
- **Default Timeout**: 300 seconds (5 minutes)
- **Check Interval**: 15 seconds
- **Expected States**: `available` (running), `stopped` (stopped)

### Verification Process
1. Execute start/stop operation
2. Wait for state transition to begin
3. Poll resource status at configured intervals
4. Report success when expected state reached
5. Report timeout if state not reached within limit

## Reporting

### Report Types

#### CSV Report
- Structured data for analysis and auditing
- Includes all operation details and timestamps
- Saved as: `reports/rds_scheduler_report_YYYYMMDD_HHMMSS.csv`

#### JSON Report
- Machine-readable format with metadata
- Includes summary statistics and detailed results
- Saved as: `reports/rds_scheduler_report_YYYYMMDD_HHMMSS.json`

#### Table Report
- Human-readable console output
- Formatted for easy reading and debugging
- Saved as: `reports/rds_scheduler_report_YYYYMMDD_HHMMSS.txt`

### Report Fields
- **Account**: AWS account name
- **Region**: AWS region
- **Resource Type**: Aurora Cluster or RDS Instance
- **Resource ID**: Cluster identifier or instance identifier
- **Previous State**: State before operation
- **New State**: State after operation
- **Action**: Operation performed (start/stop/verify)
- **Status**: Success/Failed/DryRun/Verified
- **Error**: Error message if operation failed
- **Timestamp**: ISO format timestamp

### Sample Report Output
```
+-------------+------------------+----------------+-------------------------+----------------+-------------+--------+----------+-------+
| Account     | Region           | Resource Type  | Resource ID             | Previous State | New State   | Action | Status   | Error |
+=============+==================+================+=========================+================+=============+========+==========+=======+
| production  | ap-southeast-2   | Aurora Cluster | prod-aurora-postgres-1  | available      | stopping    | stop   | Success  |       |
| production  | ap-southeast-2   | RDS Instance   | prod-postgres-replica   | available      | stopping    | stop   | Success  |       |
| staging     | us-west-2        | Aurora Cluster | staging-aurora-cluster  | available      | stopping    | stop   | Success  |       |
+-------------+------------------+----------------+-------------------------+----------------+-------------+--------+----------+-------+
```

## GitLab CI Integration

### Individual Jobs
```yaml
# Aurora clusters only
aurora-stop:
  script:
    - python rds-scheduler/src/main.py --action stop --target clusters --verify --region $AWS_DEFAULT_REGION

# RDS instances only  
rds-instances-start:
  script:
    - python rds-scheduler/src/main.py --action start --target instances --verify --region $AWS_DEFAULT_REGION

# Both resources
rds-stop:
  script:
    - python rds-scheduler/src/main.py --action stop --target both --verify --region $AWS_DEFAULT_REGION
```

### Flexible Job
```yaml
flexible-rds:
  script:
    - TARGET_TYPE=${RDS_TARGET:-both}
    - python rds-scheduler/src/main.py --action $ACTION --target $TARGET_TYPE --verify --region $AWS_DEFAULT_REGION
  variables:
    RDS_TARGET: "both"  # Override with "clusters" or "instances"
```

### Scheduled Operations
```yaml
scheduled-shutdown:
  script:
    - echo "Phase 2: Stopping database resources..."
    - python rds-scheduler/src/main.py --action stop --target both --verify --region $AWS_DEFAULT_REGION

scheduled-startup:
  script:
    - echo "Phase 2: Starting database resources..."
    - python rds-scheduler/src/main.py --action start --target both --verify --region $AWS_DEFAULT_REGION
```

## Best Practices

### 1. Testing Strategy
```bash
# Always test with dry-run first
python main.py --action stop --target both --dry-run

# Test individual resource types
python main.py --action stop --target clusters --dry-run
python main.py --action stop --target instances --dry-run

# Verify operations work as expected
python main.py --action stop --target both --verify
```

### 2. Phased Rollout
1. **Development**: Test with dry-run mode
2. **Staging**: Test with real resources in staging environment
3. **Production**: Start with manual operations, then automate

### 3. Resource Organization
- **Consistent Tagging**: Use standardized tag keys and values
- **Environment Separation**: Different tags for prod/staging/dev
- **Documentation**: Maintain inventory of managed resources

### 4. Monitoring and Alerting
- **SNS Notifications**: Configure for operation results
- **Report Review**: Regular review of operation reports
- **Error Handling**: Monitor for failed operations and timeouts

### 5. Cost Optimization
- **Aurora Clusters**: Highest cost savings when stopped
- **RDS Instances**: Compute cost savings, storage costs continue
- **Scheduling**: Stop during off-hours, start before business hours

## Troubleshooting

### Common Issues

#### No Resources Found
```
Found 0 tagged Aurora PostgreSQL clusters
Found 0 tagged RDS instances
```
**Solution**: Verify resource tagging and tag configuration

#### Verification Timeout
```
Cluster verification timed out after 600 seconds
```
**Solutions**:
- Increase timeout in configuration
- Check cluster status in AWS console
- Verify cluster is not in maintenance window

#### Permission Errors
```
Error stopping Aurora cluster: AccessDenied
```
**Solution**: Verify IAM permissions for RDS operations

#### Region Mismatch
```
Error finding tagged Aurora clusters: InvalidParameterValue
```
**Solution**: Ensure region parameter matches resource locations

### Debug Mode
```bash
# Enable debug logging
python main.py --action stop --target both --dry-run --region ap-southeast-2

# Check configuration
python -c "from config_manager import ConfigManager; cm = ConfigManager(); print(cm.config.sections())"
```

### Emergency Procedures
```bash
# Force start all resources
python main.py --action start --target both --region ap-southeast-2

# Start specific resource type only
python main.py --action start --target clusters --region ap-southeast-2
python main.py --action start --target instances --region ap-southeast-2

# Check status without operations
aws rds describe-db-clusters --query 'DBClusters[*].[DBClusterIdentifier,Status]'
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,DBInstanceStatus]'
```

## Performance Considerations

### Aurora Clusters
- **Start Time**: 2-5 minutes typically
- **Stop Time**: 1-3 minutes typically
- **Verification**: Check every 30 seconds, 10-minute timeout

### RDS Instances
- **Start Time**: 1-3 minutes typically
- **Stop Time**: 30 seconds - 2 minutes typically
- **Verification**: Check every 15 seconds, 5-minute timeout

### Batch Operations
- **Parallel Processing**: Operations run in parallel for multiple resources
- **Error Isolation**: Failed operations don't affect successful ones
- **Progress Tracking**: Individual resource status reported

## Security Considerations

### IAM Permissions
- Use least privilege principle
- Separate policies for different environments
- Regular permission audits

### Resource Access
- Tag-based filtering provides security boundary
- Account-specific operations limit scope
- Dry-run mode for safe testing

### Audit Trail
- Comprehensive logging of all operations
- Report generation for compliance
- SNS notifications for monitoring

## Migration from Basic RDS Scheduler

### Key Changes
1. **Target Parameter**: Now required, use `--target both` for previous behavior
2. **Aurora Support**: New cluster operations and verification
3. **Enhanced Reporting**: Resource type differentiation
4. **Improved Dry-Run**: More comprehensive simulation

### Migration Steps
1. Update command line calls to include `--target both`
2. Review and update configuration files
3. Test with dry-run mode
4. Update GitLab CI job definitions
5. Verify SNS topic configurations

### Backward Compatibility
- Configuration files remain compatible
- Account definitions unchanged
- Core functionality preserved
- Enhanced features are additive

---

**Next Steps**: Review the [GitLab CI Management Guide](gitlab-ci-management.md) for complete pipeline integration strategies. 