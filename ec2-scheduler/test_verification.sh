#!/bin/bash

# Test script to demonstrate different verification levels
# This script shows the enhanced verification functionality

echo "=== Testing EC2 Scheduler Enhanced Verification ==="
echo ""

echo "1. DRY RUN - Show what would be affected"
echo "Command: python3 main.py --action stop --target ec2 --dry-run"
echo ""
python3 src/main.py --action stop --target ec2 --dry-run --region ap-southeast-2
echo ""

echo "2. BASIC VERIFICATION - State checks only"  
echo "Command: python3 main.py --action start --verify --status-checks state"
echo "Note: This verifies only that instances reach the expected state (running/stopped)"
echo ""

echo "3. SYSTEM VERIFICATION - State + System status checks"
echo "Command: python3 main.py --action start --verify --status-checks system"  
echo "Note: This verifies state + AWS system status checks (for running instances)"
echo ""

echo "4. FULL VERIFICATION - State + System + Instance + Reachability"
echo "Command: python3 main.py --action start --verify --status-checks full"
echo "Note: This verifies all AWS status checks including reachability"
echo ""

echo "=== Verification Levels Explained ==="
echo ""
echo "- state: Only checks instance state (running/stopped)"
echo "- system: Checks state + AWS system status (hypervisor-level checks)" 
echo "- full: Checks state + system + instance status + network reachability"
echo ""
echo "Notes:"
echo "- System and full checks only apply to running instances"
echo "- Stopped instances skip system/instance status checks"
echo "- Use --verify flag to enable verification after operations"
echo "- Verification results are included in reports and artifacts"
echo ""

echo "Test completed. Check the reports/ directory for detailed output files."