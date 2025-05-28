# Check Kyverno deployment method
kubectl get deployment kyverno -n kyverno -o yaml | grep -A5 -B5 "image:"

# Check if webhooks are auto-generated (look for owner references)
kubectl get validatingwebhookconfigurations -o yaml | grep -A10 -B5 kyverno

# Check Kyverno policies storage
kubectl get clusterpolicy,policy -A

# Check Kyverno config/settings
kubectl get configmap -n kyverno
kubectl describe deployment kyverno -n kyverno

# Check if Kyverno manages its own webhooks automatically
kubectl logs deployment/kyverno -n kyverno | grep -i webhook
