#!/usr/bin/env python3

import boto3
import json
import yaml
from kubernetes import client, config
from datetime import datetime

def setup_clients():
    """Initialize AWS and Kubernetes clients"""
    # AWS clients
    eks = boto3.client('eks')
    ec2 = boto3.client('ec2')
    iam = boto3.client('iam')
    
    # Kubernetes client (assumes kubeconfig is configured)
    config.load_kube_config()
    k8s_core = client.CoreV1Api()
    k8s_apps = client.AppsV1Api()
    k8s_rbac = client.RbacAuthorizationV1Api()
    k8s_custom = client.CustomObjectsApi()
    
    return eks, ec2, iam, k8s_core, k8s_apps, k8s_rbac, k8s_custom

def get_cluster_config(eks, cluster_name):
    """Get EKS cluster configuration"""
    print(f"Gathering cluster config for: {cluster_name}")
    
    cluster = eks.describe_cluster(name=cluster_name)['cluster']
    
    # Get add-ons
    addons = eks.list_addons(clusterName=cluster_name)['addons']
    addon_details = []
    for addon in addons:
        details = eks.describe_addon(clusterName=cluster_name, addonName=addon)['addon']
        addon_details.append({
            'name': addon,
            'version': details['addonVersion'],
            'serviceAccountRoleArn': details.get('serviceAccountRoleArn'),
            'configurationValues': details.get('configurationValues')
        })
    
    return {
        'name': cluster['name'],
        'version': cluster['version'],
        'roleArn': cluster['roleArn'],
        'vpcConfig': cluster['resourcesVpcConfig'],
        'kubernetesNetworkConfig': cluster.get('kubernetesNetworkConfig'),
        'logging': cluster.get('logging'),
        'identity': cluster.get('identity'),
        'encryptionConfig': cluster.get('encryptionConfig'),
        'addons': addon_details
    }

def get_nodegroups_config(eks, cluster_name):
    """Get node groups configuration"""
    print("Gathering node groups config...")
    
    nodegroups = eks.list_nodegroups(clusterName=cluster_name)['nodegroups']
    nodegroup_configs = []
    
    for ng in nodegroups:
        ng_detail = eks.describe_nodegroup(clusterName=cluster_name, nodegroupName=ng)['nodegroup']
        nodegroup_configs.append({
            'nodegroupName': ng_detail['nodegroupName'],
            'scalingConfig': ng_detail.get('scalingConfig'),
            'instanceTypes': ng_detail.get('instanceTypes'),
            'amiType': ng_detail.get('amiType'),
            'capacityType': ng_detail.get('capacityType'),
            'diskSize': ng_detail.get('diskSize'),
            'nodeRole': ng_detail.get('nodeRole'),
            'subnets': ng_detail.get('subnets'),
            'remoteAccess': ng_detail.get('remoteAccess'),
            'labels': ng_detail.get('labels'),
            'taints': ng_detail.get('taints'),
            'launchTemplate': ng_detail.get('launchTemplate'),
            'tags': ng_detail.get('tags')
        })
    
    return nodegroup_configs

