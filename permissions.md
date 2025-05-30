## **IAM Permissions Required**

### **1. AWS EKS API Permissions (for boto3 operations)**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListClusters",
                "eks:ListNodegroups",
                "eks:DescribeNodegroup",
                "eks:UpdateNodegroupConfig",
                "eks:DescribeUpdate"
            ],
            "Resource": [
                "arn:aws:eks:*:*:cluster/*",
                "arn:aws:eks:*:*:nodegroup/*/*/*"
            ]
        }
    ]
}
```

### **2. Auto Scaling Permissions (if using ASG directly)**

```json
{
    "Effect": "Allow",
    "Action": [
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:UpdateAutoScalingGroup"
    ],
    "Resource": "*"
}
```

### **3. EC2 Permissions (for node operations)**

```json
{
    "Effect": "Allow",
    "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes"
    ],
    "Resource": "*"
}
```

## **Kubernetes RBAC Permissions (for kubectl operations)**

### **Option 1: Add IAM User/Role to aws-auth ConfigMap**

```bash
# Check current aws-auth
kubectl get configmap aws-auth -n kube-system -o yaml

# Edit to add your IAM user/role
kubectl edit configmap aws-auth -n kube-system
```

**Add this to the configmap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapUsers: |
    - userarn: arn:aws:iam::ACCOUNT:user/YOUR-USERNAME
      username: eks-scaler
      groups:
        - system:masters  # Full admin access
  mapRoles: |
    - rolearn: arn:aws:iam::ACCOUNT:role/YOUR-ROLE
      username: eks-scaler-role
      groups:
        - system:masters  # Full admin access
```

### **Option 2: Create Custom RBAC (More Secure)**

**Create ClusterRole with specific permissions:**

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: eks-scaler-role
rules:
# Node operations
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "describe"]

# Pod operations  
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "delete", "describe"]

# Deployment operations
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "patch", "update", "describe"]

# Service and endpoint operations
- apiGroups: [""]
  resources: ["services", "endpoints"]
  verbs: ["get", "list", "describe"]

# Event viewing
- apiGroups: [""]
  resources: ["events"]
  verbs: ["get", "list"]

# Webhook management (critical for your use case)
- apiGroups: ["admissionregistration.k8s.io"]
  resources: ["validatingwebhookconfigurations", "mutatingwebhookconfigurations"]
  verbs: ["get", "list", "delete", "describe"]

# Policy resources (for Kyverno)
- apiGroups: ["kyverno.io"]
  resources: ["clusterpolicies", "policies"]
  verbs: ["get", "list", "describe"]

# ConfigMap access (for aws-auth if needed)
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]
  resourceNames: ["aws-auth"]

# Namespace operations
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
```

**Bind to IAM user/role:**

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: eks-scaler-binding
subjects:
- kind: User
  name: eks-scaler  # Must match username in aws-auth
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: eks-scaler-role
  apiGroup: rbac.authorization.k8s.io
```

## **GitLab Runner Specific Permissions**

### **For GitLab CI Service Account:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListNodegroups",
                "eks:DescribeNodegroup", 
                "eks:UpdateNodegroupConfig",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

### **GitLab Runner Configuration:**

```yaml
# In your .gitlab-ci.yml
variables:
  AWS_DEFAULT_REGION: us-west-2
  KUBECONFIG: /tmp/kubeconfig

before_script:
  - aws eks update-kubeconfig --region $AWS_DEFAULT_REGION --name $CLUSTER_NAME
  - kubectl version --client
```

## **Minimal Security Approach**

### **Create dedicated EKS scaling role:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListNodegroups",
                "eks:DescribeNodegroup",
                "eks:UpdateNodegroupConfig"
            ],
            "Resource": [
                "arn:aws:eks:us-west-2:ACCOUNT:cluster/CLUSTER-NAME",
                "arn:aws:eks:us-west-2:ACCOUNT:nodegroup/CLUSTER-NAME/*/*"
            ]
        }
    ]
}
```

## **Verification Commands**

### **Test IAM permissions:**
```bash
# Test EKS access
aws eks describe-cluster --name YOUR-CLUSTER-NAME
aws eks list-nodegroups --cluster-name YOUR-CLUSTER-NAME

# Test kubectl access
kubectl auth can-i get nodes
kubectl auth can-i delete validatingwebhookconfigurations
kubectl auth can-i scale deployments
```

### **Debug permission issues:**
```bash
# Check current IAM identity
aws sts get-caller-identity

# Check kubectl permissions
kubectl auth can-i --list

# Check if you're in aws-auth
kubectl get configmap aws-auth -n kube-system -o yaml | grep -A 5 -B 5 YOUR-USERNAME
```

## **Recommended Setup**

**For Development:**
- Add your IAM user to `system:masters` group in aws-auth
- Quick and gives full access

**For Production:**
- Create dedicated IAM role for scaling operations
- Use custom RBAC with minimal required permissions
- Separate roles for different environments

**Critical permissions for your use case:**
- `eks:UpdateNodegroupConfig` - For scaling nodes
- `admissionregistration.k8s.io` resources - For webhook cleanup
- `apps/deployments` - For autoscaler management

The webhook deletion permission is **critical** since that's what prevented your bootstrap deadlock.​​​​​​​​​​​​​​​​