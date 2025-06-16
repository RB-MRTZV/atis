#!/bin/bash

# EKS Scheduler - Static Configuration Runner
# This script runs the EKS scheduler with static account configuration
# bypassing any configuration file issues

set -e

# Default values
ACCOUNT_NAME="production"
ACCOUNT_ID="123456789012"
REGION="us-west-2"
ACTION=""
CLUSTER=""
MIN_NODES=1
DRY_RUN=""

# Function to show usage
show_usage() {
    echo "Usage: $0 --action <start|stop> --cluster <cluster-name> [options]"
    echo ""
    echo "Required:"
    echo "  --action <start|stop>     Action to perform (start=scale up, stop=scale down)"
    echo "  --cluster <name>          EKS cluster name"
    echo ""
    echo "Optional:"
    echo "  --account <name>          Account name (default: production)"
    echo "  --account-id <id>         AWS Account ID (default: 123456789012)"
    echo "  --region <region>         AWS region (default: us-west-2)"
    echo "  --min-nodes <num>         Minimum nodes for scale up (default: 1)"
    echo "  --dry-run                 Simulate actions without executing"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --action stop --cluster my-cluster --dry-run"
    echo "  $0 --action start --cluster my-cluster --min-nodes 2 --account production"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --action)
            ACTION="$2"
            shift 2
            ;;
        --cluster)
            CLUSTER="$2"
            shift 2
            ;;
        --account)
            ACCOUNT_NAME="$2"
            shift 2
            ;;
        --account-id)
            ACCOUNT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --min-nodes)
            MIN_NODES="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$ACTION" ]]; then
    echo "Error: --action is required"
    show_usage
    exit 1
fi

if [[ -z "$CLUSTER" ]]; then
    echo "Error: --cluster is required"
    show_usage
    exit 1
fi

if [[ "$ACTION" != "start" && "$ACTION" != "stop" ]]; then
    echo "Error: --action must be 'start' or 'stop'"
    show_usage
    exit 1
fi

# Show configuration
echo "================================="
echo "EKS Scheduler - Static Config"
echo "================================="
echo "Action:      $ACTION"
echo "Cluster:     $CLUSTER"
echo "Account:     $ACCOUNT_NAME ($ACCOUNT_ID)"
echo "Region:      $REGION"
echo "Min Nodes:   $MIN_NODES"
echo "Dry Run:     $([ -n "$DRY_RUN" ] && echo "YES" || echo "NO")"
echo "================================="

# Navigate to source directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/src"

# Run the EKS scheduler with static configuration
python3 main.py \
    --action "$ACTION" \
    --cluster "$CLUSTER" \
    --account "$ACCOUNT_NAME" \
    --account-id "$ACCOUNT_ID" \
    --region "$REGION" \
    --min-nodes "$MIN_NODES" \
    --skip-config \
    $DRY_RUN

echo ""
echo "EKS Scheduler completed!" 