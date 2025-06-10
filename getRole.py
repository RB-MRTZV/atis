#!/usr/bin/env python3
“””
IAM Role Permissions Analyzer
Retrieves and displays all permissions with conditions for a given IAM role
“””

import argparse
import json
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime
from typing import Dict, List, Any, Tuple
import sys

def parse_arguments() -> argparse.Namespace:
“”“Parse command line arguments”””
parser = argparse.ArgumentParser(
description=‘List all permissions with conditions for an IAM role’
)
parser.add_argument(
‘–role-name’,
type=str,
default=‘ConsumerAccountIaC’,
help=‘IAM role name to analyze (default: ConsumerAccountIaC)’
)
parser.add_argument(
‘–output-file’,
type=str,
default=‘iam_role_permissions.txt’,
help=‘Output file name (default: iam_role_permissions.txt)’
)
parser.add_argument(
‘–region’,
type=str,
default=‘us-east-1’,
help=‘AWS region (default: us-east-1)’
)
return parser.parse_args()

def get_iam_client(region: str) -> boto3.client:
“”“Create and return IAM client”””
try:
return boto3.client(‘iam’, region_name=region)
except Exception as e:
print(f”Error creating IAM client: {e}”)
sys.exit(1)

def get_role_details(iam_client: boto3.client, role_name: str) -> Dict[str, Any]:
“”“Get role details including trust policy”””
try:
response = iam_client.get_role(RoleName=role_name)
return response[‘Role’]
except ClientError as e:
if e.response[‘Error’][‘Code’] == ‘NoSuchEntity’:
print(f”Error: Role ‘{role_name}’ not found”)
else:
print(f”Error getting role details: {e}”)
sys.exit(1)

def get_attached_policies(iam_client: boto3.client, role_name: str) -> List[Dict[str, str]]:
“”“Get all managed policies attached to the role”””
policies = []
try:
paginator = iam_client.get_paginator(‘list_attached_role_policies’)
for page in paginator.paginate(RoleName=role_name):
policies.extend(page[‘AttachedPolicies’])
except ClientError as e:
print(f”Error listing attached policies: {e}”)
return policies

def get_inline_policies(iam_client: boto3.client, role_name: str) -> List[str]:
“”“Get all inline policy names for the role”””
policies = []
try:
paginator = iam_client.get_paginator(‘list_role_policies’)
for page in paginator.paginate(RoleName=role_name):
policies.extend(page[‘PolicyNames’])
except ClientError as e:
print(f”Error listing inline policies: {e}”)
return policies

def get_policy_document(iam_client: boto3.client, policy_arn: str) -> Dict[str, Any]:
“”“Get policy document for a managed policy”””
try:
# Get the default version
policy_details = iam_client.get_policy(PolicyArn=policy_arn)
version_id = policy_details[‘Policy’][‘DefaultVersionId’]

```
    # Get the policy document
    response = iam_client.get_policy_version(
        PolicyArn=policy_arn,
        VersionId=version_id
    )
    return json.loads(response['PolicyVersion']['Document'])
except ClientError as e:
    print(f"Error getting policy document for {policy_arn}: {e}")
    return {}
```

def get_inline_policy_document(iam_client: boto3.client, role_name: str, policy_name: str) -> Dict[str, Any]:
“”“Get policy document for an inline policy”””
try:
response = iam_client.get_role_policy(
RoleName=role_name,
PolicyName=policy_name
)
return json.loads(response[‘PolicyDocument’])
except ClientError as e:
print(f”Error getting inline policy {policy_name}: {e}”)
return {}

def parse_statement_permissions(statement: Dict[str, Any]) -> List[Dict[str, Any]]:
“”“Parse a policy statement and extract permissions with conditions”””
permissions = []

```
effect = statement.get('Effect', 'Allow')
actions = statement.get('Action', [])
resources = statement.get('Resource', [])
conditions = statement.get('Condition', {})

# Ensure actions and resources are lists
if isinstance(actions, str):
    actions = [actions]
if isinstance(resources, str):
    resources = [resources]

for action in actions:
    permission = {
        'Effect': effect,
        'Action': action,
        'Resources': resources,
        'Conditions': conditions
    }
    permissions.append(permission)

return permissions
```

def format_conditions(conditions: Dict[str, Any]) -> str:
“”“Format conditions dictionary into readable string”””
if not conditions:
return “None”

```
formatted = []
for operator, values in conditions.items():
    for key, value in values.items():
        if isinstance(value, list):
            value_str = ', '.join(str(v) for v in value)
        else:
            value_str = str(value)
        formatted.append(f"{operator}: {key} = {value_str}")

return '; '.join(formatted)
```