def get_vpc_config(ec2, vpc_id):
    """Get VPC and networking configuration"""
    print(f"Gathering VPC config for: {vpc_id}")
    
    # VPC details
    vpc = ec2.describe_vpcs(VpcIds=[vpc_id])['Vpcs'][0]
    
    # Subnets
    subnets = ec2.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
    
    # Security groups
    security_groups = ec2.describe_security_groups(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['SecurityGroups']
    
    # Route tables
    route_tables = ec2.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['RouteTables']
    
    # Internet gateway
    igws = ec2.describe_internet_gateways(Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])['InternetGateways']
    
    # NAT gateways
    nat_gws = ec2.describe_nat_gateways(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['NatGateways']
    
    return {
        'vpc': {
            'vpcId': vpc['VpcId'],
            'cidrBlock': vpc['CidrBlock'],
            'enableDnsHostnames': vpc.get('EnableDnsHostnames'),
            'enableDnsSupport': vpc.get('EnableDnsSupport'),
            'tags': vpc.get('Tags', [])
        },
        'subnets': [{
            'subnetId': s['SubnetId'],
            'cidrBlock': s['CidrBlock'],
            'availabilityZone': s['AvailabilityZone'],
            'mapPublicIpOnLaunch': s.get('MapPublicIpOnLaunch'),
            'tags': s.get('Tags', [])
        } for s in subnets],
        'securityGroups': [{
            'groupId': sg['GroupId'],
            'groupName': sg['GroupName'],
            'description': sg['Description'],
            'ingressRules': sg['IpPermissions'],
            'egressRules': sg['IpPermissionsEgress'],
            'tags': sg.get('Tags', [])
        } for sg in security_groups],
        'routeTables': [{
            'routeTableId': rt['RouteTableId'],
            'routes': rt['Routes'],
            'associations': rt['Associations'],
            'tags': rt.get('Tags', [])
        } for rt in route_tables],
        'internetGateways': igws,
        'natGateways': nat_gws
    }

def get_iam_roles(iam, role_arns):
    """Get IAM role configurations"""
    print("Gathering IAM roles config...")
    
    roles_config = []
    for role_arn in role_arns:
        role_name = role_arn.split('/')[-1]
        try:
            role = iam.get_role(RoleName=role_name)['Role']
            
            # Get attached policies
            attached_policies = iam.list_attached_role_policies(RoleName=role_name)['AttachedPolicies']
            
            roles_config.append({
                'roleName': role['RoleName'],
                'roleArn': role['Arn'],
                'assumeRolePolicyDocument': role['AssumeRolePolicyDocument'],
                'attachedPolicies': attached_policies,
                'tags': role.get('Tags', [])
            })
        except Exception as e:
            print(f"Could not get role {role_name}: {e}")
    
    return roles_config

def get_k8s_resources(k8s_core, k8s_apps, k8s_rbac, k8s_custom):
    """Get key Kubernetes resources"""
    print("Gathering Kubernetes resources...")
    
    config_data = {}
    
    # Namespaces
    namespaces = k8s_core.list_namespace()
    config_data['namespaces'] = [ns.metadata.name for ns in namespaces.items if not ns.metadata.name.startswith('kube-')]
    
    # Storage classes
    storage_api = client.StorageV1Api()
    storage_classes = storage_api.list_storage_class()
    config_data['storageClasses'] = [{
        'name': sc.metadata.name,
        'provisioner': sc.provisioner,
        'parameters': sc.parameters,
        'allowVolumeExpansion': sc.allow_volume_expansion,
        'reclaimPolicy': sc.reclaim_policy
    } for sc in storage_classes.items]
    
    # ConfigMaps (structure only, no sensitive data)
    configmaps = k8s_core.list_config_map_for_all_namespaces()
    config_data['configMaps'] = [{
        'name': cm.metadata.name,
        'namespace': cm.metadata.namespace,
        'keys': list(cm.data.keys()) if cm.data else []
    } for cm in configmaps.items if not cm.metadata.namespace.startswith('kube-')]
    
    # Services
    services = k8s_core.list_service_for_all_namespaces()
    config_data['services'] = [{
        'name': svc.metadata.name,
        'namespace': svc.metadata.namespace,
        'type': svc.spec.type,
        'ports': [{'port': p.port, 'targetPort': p.target_port, 'protocol': p.protocol} for p in svc.spec.ports] if svc.spec.ports else []
    } for svc in services.items if not svc.metadata.namespace.startswith('kube-')]
    
    # Get CRDs to understand what custom resources exist
    try:
        apiextensions_api = client.ApiextensionsV1Api()
        crds = apiextensions_api.list_custom_resource_definition()
        config_data['customResourceDefinitions'] = [{
            'name': crd.metadata.name,
            'group': crd.spec.group,
            'version': crd.spec.versions[0].name if crd.spec.versions else None,
            'kind': crd.spec.names.kind
        } for crd in crds.items]
    except Exception as e:
        print(f"Could not get CRDs: {e}")
        config_data['customResourceDefinitions'] = []
    
    return config_data

def save_config(config_data, output_dir="."):
    """Save configuration to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save as JSON
    json_filename = f"{output_dir}/eks_config_{timestamp}.json"
    with open(json_filename, 'w') as f:
        json.dump(config_data, f, indent=2, default=str)
    
    # Save as YAML
    yaml_filename = f"{output_dir}/eks_config_{timestamp}.yaml"
    with open(yaml_filename, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)
    
    print(f"Configuration saved to:")
    print(f"  JSON: {json_filename}")
    print(f"  YAML: {yaml_filename}")

def main():
    # Configuration
    CLUSTER_NAME = "your-cluster-name"  # Replace with your cluster name
    
    try:
        # Setup clients
        eks, ec2, iam, k8s_core, k8s_apps, k8s_rbac, k8s_custom = setup_clients()
        
        # Gather all configurations
        config_data = {}
        
        # EKS cluster config
        cluster_config = get_cluster_config(eks, CLUSTER_NAME)
        config_data['cluster'] = cluster_config
        
        # Node groups
        config_data['nodeGroups'] = get_nodegroups_config(eks, CLUSTER_NAME)
        
        # VPC configuration
        vpc_id = cluster_config['vpcConfig']['vpcId']
        config_data['networking'] = get_vpc_config(ec2, vpc_id)
        
        # IAM roles
        role_arns = [cluster_config['roleArn']]
        for ng in config_data['nodeGroups']:
            role_arns.append(ng['nodeRole'])
        config_data['iamRoles'] = get_iam_roles(iam, role_arns)
        
        # Kubernetes resources
        config_data['kubernetesResources'] = get_k8s_resources(k8s_core, k8s_apps, k8s_rbac, k8s_custom)
        
        # Save configuration
        save_config(config_data)
        
        print("\n=== Configuration Discovery Complete ===")
        print(f"Cluster: {CLUSTER_NAME}")
        print(f"Node Groups: {len(config_data['nodeGroups'])}")
        print(f"Namespaces: {len(config_data['kubernetesResources']['namespaces'])}")
        print(f"Custom Resources: {len(config_data['kubernetesResources']['customResourceDefinitions'])}")
        
    except Exception as e:
        print(f"Error during discovery: {e}")
        raise

if __name__ == "__main__":
    main()
