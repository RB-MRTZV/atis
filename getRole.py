#!/usr/bin/env python3
“””
IAM Role Permissions Analyzer
Retrieves and displays all permissions from inline policies attached to an IAM role.
“””

import argparse
import json
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime
from tabulate import tabulate
import sys

def parse_arguments():
“”“Parse command line arguments.”””
parser = argparse.ArgumentParser(
description=‘Analyze IAM role permissions from inline policies’
)
parser.add_argument(
‘–role-name’,
type=str,
default=‘ConsumerAccountIaC’,
help=‘IAM role name to analyze (default: ConsumerAccountIaC)’
)
parser.add_argument(
‘–output-prefix’,
type=str,
default=‘iam_permissions’,
help=‘Prefix for output files (default: iam_permissions)’
)
parser.add_argument(
‘–region’,
type=str,
default=‘us-east-1’,
help=‘AWS region (default: us-east-1)’
)
return parser.parse_args()

def get_iam_client(region):
“”“Create and return IAM client.”””
try:
return boto3.client(‘iam’, region_name=region)
except Exception as e:
print(f”Error creating IAM client: {e}”)
sys.exit(1)

def verify_role_exists(iam_client, role_name):
“”“Verify that the IAM role exists.”””
try:
iam_client.get_role(RoleName=role_name)
return True
except ClientError as e:
if e.response[‘Error’][‘Code’] == ‘NoSuchEntity’:
print(f”Error: Role ‘{role_name}’ not found”)
return False
else:
print(f”Error verifying role: {e}”)
return False

def get_inline_policies(iam_client, role_name):
“”“Get all inline policies for a role.”””
policies = []
try:
# List all inline policies
paginator = iam_client.get_paginator(‘list_role_policies’)
for response in paginator.paginate(RoleName=role_name):
for policy_name in response.get(‘PolicyNames’, []):
# Get the policy document
policy_response = iam_client.get_role_policy(
RoleName=role_name,
PolicyName=policy_name
)

```
            policy_doc = policy_response['PolicyDocument']
            policies.append({
                'PolicyName': policy_name,
                'PolicyDocument': policy_doc
            })
            
except ClientError as e:
    print(f"Error retrieving policies: {e}")
    sys.exit(1)

return policies
```

def parse_policy_statements(policy_document):
“”“Parse policy statements to extract permissions and conditions.”””
permissions = []

```
statements = policy_document.get('Statement', [])

for idx, statement in enumerate(statements):
    effect = statement.get('Effect', 'Unknown')
    actions = statement.get('Action', [])
    resources = statement.get('Resource', [])
    conditions = statement.get('Condition', {})
    
    # Ensure actions and resources are lists
    if isinstance(actions, str):
        actions = [actions]
    if isinstance(resources, str):
        resources = [resources]
    
    # Parse each action
    for action in actions:
        permission = {
            'StatementId': statement.get('Sid', f'Statement{idx+1}'),
            'Effect': effect,
            'Action': action,
            'Resources': resources,
            'Conditions': conditions
        }
        permissions.append(permission)

return permissions
```

def format_conditions(conditions):
“”“Format conditions for readable display.”””
if not conditions:
return “None”

```
formatted = []
for operator, values in conditions.items():
    for key, value in values.items():
        if isinstance(value, list):
            value_str = ', '.join(value)
        else:
            value_str = str(value)
        formatted.append(f"{operator}:{key}={value_str}")

return '; '.join(formatted)
```

def format_resources(resources):
“”“Format resources for readable display.”””
if not resources:
return “None”
return ’, ’.join(resources) if isinstance(resources, list) else str(resources)

def create_table_output(role_name, all_permissions):
“”“Create a formatted table output.”””
table_data = []

```
for policy_name, permissions in all_permissions.items():
    for perm in permissions:
        table_data.append([
            policy_name,
            perm['StatementId'],
            perm['Effect'],
            perm['Action'],
            format_resources(perm['Resources']),
            format_conditions(perm['Conditions'])
        ])

headers = ['Policy Name', 'Statement ID', 'Effect', 'Action', 'Resources', 'Conditions']

return tabulate(table_data, headers=headers, tablefmt='grid', maxcolwidths=50)
```

def save_outputs(role_name, all_permissions, output_prefix):
“”“Save outputs to both text and JSON files.”””
timestamp = datetime.now().strftime(’%Y%m%d_%H%M%S’)

```
# Save JSON output
json_filename = f"{output_prefix}_{timestamp}.json"
json_output = {
    'RoleName': role_name,
    'Timestamp': timestamp,
    'Policies': all_permissions
}

with open(json_filename, 'w') as f:
    json.dump(json_output, f, indent=2, default=str)
print(f"JSON output saved to: {json_filename}")

# Save text table output
txt_filename = f"{output_prefix}_{timestamp}.txt"
table_output = create_table_output(role_name, all_permissions)

with open(txt_filename, 'w') as f:
    f.write(f"IAM Role Permissions Analysis\n")
    f.write(f"{'=' * 80}\n")
    f.write(f"Role Name: {role_name}\n")
    f.write(f"Analysis Date: {timestamp}\n")
    f.write(f"{'=' * 80}\n\n")
    f.write(table_output)
    f.write(f"\n\nTotal Policies: {len(all_permissions)}\n")
    
    total_permissions = sum(len(perms) for perms in all_permissions.values())
    f.write(f"Total Permission Entries: {total_permissions}\n")

print(f"Text output saved to: {txt_filename}")
```

def main():
“”“Main function to orchestrate the analysis.”””
args = parse_arguments()

```
print(f"Analyzing IAM role: {args.role_name}")

# Create IAM client
iam_client = get_iam_client(args.region)

# Verify role exists
if not verify_role_exists(iam_client, args.role_name):
    sys.exit(1)

# Get inline policies
print("Retrieving inline policies...")
policies = get_inline_policies(iam_client, args.role_name)

if not policies:
    print(f"No inline policies found for role '{args.role_name}'")
    sys.exit(0)

print(f"Found {len(policies)} inline policies")

# Parse all policies
all_permissions = {}
for policy in policies:
    policy_name = policy['PolicyName']
    permissions = parse_policy_statements(policy['PolicyDocument'])
    all_permissions[policy_name] = permissions

# Save outputs
save_outputs(args.role_name, all_permissions, args.output_prefix)

print("\nAnalysis complete!")
```

if **name** == ‘**main**’:
main()