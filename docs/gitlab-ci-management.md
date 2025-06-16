# GitLab CI Management Guide for AWS Instance Scheduler

## Overview

This guide explains how to manage your multi-service AWS scheduler using GitLab CI with a phased approach that ensures proper dependency management and cost optimization.

## Architecture

### Service Tiers
1. **Compute Tier (Phase 1)**: EC2, ASG, EKS
2. **Database Tier (Phase 2)**: RDS (runs after compute tier)

### Pipeline Stages
```
validate → compute-stop → compute-start → database-stop → database-start → report
```

## Manual Operations (Initial Phase)

### Individual Service Control

#### EC2 Operations
```bash
# Manual jobs available:
- ec2-stop          # Stop tagged EC2 instances
- ec2-start         # Start tagged EC2 instances
```

#### ASG Operations
```bash
# Manual jobs available:
- asg-stop          # Stop tagged ASG instances
- asg-start         # Start tagged ASG instances
```

#### EKS Operations
```bash
# Manual jobs available:
- eks-scale-down    # Scale node groups to 0
- eks-scale-up      # Scale node groups back up
```

#### RDS Operations
```bash
# Manual jobs available:
- rds-stop          # Stop tagged RDS instances
- rds-start         # Start tagged RDS instances
```

### Combined Operations

#### All Compute Resources
```bash
# Recommended for coordinated shutdown/startup:
- compute-stop-all  # Stops EC2, ASG, and EKS together
- compute-start-all # Starts EC2, ASG, and EKS together
```

#### Phased Operations with Dependencies
```bash
# For proper sequencing:
1. Run: compute-stop-all
2. Then: rds-stop (has dependency on compute-stop-all)

# For startup:
1. Run: compute-start-all  
2. Then: rds-start (has dependency on compute-start-all)
```

### Flexible Operations

Use these for custom parameters:

```bash
# flexible-ec2
Variables:
- ACTION: start|stop
- TARGET: ec2|asg|both
- ACCOUNTS: production|staging|all

# flexible-eks  
Variables:
- ACTION: start|stop
- CUSTOM_CLUSTER: override cluster name
- CUSTOM_MIN_NODES: override min nodes

# flexible-rds
Variables:
- ACTION: start|stop
```

## Scheduled Operations (Production Phase)

### Recommended Schedule Setup

#### Evening Shutdown (7 PM weekdays)
```yaml
# GitLab Schedule Variables:
SCHEDULE_TYPE: shutdown
```
**What it does:**
1. Stops all compute resources (EC2, ASG, EKS)
2. Then stops database resources (RDS)
3. Saves state for restoration

#### Morning Startup (7 AM weekdays)
```yaml
# GitLab Schedule Variables:
SCHEDULE_TYPE: startup
```
**What it does:**
1. Starts all compute resources (EC2, ASG, EKS)
2. Then starts database resources (RDS)
3. Restores previous configurations

### Setting Up Schedules in GitLab

1. **Go to**: Project → CI/CD → Schedules
2. **Create Schedule**: 
   - **Description**: "Evening Shutdown"
   - **Interval Pattern**: `0 19 * * 1-5` (7 PM weekdays)
   - **Target Branch**: `v1.1`
   - **Variables**: 
     - `SCHEDULE_TYPE` = `shutdown`

3. **Create Schedule**:
   - **Description**: "Morning Startup"  
   - **Interval Pattern**: `0 7 * * 1-5` (7 AM weekdays)
   - **Target Branch**: `v1.1`
   - **Variables**:
     - `SCHEDULE_TYPE` = `startup`

## Best Practices

### 1. Testing Strategy

#### Always Test First
```bash
# Use dry-run-all job to validate:
- Checks all services without making changes
- Validates configurations
- Reports what would be affected
```

