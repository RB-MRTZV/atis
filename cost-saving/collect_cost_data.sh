#!/bin/bash
# AWS Cost Data Collection Wrapper Script
# This script handles both the boto3 and AWS CLI versions of the data collector

set -e  # Exit on any error

# Default values
ENVIRONMENT="dev"
REGION="ap-southeast-2"
COST_DAYS="30"
PROFILE=""
USE_CLI_VERSION="false"

# Function to show usage
show_usage() {
    echo "AWS Cost Data Collection Wrapper"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --environment ENV     Environment type: dev or prod (default: dev)"
    echo "  --region REGION       AWS region (default: us-east-1)"
    echo "  --profile PROFILE     AWS profile name"
    echo "  --cost-days DAYS      Number of days back to analyze costs (default: 30)"
    echo "  --use-cli             Force use of AWS CLI version (bypass boto3)"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --environment dev --cost-days 30"
    echo "  $0 --profile prod-profile --environment prod --cost-days 60"
    echo "  $0 --use-cli --environment dev"
    echo ""
}

# Parse command line arguments
while [ $# -gt 0 ]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --cost-days)
            COST_DAYS="$2"
            shift 2
            ;;
        --use-cli)
            USE_CLI_VERSION="true"
            shift
            ;;
        --help|-h)
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

# Validate environment
if [ "$ENVIRONMENT" != "dev" ] && [ "$ENVIRONMENT" != "prod" ]; then
    echo "Error: Environment must be 'dev' or 'prod'"
    exit 1
fi

# Determine Python command
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python not found. Please install Python 3."
    exit 1
fi

echo "AWS Cost Data Collector"
echo "======================"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo "Cost Days: $COST_DAYS"
if [ -n "$PROFILE" ]; then
    echo "Profile: $PROFILE"
fi
echo "Python: $PYTHON_CMD"
echo ""

# Build command arguments
CMD_ARGS="--environment $ENVIRONMENT --region $REGION --cost-days $COST_DAYS"
if [ -n "$PROFILE" ]; then
    CMD_ARGS="$CMD_ARGS --profile $PROFILE"
fi

# Determine which script to use
if [ "$USE_CLI_VERSION" = "true" ]; then
    echo "Using AWS CLI version (forced)..."
    SCRIPT_PATH="scripts/aws_cost_data_collector_cli.py"
else
    echo "Attempting to use boto3 version first..."
    SCRIPT_PATH="scripts/aws_cost_data_collector.py"
    
    # Try boto3 version first, fallback to CLI version if it fails
    if ! $PYTHON_CMD $SCRIPT_PATH $CMD_ARGS 2>/dev/null; then
        echo ""
        echo "boto3 version failed, falling back to AWS CLI version..."
        echo "This usually happens due to boto3 version compatibility issues."
        echo ""
        SCRIPT_PATH="scripts/aws_cost_data_collector_cli.py"
    else
        echo "boto3 version completed successfully!"
        exit 0
    fi
fi

# Run the selected script
echo "Running: $PYTHON_CMD $SCRIPT_PATH $CMD_ARGS"
echo ""

if $PYTHON_CMD $SCRIPT_PATH $CMD_ARGS; then
    echo ""
    echo "✅ AWS cost data collection completed successfully!"
    echo "Check the 'output' directory for the generated report."
else
    echo ""
    echo "❌ AWS cost data collection failed!"
    echo ""
    echo "Troubleshooting tips:"
    echo "1. Ensure AWS CLI is installed and configured"
    echo "2. Check that your AWS credentials have the required permissions"
    echo "3. Verify network connectivity to AWS services"
    echo "4. Check the AWS region is correct and accessible"
    exit 1
fi
