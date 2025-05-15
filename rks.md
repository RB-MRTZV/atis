# Resource Analysis Commands for EKS Clusters

Here's a comprehensive list of kubectl and eksctl commands to analyze the resource needs and capacity of your EKS clusters:

## Pod Resource Analysis

```bash
# List all pods with their CPU/memory requests
kubectl get pods -o custom-columns=NAME:.metadata.name,CPU_REQUEST:.spec.containers[*].resources.requests.cpu,MEMORY_REQUEST:.spec.containers[*].resources.requests.memory -A

# List all pods with their CPU/memory limits
kubectl get pods -o custom-columns=NAME:.metadata.name,CPU_LIMIT:.spec.containers[*].resources.limits.cpu,MEMORY_LIMIT:.spec.containers[*].resources.limits.memory -A

# Get detailed resource usage for pods (requires metrics-server)
kubectl top pods -A

# Get resource usage sorted by CPU consumption
kubectl top pods -A --sort-by=cpu

# Get resource usage sorted by memory consumption
kubectl top pods -A --sort-by=memory

# Analyze pod QoS classes (helps understand eviction priority)
kubectl get pods -A -o custom-columns=NAME:.metadata.name,QOS:.status.qosClass

# Check pods without resource requests/limits
kubectl get pods -A -o go-template='{{range .items}}{{if not .spec.containers[0].resources.requests}}{{.metadata.name}}{{"\n"}}{{end}}{{end}}'
```

## Node Capacity Analysis

```bash
# Get node capacity information
kubectl describe nodes | grep -A 5 "Capacity"
kubectl describe nodes | grep -A 10 "Allocated resources"

# Get nodes with their instance types
kubectl get nodes -o custom-columns=NAME:.metadata.name,INSTANCE-TYPE:.metadata.labels.node\\.kubernetes\\.io/instance-type

# Get detailed resource usage for nodes
kubectl top nodes

# Check node utilization percentages
kubectl top nodes | awk '{print $1, $2, $4}' | column -t

# Get pods running on a specific node
kubectl get pods -A -o wide --field-selector spec.nodeName=<node-name>

# Count pods per node
kubectl get pods -A -o wide | grep -v NAMESPACE | awk '{print $8}' | sort | uniq -c

# Check available pod capacity per node
kubectl get nodes -o custom-columns=NAME:.metadata.name,MAX-PODS:.status.capacity.pods
```

## Cluster-Wide Analysis

```bash
# Get all namespaces with resource quotas
kubectl get resourcequota --all-namespaces

# View Pod Disruption Budgets (important for downscaling)
kubectl get pdb -A

# Check deployments and their replica counts
kubectl get deployments -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,DESIRED:.spec.replicas,CURRENT:.status.replicas

# Get StatefulSets (which may have node affinity requirements)
kubectl get statefulsets -A

# Check daemonsets (which run on every node)
kubectl get daemonsets -A

# Check for any node affinity/anti-affinity rules
kubectl get pods -A -o yaml | grep -A 10 affinity
```

## EKS-Specific Commands

```bash
# Get EKS cluster information
eksctl get cluster --name <cluster-name>

# Get node groups for your EKS cluster
eksctl get nodegroup --cluster <cluster-name>

# Get addon information
eksctl get addon --cluster <cluster-name>

# Check autoscaler configuration
eksctl get iamserviceaccount --cluster <cluster-name>

# Describe a node group to see its scaling configuration
eksctl describe nodegroup --cluster <cluster-name> --name <nodegroup-name>

# Get Fargate profiles (if used)
eksctl get fargateprofile --cluster <cluster-name>
```

## Advanced Analysis

```bash
# Simulate pod scheduling to check if resources are available
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data --dry-run=client

# Check pod distribution by namespace
kubectl get pods -A | grep -v NAMESPACE | awk '{print $1}' | sort | uniq -c

# Analyze pod scheduling failures
kubectl get events -A | grep -i "Failed" | grep -i "schedule"

# Check for taints and tolerations
kubectl describe nodes | grep -A 5 Taints

# Get HorizontalPodAutoscalers (affects resource needs)
kubectl get hpa -A
```

## AWS-Specific Resource Analysis

```bash
# Get CloudWatch metrics for EKS using AWS CLI
aws cloudwatch get-metric-statistics --namespace AWS/EKS --metric-name pod_cpu_utilization --dimensions Name=ClusterName,Value=<cluster-name> --start-time $(date -u +%Y-%m-%dT%H:%M:%SZ --date '24 hours ago') --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) --period 3600 --statistics Average

# Check node group autoscaling activity
aws autoscaling describe-scaling-activities --auto-scaling-group-name <asg-name>
```

These commands will give you detailed insights into your workload resource requirements and cluster capacity, helping you determine if consolidating to a single node after hours is feasible, and what instance type that node should be.​​​​​​​​​​​​​​​​