#### Gradual Rollout
```bash
# Phase 1: Manual individual services
1. Test each service separately
2. Verify state management works
3. Check notifications

# Phase 2: Manual combined operations  
1. Test compute-stop-all + rds-stop sequence
2. Test compute-start-all + rds-start sequence
3. Verify dependencies work correctly

# Phase 3: Scheduled operations
1. Set up schedules
2. Monitor first few runs
3. Adjust timing if needed
```

### 2. State Management

#### EKS State Persistence
- State files stored in `eks-scheduler/src/state/`
- Artifacts persist for 7 days between jobs
- Dependencies ensure state availability

#### Monitoring State
```bash
# Check artifacts after scale-down:
- Download artifacts from eks-scale-down job
- Verify state files contain original configurations
- Ensure scale-up job can access state
```

### 3. Error Handling

#### Job Dependencies
```yaml
# RDS jobs use 'needs' with 'optional: true'
# This means:
- RDS will wait for compute tier to complete
- If compute tier fails, RDS can still run manually
- No blocking dependencies that prevent recovery
```

#### Recovery Procedures
```bash
# If scheduled job fails:
1. Check job logs for specific error
2. Run individual service jobs manually
3. Use flexible jobs with custom parameters
4. Verify state files if EKS involved
```

### 4. Cost Optimization

#### Timing Considerations
```bash
# Recommended schedule:
- Shutdown: 7 PM (after business hours)
- Startup: 7 AM (before business hours)
- Weekend: Keep shutdown (optional startup Saturday AM)
```

#### Resource Prioritization
```bash
# Shutdown order (most savings first):
1. EKS (highest compute cost)
2. EC2 instances (variable cost)
3. ASG instances (auto-scaling cost)
4. RDS (storage continues, compute stops)

# Startup order (dependencies first):
1. Compute resources (EC2, ASG, EKS)
2. Database resources (RDS)
```

## Monitoring and Notifications

### Artifacts and Reports
- All jobs generate reports in `reports/` directory
- JUnit XML for GitLab integration
- CSV/JSON reports for analysis
- State files for EKS restoration

### SNS Notifications
- Configured in each scheduler's `config.ini`
- Consolidated notifications via `notify-only` job
- Success/failure alerts for scheduled operations

### GitLab Integration
- Pipeline status visible in GitLab UI
- Job artifacts downloadable for 1 week
- Environment tracking for production deployments
- Manual approval gates for safety

## Troubleshooting

### Common Issues

#### EKS State Not Found
```bash
# Solution:
1. Check if eks-scale-down job completed successfully
2. Verify artifacts were generated
3. Re-run eks-scale-down if needed
4. Use flexible-eks with custom parameters
```

#### RDS Job Skipped
```bash
# Cause: Compute tier job failed
# Solution:
1. Fix compute tier issue first
2. Run RDS job manually
3. Or use flexible-rds job
```

#### Schedule Not Triggering
```bash
# Check:
1. Schedule is active in GitLab
2. Target branch exists (v1.1)
3. SCHEDULE_TYPE variable is set correctly
4. Cron expression is valid
```

### Emergency Procedures

#### Force Start All Resources
```bash
# Use flexible jobs with ACTION=start:
1. flexible-ec2 (ACTION=start, TARGET=both)
2. flexible-eks (ACTION=start)  
3. flexible-rds (ACTION=start)
```

#### Emergency Stop
```bash
# Use individual stop jobs if combined fails:
1. ec2-stop
2. asg-stop  
3. eks-scale-down
4. rds-stop
```

## Migration Path

### Phase 1: Manual Testing (Current)
- Use individual service jobs
- Test each scheduler separately
- Verify configurations and notifications

### Phase 2: Manual Coordination
- Use combined operations (compute-stop-all, etc.)
- Test dependency chains
- Validate state management

### Phase 3: Scheduled Automation
- Set up GitLab schedules
- Monitor first few automated runs
- Fine-tune timing and parameters

### Phase 4: Full Production
- Automated daily operations
- Exception handling procedures
- Regular review and optimization

This approach ensures a smooth transition from manual operations to fully automated cost optimization while maintaining safety and reliability. 