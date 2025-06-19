#!/usr/bin/env python3
"""
AWS Cost Analysis and Optimization Recommendations

This script analyzes collected AWS cost data and generates actionable recommendations.
"""

import json
import glob
import sys
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CostAnalyzer:
    def __init__(self, data_file=None):
        """Initialize cost analyzer with data file or directory."""
        self.data_files = []
        
        if data_file:
            self.data_files = [data_file]
        else:
            # Find all cost data files
            self.data_files = glob.glob('output/aws_cost_data_*.json')
        
        if not self.data_files:
            raise ValueError("No cost data files found. Run data collection first.")
        
        logger.info(f"Found {len(self.data_files)} cost data files to analyze")

    def load_cost_data(self):
        """Load and combine all cost data files."""
        combined_data = {
            'accounts': {},
            'total_monthly_cost': 0,
            'service_costs': {},
            'recommendations': []
        }
        
        for file_path in self.data_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                account_id = data.get('account_id', 'unknown')
                environment = data.get('environment', 'unknown')
                
                combined_data['accounts'][f"{account_id}_{environment}"] = data
                
                # Aggregate cost data
                cost_analysis = data.get('cost_analysis', {})
                service_totals = cost_analysis.get('service_totals', {})
                
                for service, amount in service_totals.items():
                    if service not in combined_data['service_costs']:
                        combined_data['service_costs'][service] = 0
                    combined_data['service_costs'][service] += amount
                    combined_data['total_monthly_cost'] += amount
                
            except Exception as e:
                logger.warning(f"Failed to load {file_path}: {e}")
        
        return combined_data

    def analyze_storage_costs(self, account_data):
        """Analyze storage-related costs and generate recommendations."""
        recommendations = []
        cost_analysis = account_data.get('cost_analysis', {})
        storage_data = account_data.get('storage', {})
        
        # S3 Analysis
        s3_cost = cost_analysis.get('service_totals', {}).get('Amazon Simple Storage Service', 0)
        s3_buckets = storage_data.get('s3_buckets', [])
        
        if s3_cost > 10:  # More than $10/month
            recommendations.append({
                'service': 'S3',
                'type': 'cost_optimization',
                'priority': 'high' if s3_cost > 100 else 'medium',
                'current_cost': s3_cost,
                'recommendation': 'Implement S3 lifecycle policies for automatic tiering',
                'potential_savings': f"${s3_cost * 0.3:.2f}/month (estimated 30% reduction)",
                'implementation': [
                    'Review object access patterns using S3 Storage Class Analysis',
                    'Configure lifecycle rules to move objects to IA after 30 days',
                    'Archive old data to Glacier after 90 days',
                    'Enable S3 Intelligent Tiering for automatic optimization'
                ]
            })
        
        # EBS Analysis
        ebs_cost = cost_analysis.get('service_totals', {}).get('Amazon Elastic Block Store', 0)
        ebs_volumes = storage_data.get('ebs_volumes', [])
        unattached_volumes = [v for v in ebs_volumes if v.get('attachments', 0) == 0]
        
        if unattached_volumes:
            estimated_waste = len(unattached_volumes) * 8  # Assume $8/month per unattached volume
            recommendations.append({
                'service': 'EBS',
                'type': 'resource_cleanup',
                'priority': 'high',
                'current_cost': ebs_cost,
                'recommendation': f'Delete {len(unattached_volumes)} unattached EBS volumes',
                'potential_savings': f"${estimated_waste:.2f}/month",
                'implementation': [
                    'Review unattached volumes for business need',
                    'Create snapshots of important volumes before deletion',
                    'Delete unattached volumes using AWS Console or CLI'
                ]
            })
        
        # EFS Analysis
        efs_cost = cost_analysis.get('service_totals', {}).get('Amazon Elastic File System', 0)
        efs_filesystems = storage_data.get('efs_filesystems', [])
        
        if efs_cost > 20:  # More than $20/month
            recommendations.append({
                'service': 'EFS',
                'type': 'cost_optimization',
                'priority': 'medium',
                'current_cost': efs_cost,
                'recommendation': 'Enable EFS Intelligent Tiering',
                'potential_savings': f"${efs_cost * 0.4:.2f}/month (estimated 40% reduction)",
                'implementation': [
                    'Enable Intelligent Tiering on existing file systems',
                    'Monitor file access patterns',
                    'Consider provisioned throughput vs burst mode'
                ]
            })
        
        return recommendations

    def analyze_compute_costs(self, account_data):
        """Analyze compute-related costs and generate recommendations."""
        recommendations = []
        cost_analysis = account_data.get('cost_analysis', {})
        compute_data = account_data.get('compute', {})
        
        # EC2 Analysis
        ec2_cost = cost_analysis.get('service_totals', {}).get('Amazon Elastic Compute Cloud - Compute', 0)
        ec2_instances = compute_data.get('ec2_instances', [])
        running_instances = [i for i in ec2_instances if i.get('state') == 'running']
        
        if ec2_cost > 50:  # More than $50/month
            # Check for rightsizing opportunities
            rightsizing_recs = cost_analysis.get('rightsizing_recommendations', [])
            if rightsizing_recs:
                total_potential_savings = sum(
                    float(rec.get('modify_recommendation', {}).get('EstimatedMonthlySavings', {}).get('Amount', 0))
                    for rec in rightsizing_recs
                )
                
                recommendations.append({
                    'service': 'EC2',
                    'type': 'rightsizing',
                    'priority': 'high',
                    'current_cost': ec2_cost,
                    'recommendation': f'Rightsize {len(rightsizing_recs)} EC2 instances based on utilization',
                    'potential_savings': f"${total_potential_savings:.2f}/month",
                    'implementation': [
                        'Review CloudWatch metrics for CPU and memory utilization',
                        'Test performance with smaller instance types in dev environment',
                        'Implement gradual rightsizing with monitoring'
                    ]
                })
            
            # Reserved Instance recommendations
            ri_recs = cost_analysis.get('reserved_instance_recommendations', [])
            if ri_recs and len(running_instances) >= 3:
                recommendations.append({
                    'service': 'EC2',
                    'type': 'reserved_instances',
                    'priority': 'medium',
                    'current_cost': ec2_cost,
                    'recommendation': 'Purchase Reserved Instances for stable workloads',
                    'potential_savings': f"${ec2_cost * 0.3:.2f}/month (estimated 30% reduction)",
                    'implementation': [
                        'Analyze instance usage patterns over 60+ days',
                        'Purchase 1-year term Reserved Instances for predictable workloads',
                        'Consider Savings Plans for flexible compute usage'
                    ]
                })
        
        # Lambda Analysis
        lambda_cost = cost_analysis.get('service_totals', {}).get('AWS Lambda', 0)
        lambda_functions = compute_data.get('lambda_functions', [])
        
        if lambda_cost > 10:  # More than $10/month
            high_memory_functions = [f for f in lambda_functions if f.get('memory_size', 0) > 1024]
            if high_memory_functions:
                recommendations.append({
                    'service': 'Lambda',
                    'type': 'optimization',
                    'priority': 'medium',
                    'current_cost': lambda_cost,
                    'recommendation': f'Optimize memory allocation for {len(high_memory_functions)} Lambda functions',
                    'potential_savings': f"${lambda_cost * 0.2:.2f}/month (estimated 20% reduction)",
                    'implementation': [
                        'Use AWS Lambda Power Tuning tool',
                        'Test functions with different memory configurations',
                        'Monitor execution duration and memory usage'
                    ]
                })
        
        # RDS Analysis
        rds_cost = cost_analysis.get('service_totals', {}).get('Amazon RDS Service', 0)
        rds_instances = compute_data.get('rds_instances', [])
        
        if rds_cost > 30:  # More than $30/month
            multi_az_instances = [r for r in rds_instances if r.get('multi_az')]
            if multi_az_instances and account_data.get('environment') == 'dev':
                estimated_savings = len(multi_az_instances) * 50  # Assume $50 savings per instance
                recommendations.append({
                    'service': 'RDS',
                    'type': 'environment_optimization',
                    'priority': 'high',
                    'current_cost': rds_cost,
                    'recommendation': f'Disable Multi-AZ for {len(multi_az_instances)} RDS instances in dev environment',
                    'potential_savings': f"${estimated_savings:.2f}/month",
                    'implementation': [
                        'Modify RDS instances to single-AZ deployment',
                        'Schedule automated backups appropriately',
                        'Consider using RDS snapshots for dev data refresh'
                    ]
                })
        
        return recommendations

    def analyze_log_costs(self, account_data):
        """Analyze CloudWatch Logs costs and generate recommendations."""
        recommendations = []
        cost_analysis = account_data.get('cost_analysis', {})
        logs_data = account_data.get('logs', {})
        
        logs_cost = cost_analysis.get('service_totals', {}).get('Amazon CloudWatch', 0)
        log_groups = logs_data.get('log_groups', [])
        
        if logs_cost > 20:  # More than $20/month
            # Check for log groups with no retention or very long retention
            long_retention_groups = [
                lg for lg in log_groups 
                if lg.get('retention_in_days') == 'Never Expire' or 
                (isinstance(lg.get('retention_in_days'), int) and lg.get('retention_in_days') > 365)
            ]
            
            if long_retention_groups:
                recommendations.append({
                    'service': 'CloudWatch Logs',
                    'type': 'retention_optimization',
                    'priority': 'high',
                    'current_cost': logs_cost,
                    'recommendation': f'Optimize retention for {len(long_retention_groups)} log groups',
                    'potential_savings': f"${logs_cost * 0.5:.2f}/month (estimated 50% reduction)",
                    'implementation': [
                        'Set 30-day retention for debug/development logs',
                        'Set 90-day retention for application logs',
                        'Set 1-year retention for audit logs',
                        'Export important logs to S3 for long-term archival'
                    ]
                })
            
            # Check for high-volume log groups
            high_volume_groups = [
                lg for lg in log_groups 
                if lg.get('stored_bytes', 0) > 1073741824  # 1GB
            ]
            
            if high_volume_groups:
                recommendations.append({
                    'service': 'CloudWatch Logs',
                    'type': 'volume_optimization',
                    'priority': 'medium',
                    'current_cost': logs_cost,
                    'recommendation': f'Reduce log volume for {len(high_volume_groups)} high-volume log groups',
                    'potential_savings': f"${logs_cost * 0.3:.2f}/month (estimated 30% reduction)",
                    'implementation': [
                        'Implement log filtering to reduce noise',
                        'Use log sampling for debug information',
                        'Review log levels in production applications',
                        'Consider structured logging for better analysis'
                    ]
                })
        
        return recommendations

    def analyze_network_costs(self, account_data):
        """Analyze network-related costs and generate recommendations."""
        recommendations = []
        cost_analysis = account_data.get('cost_analysis', {})
        network_data = account_data.get('network', {})
        
        vpc_cost = cost_analysis.get('service_totals', {}).get('Amazon VPC', 0)
        nat_gateways = network_data.get('nat_gateways', [])
        
        if vpc_cost > 45:  # More than $45/month (typical NAT Gateway cost)
            active_nat_gateways = [ng for ng in nat_gateways if ng.get('state') == 'available']
            
            if len(active_nat_gateways) > 1:
                recommendations.append({
                    'service': 'VPC/NAT Gateway',
                    'type': 'architecture_optimization',
                    'priority': 'high',
                    'current_cost': vpc_cost,
                    'recommendation': f'Optimize {len(active_nat_gateways)} NAT Gateways',
                    'potential_savings': f"${45 * (len(active_nat_gateways) - 1):.2f}/month",
                    'implementation': [
                        'Consolidate NAT Gateways where possible',
                        'Use VPC endpoints for AWS service communication',
                        'Consider NAT instances for dev environments',
                        'Review data transfer patterns between AZs'
                    ]
                })
        
        return recommendations

    def analyze_macie_costs(self, account_data):
        """Analyze Amazon Macie costs and generate recommendations."""
        recommendations = []
        cost_analysis = account_data.get('cost_analysis', {})
        macie_data = account_data.get('macie', {})
        
        macie_cost = cost_analysis.get('service_totals', {}).get('Amazon Macie', 0)
        
        if macie_cost > 5 and macie_data.get('macie_status') == 'ENABLED':
            discovery_jobs = macie_data.get('data_discovery_jobs', [])
            
            recommendations.append({
                'service': 'Amazon Macie',
                'type': 'usage_optimization',
                'priority': 'medium',
                'current_cost': macie_cost,
                'recommendation': 'Optimize Macie data discovery job frequency and scope',
                'potential_savings': f"${macie_cost * 0.4:.2f}/month (estimated 40% reduction)",
                'implementation': [
                    'Schedule discovery jobs during off-peak hours',
                    'Focus scans on high-risk data repositories only',
                    'Reduce job frequency for stable environments',
                    'Use custom data identifiers to improve efficiency',
                    'Review findings regularly to tune sensitivity'
                ]
            })
        
        return recommendations

    def analyze_cost_optimization_hub_data(self, account_data):
        """Analyze Cost Optimization Hub recommendations and integrate them."""
        recommendations = []
        coh_data = account_data.get('cost_optimization_hub', {})
        
        if coh_data.get('enrollment_status') == 'Active':
            coh_recommendations = coh_data.get('recommendations', [])
            coh_summary = coh_data.get('summary', {})
            
            logger.info(f"Processing {len(coh_recommendations)} Cost Optimization Hub recommendations")
            
            # Group recommendations by action type and priority
            grouped_recommendations = {
                'high_priority': [],
                'medium_priority': [],
                'low_priority': []
            }
            
            for coh_rec in coh_recommendations:
                savings = coh_rec.get('estimated_monthly_savings', 0)
                effort = coh_rec.get('implementation_effort', 'Unknown')
                action_type = coh_rec.get('action_type', 'Unknown')
                resource_type = coh_rec.get('resource_type', 'Unknown')
                
                # Determine priority based on savings amount and implementation effort
                if savings > 50 and effort in ['VeryLow', 'Low']:
                    priority = 'high'
                elif savings > 20 or effort in ['VeryLow', 'Low', 'Medium']:
                    priority = 'medium'
                else:
                    priority = 'low'
                
                # Create standardized recommendation
                recommendation = {
                    'service': f'Cost Optimization Hub - {resource_type}',
                    'type': 'aws_recommendation',
                    'priority': priority,
                    'current_cost': coh_rec.get('current_monthly_cost', 0),
                    'recommendation': f"{action_type}: {coh_rec.get('resource_id', 'Resource')}",
                    'potential_savings': f"${savings:.2f}/month",
                    'source': 'AWS Cost Optimization Hub',
                    'implementation_effort': effort,
                    'rollback_possible': coh_rec.get('rollback_possible', False),
                    'restart_needed': coh_rec.get('restart_needed', False),
                    'recommendation_id': coh_rec.get('recommendation_id', ''),
                    'resource_arn': coh_rec.get('resource_arn', ''),
                    'last_refresh': coh_rec.get('last_refresh_timestamp', ''),
                    'savings_percentage': coh_rec.get('details', {}).get('estimated_savings_percentage', 0),
                    'implementation': self._get_coh_implementation_steps(action_type, resource_type, effort)
                }
                
                grouped_recommendations[f'{priority}_priority'].append(recommendation)
                recommendations.append(recommendation)
            
            # Add summary recommendation if there are multiple COH recommendations
            if len(coh_recommendations) > 0:
                total_coh_savings = coh_summary.get('total_estimated_monthly_savings', 0)
                high_impact_count = coh_summary.get('high_impact_recommendations', 0)
                
                summary_recommendation = {
                    'service': 'Cost Optimization Hub - Summary',
                    'type': 'hub_summary',
                    'priority': 'high' if total_coh_savings > 100 else 'medium',
                    'current_cost': 0,
                    'recommendation': f'Implement {len(coh_recommendations)} AWS-identified optimizations ({high_impact_count} high-impact)',
                    'potential_savings': f"${total_coh_savings:.2f}/month",
                    'source': 'AWS Cost Optimization Hub',
                    'implementation': [
                        f'Review {len(grouped_recommendations["high_priority"])} high-priority recommendations first',
                        f'Focus on {coh_summary.get("recommendations_by_effort", {}).get("VeryLow", 0) + coh_summary.get("recommendations_by_effort", {}).get("Low", 0)} low-effort optimizations',
                        'Use AWS Console Cost Optimization Hub for detailed guidance',
                        'Implement recommendations with rollback capability first',
                        'Monitor cost impact after each implementation'
                    ],
                    'coh_breakdown': {
                        'by_action_type': coh_summary.get('recommendations_by_type', {}),
                        'by_effort': coh_summary.get('recommendations_by_effort', {}),
                        'high_impact_count': high_impact_count
                    }
                }
                
                recommendations.insert(0, summary_recommendation)
        
        elif coh_data.get('enrollment_status') == 'access_denied':
            recommendations.append({
                'service': 'Cost Optimization Hub',
                'type': 'enrollment',
                'priority': 'medium',
                'current_cost': 0,
                'recommendation': 'Enable Cost Optimization Hub for AWS-generated recommendations',
                'potential_savings': 'Variable - typically 10-20% additional savings',
                'implementation': [
                    'Contact AWS account team to enable Cost Optimization Hub',
                    'Review and accept service terms',
                    'Wait 24-48 hours for initial recommendations',
                    'Integrate recommendations into regular cost review process'
                ]
            })
        
        return recommendations
    
    def _get_coh_implementation_steps(self, action_type, resource_type, effort):
        """Get implementation steps based on Cost Optimization Hub recommendation type."""
        steps = []
        
        if action_type == 'Rightsize':
            steps = [
                'Review current resource utilization metrics',
                'Test recommended instance size in non-production environment',
                'Schedule maintenance window for rightsizing',
                'Monitor performance after implementation',
                'Rollback if performance issues occur'
            ]
        elif action_type == 'Stop':
            steps = [
                'Verify resource is not in active use',
                'Check for any dependent resources or services',
                'Create backup/snapshot if needed',
                'Stop resource during maintenance window',
                'Monitor for any impact on applications'
            ]
        elif action_type == 'PurchaseReservedInstances':
            steps = [
                'Analyze usage patterns over past 60 days',
                'Confirm instance family and size stability',
                'Purchase Reserved Instances with appropriate term',
                'Monitor utilization to ensure optimal coverage'
            ]
        elif action_type == 'PurchaseSavingsPlans':
            steps = [
                'Review compute usage across EC2, Fargate, and Lambda',
                'Calculate optimal commitment amount',
                'Purchase Savings Plan with flexible terms',
                'Monitor coverage and utilization regularly'
            ]
        elif action_type == 'Upgrade':
            steps = [
                'Review upgrade requirements and compatibility',
                'Test upgrade in development environment',
                'Plan upgrade during maintenance window',
                'Verify performance improvements post-upgrade'
            ]
        else:
            steps = [
                'Review AWS Cost Optimization Hub recommendation details',
                'Test recommendation in non-production environment',
                'Implement during scheduled maintenance window',
                'Monitor cost and performance impact'
            ]
        
        # Add effort-specific guidance
        if effort == 'VeryLow':
            steps.insert(0, 'Quick implementation - minimal risk and effort required')
        elif effort == 'Low':
            steps.insert(0, 'Low effort implementation - can be completed within hours')
        elif effort == 'Medium':
            steps.insert(0, 'Medium effort implementation - requires planning and testing')
        elif effort == 'High':
            steps.insert(0, 'High effort implementation - requires significant planning and resources')
        
        return steps

    def generate_comprehensive_analysis(self):
        """Generate comprehensive cost analysis and recommendations."""
        logger.info("Starting comprehensive cost analysis...")
        
        combined_data = self.load_cost_data()
        all_recommendations = []
        
        # Analyze each account
        for account_key, account_data in combined_data['accounts'].items():
            logger.info(f"Analyzing {account_key}...")
            
            # Collect recommendations from all analysis functions
            account_recommendations = []
            account_recommendations.extend(self.analyze_storage_costs(account_data))
            account_recommendations.extend(self.analyze_compute_costs(account_data))
            account_recommendations.extend(self.analyze_log_costs(account_data))
            account_recommendations.extend(self.analyze_network_costs(account_data))
            account_recommendations.extend(self.analyze_macie_costs(account_data))
            account_recommendations.extend(self.analyze_cost_optimization_hub_data(account_data))
            
            # Add account context to recommendations
            for rec in account_recommendations:
                rec['account'] = account_key
                rec['environment'] = account_data.get('environment', 'unknown')
            
            all_recommendations.extend(account_recommendations)
        
        # Sort recommendations by priority and potential savings
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        all_recommendations.sort(
            key=lambda x: (
                priority_order.get(x.get('priority', 'low'), 1),
                float(x.get('potential_savings', '$0/month').replace('$', '').replace('/month', '').split()[0])
            ),
            reverse=True
        )
        
        # Generate summary
        total_potential_savings = sum(
            float(rec.get('potential_savings', '$0/month').replace('$', '').replace('/month', '').split()[0])
            for rec in all_recommendations
        )
        
        analysis_report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_monthly_cost': combined_data['total_monthly_cost'],
            'total_potential_savings': total_potential_savings,
            'savings_percentage': (total_potential_savings / combined_data['total_monthly_cost'] * 100) if combined_data['total_monthly_cost'] > 0 else 0,
            'accounts_analyzed': len(combined_data['accounts']),
            'recommendations_count': len(all_recommendations),
            'service_costs': combined_data['service_costs'],
            'recommendations': all_recommendations,
            'implementation_priority': {
                'immediate': [r for r in all_recommendations if r.get('priority') == 'high'],
                'short_term': [r for r in all_recommendations if r.get('priority') == 'medium'],
                'long_term': [r for r in all_recommendations if r.get('priority') == 'low']
            }
        }
        
        return analysis_report

    def save_analysis_report(self, analysis_report, output_file=None):
        """Save analysis report to file."""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'output/cost_analysis_detailed_{timestamp}.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_report, f, indent=2, default=str)
        
        logger.info(f"Detailed cost analysis saved to: {output_file}")
        return output_file

def main():
    parser = argparse.ArgumentParser(description='AWS Cost Analysis and Optimization')
    parser.add_argument('--data-file', help='Specific cost data file to analyze')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    try:
        analyzer = CostAnalyzer(data_file=args.data_file)
        report = analyzer.generate_comprehensive_analysis()
        output_file = analyzer.save_analysis_report(report, args.output)
        
        # Print summary
        print(f"\n=== AWS Cost Analysis Summary ===")
        print(f"Total Monthly Cost: ${report['total_monthly_cost']:.2f}")
        print(f"Potential Monthly Savings: ${report['total_potential_savings']:.2f}")
        print(f"Potential Savings Percentage: {report['savings_percentage']:.1f}%")
        print(f"Recommendations Generated: {report['recommendations_count']}")
        print(f"Detailed report saved to: {output_file}")
        
        # Show top 3 recommendations
        print(f"\n=== Top 3 Recommendations ===")
        for i, rec in enumerate(report['recommendations'][:3], 1):
            print(f"{i}. {rec['service']}: {rec['recommendation']}")
            print(f"   Potential Savings: {rec['potential_savings']}")
            print(f"   Priority: {rec['priority'].upper()}")
            print()
        
    except Exception as e:
        logger.error(f"Cost analysis failed: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())