#!/usr/bin/env python3
import json
import csv
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, results_file='cost_estimation_results.json'):
        self.results = self._load_results(results_file)
    
    def _load_results(self, results_file):
        """Load cost estimation results"""
        try:
            with open(results_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load results: {str(e)}")
            return {}
    
    def generate_csv_report(self, output_file='cost_report.csv'):
        """Generate CSV report with detailed costs"""
        logger.info(f"Generating CSV report: {output_file}")
        
        # Create detailed report
        detailed_data = self.results.get('detailed', [])
        
        if not detailed_data:
            logger.warning("No detailed data found")
            return
        
        # Write detailed CSV
        fieldnames = [
            'service', 'resource_id', 'instance_type', 'environment',
            'hourly_cost', 'daily_cost', 'monthly_cost', 'currency'
        ]
        
        # Add service-specific fields
        ec2_fields = ['type', 'in_asg', 'asg_name']
        rds_fields = ['engine', 'multi_az', 'storage_type']
        eks_fields = ['cluster_name', 'nodegroup_name', 'deployment_count']
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames + ec2_fields + rds_fields + eks_fields)
            writer.writeheader()
            
            for row in detailed_data:
                # Create row with all possible fields
                csv_row = {field: row.get(field, '') for field in fieldnames + ec2_fields + rds_fields + eks_fields}
                writer.writerow(csv_row)
        
        # Generate summary CSV
        summary_file = output_file.replace('.csv', '_summary.csv')
        summary_data = self.results.get('summary', [])
        
        with open(summary_file, 'w', newline='') as csvfile:
            fieldnames = ['service', 'environment', 'resource_count', 'daily_cost', 'monthly_cost', 'currency']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_data)
        
        logger.info(f"CSV reports generated: {output_file}, {summary_file}")
    
    def generate_html_report(self, output_file='cost_report.html'):
        """Generate HTML report with styled tables and charts"""
        logger.info(f"Generating HTML report: {output_file}")
        
        metadata = self.results.get('metadata', {})
        summary_data = self.results.get('summary', [])
        detailed_data = self.results.get('detailed', [])
        
        # Calculate totals by service and environment
        service_totals = {}
        env_totals = {}
        
        for item in summary_data:
            if item['service'] != 'TOTAL':
                service = item['service']
                env = item['environment']
                
                if service not in service_totals:
                    service_totals[service] = 0
                service_totals[service] += item['monthly_cost']
                
                if env not in env_totals:
                    env_totals[env] = 0
                env_totals[env] += item['monthly_cost']
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>AWS Cost Estimation Report</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #232f3e;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .metadata {{
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .card h3 {{
            margin: 0 0 10px 0;
            color: #232f3e;
        }}
        .card .amount {{
            font-size: 28px;
            font-weight: bold;
            color: #ff9900;
        }}
        .card .label {{
            color: #666;
            font-size: 14px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        th {{
            background-color: #232f3e;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .section-title {{
            color: #232f3e;
            margin: 30px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #ff9900;
        }}
        .total-row {{
            font-weight: bold;
            background-color: #f0f0f0;
        }}
        .ec2-managed {{
            color: #1e88e5;
        }}
        .ec2-ephemeral {{
            color: #43a047;
        }}
        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .chart-container {{
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart-container.small {{
            max-width: 350px;
            margin: 0 auto;
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>AWS Cost Estimation Report</h1>
        <p>Account: {metadata.get('account_id', 'N/A')} | Region: {metadata.get('region', 'N/A')}</p>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <div class="metadata">
        <h3>Report Information</h3>
        <p><strong>Scan Time:</strong> {metadata.get('scan_time', 'N/A')}</p>
        <p><strong>Currency:</strong> {metadata.get('currency', 'USD')}</p>
        <p><strong>Pricing Data Updated:</strong> {metadata.get('config_last_updated', 'N/A')}</p>
    </div>
"""
        
        # Add summary cards
        total_monthly = sum(item['monthly_cost'] for item in summary_data if item['service'] == 'TOTAL')
        total_daily = sum(item['daily_cost'] for item in summary_data if item['service'] == 'TOTAL')
        total_resources = sum(item['resource_count'] for item in summary_data if item['service'] == 'TOTAL')
        
        html_content += f"""
    <div class="summary-cards">
        <div class="card">
            <h3>Total Monthly Cost</h3>
            <div class="amount">${total_monthly:,.2f}</div>
            <div class="label">{metadata.get('currency', 'USD')} per month</div>
        </div>
        <div class="card">
            <h3>Total Daily Cost</h3>
            <div class="amount">${total_daily:,.2f}</div>
            <div class="label">{metadata.get('currency', 'USD')} per day</div>
        </div>
        <div class="card">
            <h3>Total Resources</h3>
            <div class="amount">{total_resources}</div>
            <div class="label">Active resources</div>
        </div>
    </div>
"""
        
        # Calculate data for additional charts
        instance_type_costs = {}
        for item in detailed_data:
            inst_type = item['instance_type']
            if inst_type not in instance_type_costs:
                instance_type_costs[inst_type] = 0
            instance_type_costs[inst_type] += item['monthly_cost']
        
        # Sort and get top 10 instance types
        top_instance_types = dict(sorted(instance_type_costs.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Add charts
        html_content += """
    <div class="chart-row">
        <div class="chart-container small">
            <h3>Cost by Service</h3>
            <canvas id="serviceChart"></canvas>
        </div>
        <div class="chart-container">
            <h3>Cost by Environment</h3>
            <canvas id="envChart"></canvas>
        </div>
    </div>
    
    <div class="charts">
        <div class="chart-container">
            <h3>Top 10 Instance Types by Cost</h3>
            <canvas id="instanceChart"></canvas>
        </div>
        <div class="chart-container">
            <h3>Resource Count by Service</h3>
            <canvas id="resourceChart"></canvas>
        </div>
    </div>
"""
        
        # Add summary table
        html_content += """
    <h2 class="section-title">Cost Summary by Service and Environment</h2>
    <table>
        <thead>
            <tr>
                <th>Service</th>
                <th>Environment</th>
                <th>Resource Count</th>
                <th>Daily Cost</th>
                <th>Monthly Cost</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for item in summary_data:
            row_class = 'total-row' if item['service'] == 'TOTAL' else ''
            html_content += f"""
            <tr class="{row_class}">
                <td>{item['service']}</td>
                <td>{item['environment']}</td>
                <td>{item['resource_count']}</td>
                <td>${item['daily_cost']:,.2f}</td>
                <td>${item['monthly_cost']:,.2f}</td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
"""
        
        # Add detailed EC2 table
        ec2_data = [d for d in detailed_data if d['service'] == 'EC2']
        if ec2_data:
            html_content += """
    <h2 class="section-title">EC2 Instance Details</h2>
    <table>
        <thead>
            <tr>
                <th>Instance ID</th>
                <th>Instance Type</th>
                <th>Environment</th>
                <th>Type</th>
                <th>In ASG</th>
                <th>ASG Name</th>
                <th>Daily Cost</th>
                <th>Monthly Cost</th>
            </tr>
        </thead>
        <tbody>
"""
            for item in ec2_data:
                type_class = 'ec2-ephemeral' if item.get('type') == 'Ephemeral' else 'ec2-managed'
                html_content += f"""
            <tr>
                <td>{item['resource_id']}</td>
                <td>{item['instance_type']}</td>
                <td>{item['environment']}</td>
                <td class="{type_class}">{item.get('type', '')}</td>
                <td>{item.get('in_asg', '')}</td>
                <td>{item.get('asg_name', '')}</td>
                <td>${item['daily_cost']:,.2f}</td>
                <td>${item['monthly_cost']:,.2f}</td>
            </tr>
"""
            html_content += """
        </tbody>
    </table>
"""
        
        # Add detailed RDS table
        rds_data = [d for d in detailed_data if d['service'] == 'RDS']
        if rds_data:
            html_content += """
    <h2 class="section-title">RDS Instance Details</h2>
    <table>
        <thead>
            <tr>
                <th>Instance ID</th>
                <th>Instance Class</th>
                <th>Environment</th>
                <th>Engine</th>
                <th>Multi-AZ</th>
                <th>Storage Type</th>
                <th>Daily Cost</th>
                <th>Monthly Cost</th>
            </tr>
        </thead>
        <tbody>
"""
            for item in rds_data:
                html_content += f"""
            <tr>
                <td>{item['resource_id']}</td>
                <td>{item['instance_type']}</td>
                <td>{item['environment']}</td>
                <td>{item.get('engine', '')}</td>
                <td>{item.get('multi_az', '')}</td>
                <td>{item.get('storage_type', '')}</td>
                <td>${item['daily_cost']:,.2f}</td>
                <td>${item['monthly_cost']:,.2f}</td>
            </tr>
"""
            html_content += """
        </tbody>
    </table>
"""
        
        # Add detailed EKS table with per-cluster view
        eks_data = [d for d in detailed_data if d['service'] == 'EKS']
        if eks_data:
            # Group EKS data by cluster and nodegroup
            eks_clusters = {}
            for item in eks_data:
                cluster_name = item['cluster_name']
                nodegroup_name = item['nodegroup_name']
                
                if cluster_name not in eks_clusters:
                    eks_clusters[cluster_name] = {
                        'environment': item['environment'],
                        'deployment_count': item.get('deployment_count', 'N/A'),
                        'nodegroups': {},
                        'total_daily': 0,
                        'total_monthly': 0
                    }
                
                if nodegroup_name not in eks_clusters[cluster_name]['nodegroups']:
                    eks_clusters[cluster_name]['nodegroups'][nodegroup_name] = {
                        'instance_type': item['instance_type'],
                        'nodes': [],
                        'daily_cost': 0,
                        'monthly_cost': 0
                    }
                
                eks_clusters[cluster_name]['nodegroups'][nodegroup_name]['nodes'].append(item)
                eks_clusters[cluster_name]['nodegroups'][nodegroup_name]['daily_cost'] += item['daily_cost']
                eks_clusters[cluster_name]['nodegroups'][nodegroup_name]['monthly_cost'] += item['monthly_cost']
                eks_clusters[cluster_name]['total_daily'] += item['daily_cost']
                eks_clusters[cluster_name]['total_monthly'] += item['monthly_cost']
            
            html_content += """
    <h2 class="section-title">EKS Cluster Details</h2>
"""
            
            for cluster_name, cluster_data in eks_clusters.items():
                html_content += f"""
    <div style="margin-bottom: 30px; border: 1px solid #ddd; border-radius: 5px; padding: 15px;">
        <h3 style="margin-top: 0; color: #232f3e;">Cluster: {cluster_name}</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px;">
            <div><strong>Environment:</strong> {cluster_data['environment']}</div>
            <div><strong>Deployments:</strong> {cluster_data['deployment_count']}</div>
            <div><strong>Total Daily Cost:</strong> ${cluster_data['total_daily']:,.2f}</div>
            <div><strong>Total Monthly Cost:</strong> ${cluster_data['total_monthly']:,.2f}</div>
        </div>
        
        <table style="margin-top: 15px;">
            <thead>
                <tr>
                    <th>Node Group</th>
                    <th>Instance Type</th>
                    <th>Type</th>
                    <th>Node Count</th>
                    <th>Cost per Node (Daily)</th>
                    <th>Cost per Node (Monthly)</th>
                    <th>Total Daily Cost</th>
                    <th>Total Monthly Cost</th>
                </tr>
            </thead>
            <tbody>
"""
                
                for nodegroup_name, nodegroup_data in cluster_data['nodegroups'].items():
                    node_count = len(nodegroup_data['nodes'])
                    cost_per_node_daily = nodegroup_data['daily_cost'] / node_count if node_count > 0 else 0
                    cost_per_node_monthly = nodegroup_data['monthly_cost'] / node_count if node_count > 0 else 0
                    
                    html_content += f"""
                <tr>
                    <td>{nodegroup_name}</td>
                    <td>{nodegroup_data['instance_type']}</td>
                    <td>EKS Manage Node</td>
                    <td>{node_count}</td>
                    <td>${cost_per_node_daily:,.2f}</td>
                    <td>${cost_per_node_monthly:,.2f}</td>
                    <td>${nodegroup_data['daily_cost']:,.2f}</td>
                    <td>${nodegroup_data['monthly_cost']:,.2f}</td>
                </tr>
"""
                
                html_content += """
            </tbody>
        </table>
    </div>
"""
            
            html_content += """
    </div>
"""
        
        # Calculate resource counts by service
        service_resource_counts = {}
        for item in summary_data:
            if item['service'] != 'TOTAL':
                service_resource_counts[item['service']] = service_resource_counts.get(item['service'], 0) + item['resource_count']
        
        # Add JavaScript for charts
        html_content += f"""
    <script>
        // Service Chart (smaller pie chart)
        const serviceCtx = document.getElementById('serviceChart').getContext('2d');
        new Chart(serviceCtx, {{
            type: 'doughnut',
            data: {{
                labels: {list(service_totals.keys())},
                datasets: [{{
                    data: {list(service_totals.values())},
                    backgroundColor: ['#ff9900', '#232f3e', '#146eb4', '#43a047', '#e53935']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            padding: 10,
                            usePointStyle: true
                        }}
                    }},
                    tooltip: {{
                        callbacks: {{
                            label: function(context) {{
                                return context.label + ': $' + context.parsed.toFixed(2);
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Environment Chart
        const envCtx = document.getElementById('envChart').getContext('2d');
        new Chart(envCtx, {{
            type: 'bar',
            data: {{
                labels: {list(env_totals.keys())},
                datasets: [{{
                    label: 'Monthly Cost',
                    data: {list(env_totals.values())},
                    backgroundColor: '#ff9900',
                    borderColor: '#e68900',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return '$' + value.toFixed(2);
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Instance Types Chart
        const instanceCtx = document.getElementById('instanceChart').getContext('2d');
        new Chart(instanceCtx, {{
            type: 'bar',
            data: {{
                labels: {list(top_instance_types.keys())},
                datasets: [{{
                    label: 'Monthly Cost',
                    data: {list(top_instance_types.values())},
                    backgroundColor: '#146eb4',
                    borderColor: '#0d47a1',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                indexAxis: 'y',
                scales: {{
                    x: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return '$' + value.toFixed(2);
                            }}
                        }}
                    }}
                }}
            }}
        }});
        
        // Resource Count Chart
        const resourceCtx = document.getElementById('resourceChart').getContext('2d');
        new Chart(resourceCtx, {{
            type: 'bar',
            data: {{
                labels: {list(service_resource_counts.keys())},
                datasets: [{{
                    label: 'Resource Count',
                    data: {list(service_resource_counts.values())},
                    backgroundColor: '#43a047',
                    borderColor: '#2e7d32',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {output_file}")

if __name__ == "__main__":
    generator = ReportGenerator()
    generator.generate_csv_report()
    generator.generate_html_report()