def format_resources(resources: List[str]) -> str:
“”“Format resources list into readable string”””
if not resources:
return “*”

```
# Truncate if too many resources
if len(resources) > 3:
    return f"{', '.join(resources[:3])}, ... ({len(resources)} total)"

return ', '.join(resources)
```

def write_permissions_table(permissions: List[Dict[str, Any]], role_name: str, output_file: str):
“”“Write permissions to a formatted text file”””
with open(output_file, ‘w’) as f:
# Header
f.write(”=” * 120 + “\n”)
f.write(f”IAM Role Permissions Analysis\n”)
f.write(f”Role: {role_name}\n”)
f.write(f”Generated: {datetime.now().strftime(’%Y-%m-%d %H:%M:%S’)}\n”)
f.write(”=” * 120 + “\n\n”)

```
    # Summary
    f.write(f"Total Permissions: {len(permissions)}\n")
    with_conditions = sum(1 for p in permissions if p['Conditions'])
    f.write(f"Permissions with Conditions: {with_conditions}\n")
    f.write(f"Permissions without Conditions: {len(permissions) - with_conditions}\n\n")
    
    # Table header
    f.write("-" * 120 + "\n")
    f.write(f"{'Policy':<30} {'Effect':<8} {'Action':<40} {'Has Conditions':<15}\n")
    f.write("-" * 120 + "\n")
    
    # Group by policy
    for policy_name, policy_permissions in permissions.items():
        for perm in policy_permissions:
            has_conditions = "Yes" if perm['Conditions'] else "No"
            f.write(f"{policy_name:<30} {perm['Effect']:<8} {perm['Action']:<40} {has_conditions:<15}\n")
            
            # Write resources
            resources_str = format_resources(perm['Resources'])
            f.write(f"{'':>30} Resources: {resources_str}\n")
            
            # Write conditions if present
            if perm['Conditions']:
                conditions_str = format_conditions(perm['Conditions'])
                f.write(f"{'':>30} Conditions: {conditions_str}\n")
            
            f.write("\n")
    
    f.write("-" * 120 + "\n")
```

def analyze_role_permissions(role_name: str, region: str = ‘us-east-1’) -> Dict[str, List[Dict[str, Any]]]:
“”“Main function to analyze role permissions”””
iam_client = get_iam_client(region)

```
# Get role details
print(f"Analyzing role: {role_name}")
role_details = get_role_details(iam_client, role_name)

all_permissions = {}

# Process managed policies
print("Getting attached managed policies...")
attached_policies = get_attached_policies(iam_client, role_name)
for policy in attached_policies:
    policy_name = policy['PolicyName']
    policy_arn = policy['PolicyArn']
    print(f"  Processing: {policy_name}")
    
    policy_doc = get_policy_document(iam_client, policy_arn)
    permissions = []
    
    for statement in policy_doc.get('Statement', []):
        permissions.extend(parse_statement_permissions(statement))
    
    all_permissions[f"[Managed] {policy_name}"] = permissions

# Process inline policies
print("Getting inline policies...")
inline_policies = get_inline_policies(iam_client, role_name)
for policy_name in inline_policies:
    print(f"  Processing: {policy_name}")
    
    policy_doc = get_inline_policy_document(iam_client, role_name, policy_name)
    permissions = []
    
    for statement in policy_doc.get('Statement', []):
        permissions.extend(parse_statement_permissions(statement))
    
    all_permissions[f"[Inline] {policy_name}"] = permissions

return all_permissions
```

def main():
“”“Main execution function”””
args = parse_arguments()

```
try:
    # Analyze permissions
    permissions = analyze_role_permissions(args.role_name, args.region)
    
    if not permissions:
        print(f"\nNo policies found for role '{args.role_name}'")
        return
    
    # Write to file
    print(f"\nWriting results to {args.output_file}...")
    write_permissions_table(permissions, args.role_name, args.output_file)
    
    # Summary
    total_perms = sum(len(perms) for perms in permissions.values())
    print(f"\nAnalysis complete!")
    print(f"Total policies analyzed: {len(permissions)}")
    print(f"Total permissions found: {total_perms}")
    print(f"Results written to: {args.output_file}")
    
except KeyboardInterrupt:
    print("\nOperation cancelled by user")
    sys.exit(1)
except Exception as e:
    print(f"\nUnexpected error: {e}")
    sys.exit(1)
```

if **name** == “**main**”:
main()