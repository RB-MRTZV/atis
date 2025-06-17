#!/bin/bash

# Deploy Kyverno to test cluster for webhook handling testing

echo "Installing Kyverno via Helm..."

# Add Kyverno Helm repository
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

# Install Kyverno in kyverno namespace
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set replicaCount=1 \
  --set webhooksCleanup.enable=true \
  --set admissionController.replicas=1 \
  --set backgroundController.replicas=1 \
  --set cleanupController.replicas=1 \
  --set reportsController.replicas=1

# Wait for Kyverno to be ready
echo "Waiting for Kyverno pods to be ready..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=kyverno -n kyverno --timeout=300s

# Verify installation
echo "Verifying Kyverno installation..."
kubectl get pods -n kyverno
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl get mutatingwebhookconfigurations | grep kyverno

# Create a sample policy to test webhook
cat <<EOF | kubectl apply -f -
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-labels
spec:
  validationFailureAction: enforce
  background: true
  rules:
    - name: check-for-labels
      match:
        any:
        - resources:
            kinds:
            - Pod
            namespaces:
            - "test-*"
      validate:
        message: "label 'app' is required"
        pattern:
          metadata:
            labels:
              app: "?*"
EOF

echo "Kyverno deployed successfully!"
echo ""
echo "To test webhook handling:"
echo "1. Try creating a pod without 'app' label in test-namespace:"
echo "   kubectl create namespace test-namespace"
echo "   kubectl run test-pod --image=nginx -n test-namespace"
echo ""
echo "2. This should fail due to Kyverno policy"
echo ""
echo "3. Now create with label:"
echo "   kubectl run test-pod --image=nginx -n test-namespace --labels=app=test"
echo ""
echo "To uninstall Kyverno:"
echo "   helm uninstall kyverno -n kyverno"
echo "   kubectl delete namespace kyverno"