# GitLab CI Quick Reference

## 🚀 Manual Jobs (Individual Services)

### EC2 & ASG
| Job | Action | Description |
|-----|--------|-------------|
| `ec2-stop` | Stop | Stop tagged EC2 instances |
| `ec2-start` | Start | Start tagged EC2 instances |
| `asg-stop` | Stop | Stop tagged ASG instances |
| `asg-start` | Start | Start tagged ASG instances |

### EKS (Enhanced)
| Job | Action | Description |
|-----|--------|-------------|
| `eks-scale-down` | Stop | Scale node groups to 0 with graceful pod eviction |
| `eks-scale-up` | Start | Scale node groups with bootstrap validation |

### RDS
| Job | Action | Description |
|-----|--------|-------------|
| `rds-stop` | Stop | Stop tagged RDS instances |
| `rds-start` | Start | Start tagged RDS instances |

## 🎯 Combined Operations

### Compute Tier (Recommended)
| Job | Action | Description |
|-----|--------|-------------|
| `compute-stop-all` | Stop | Stop EC2, ASG, and EKS together |
| `compute-start-all` | Start | Start EC2, ASG, and EKS together |

### Phased Execution (With Dependencies)
```
1. compute-stop-all  →  2. rds-stop
1. compute-start-all →  2. rds-start
```

## ⚙️ Flexible Jobs (Custom Parameters)

### Variables You Can Set
| Job | Variables | Example Values |
|-----|-----------|----------------|
| `flexible-ec2` | `ACTION`, `TARGET`, `ACCOUNTS` | `start`, `both`, `production` |
| `flexible-eks` | `ACTION`, `CUSTOM_CLUSTER`, `CUSTOM_MIN_NODES` | `stop`, `dev-cluster`, `2` |
| `flexible-rds` | `ACTION` | `start` |

## 🧪 Testing & Validation

| Job | Purpose |
|-----|---------|
| `dry-run-all` | Test all services without making changes |
| `validate` | Validate configurations and dependencies |

## 📅 Scheduled Operations

### Setup in GitLab: Project → CI/CD → Schedules

#### Evening Shutdown (7 PM weekdays)
```
Cron: 0 19 * * 1-5
Branch: v1.1
Variables: SCHEDULE_TYPE = shutdown
```

#### Morning Startup (7 AM weekdays)
```
Cron: 0 7 * * 1-5  
Branch: v1.1
Variables: SCHEDULE_TYPE = startup
```

## 🚨 Emergency Procedures

### Quick Start All Resources
```bash
1. flexible-ec2 (ACTION=start, TARGET=both)
2. flexible-eks (ACTION=start)
3. flexible-rds (ACTION=start)
```

### Quick Stop All Resources
```bash
1. ec2-stop
2. asg-stop
3. eks-scale-down
4. rds-stop
```

## 📊 Monitoring

### Artifacts Generated
- `reports/` - CSV, JSON, table reports
- `eks-scheduler/src/state/` - EKS state files
- JUnit XML for GitLab integration

### Notifications
- SNS notifications configured per service
- `notify-only` job for consolidated alerts

## 🔧 Common Variables

### Global Variables (Set in GitLab CI)
```yaml
AWS_DEFAULT_REGION: "ap-southeast-2"
EKS_CLUSTER_NAME: "production-cluster"
MIN_NODES: "1"
ACTION: "start"  # or "stop"
TARGET: "both"   # ec2, asg, or both
```

### Runtime Variables (Set when triggering)
```yaml
CUSTOM_CLUSTER: ""      # Override cluster name
CUSTOM_MIN_NODES: ""    # Override min nodes
ACCOUNTS: "production"  # Account filter
```

## 📋 Execution Order Recommendations

### Manual Testing Phase
1. `dry-run-all` (validate everything)
2. Individual service jobs (test each)
3. Combined operations (test coordination)

### Production Phase
1. `scheduled-shutdown` (evening)
2. `scheduled-startup` (morning)
3. Monitor and adjust as needed

## 🎯 Cost Optimization Priority

### Shutdown Order (Highest Savings First)
1. EKS clusters (highest compute cost)
2. EC2 instances (variable cost)
3. ASG instances (auto-scaling cost)  
4. RDS instances (storage continues)

### Startup Order (Dependencies First)
1. Compute resources (EC2, ASG, EKS)
2. Database resources (RDS)

## 🔍 Troubleshooting Quick Checks

### EKS Issues
- Check artifacts from `eks-scale-down`
- Verify state files exist
- Use `flexible-eks` with custom parameters

### RDS Issues  
- Ensure compute tier completed first
- Check `needs` dependencies
- Run `flexible-rds` manually

### Schedule Issues
- Verify schedule is active
- Check branch exists (v1.1)
- Validate `SCHEDULE_TYPE` variable
- Test cron expression 