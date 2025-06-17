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
    
    def generate_csv_report(self, output_file=None):
        """Generate CSV report with detailed costs"""
        # Auto-generate filename based on account ID if not provided
        if output_file is None:
            account_id = self.results.get('metadata', {}).get('account_id', 'unknown')
            output_file = f'reports/csv/cost_report_{account_id}.csv'
        
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
        
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        os.makedirs(os.path.dirname(summary_file), exist_ok=True)
        
        with open(summary_file, 'w', newline='') as csvfile:
            fieldnames = ['service', 'environment', 'resource_count', 'daily_cost', 'monthly_cost', 'currency']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary_data)
        
        logger.info(f"CSV reports generated: {output_file}, {summary_file}")
    
    def generate_html_report(self, output_file=None):
        """Generate HTML report with styled tables and charts"""
        metadata = self.results.get('metadata', {})
        
        # Auto-generate filename based on account ID if not provided
        if output_file is None:
            account_id = metadata.get('account_id', 'unknown')
            output_file = f'reports/cost_report_{account_id}.html'
        
        logger.info(f"Generating HTML report: {output_file}")
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
        .filters {{
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            align-items: end;
        }}
        .filter-group {{
            display: flex;
            flex-direction: column;
        }}
        .filter-group label {{
            margin-bottom: 5px;
            font-weight: bold;
            color: #232f3e;
        }}
        .filter-group select, .filter-group input {{
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 3px;
            font-size: 14px;
        }}
        .filter-group button {{
            padding: 10px 20px;
            background-color: #ff9900;
            color: white;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 14px;
        }}
        .filter-group button:hover {{
            background-color: #e68900;
        }}
        .hidden {{
            display: none !important;
        }}
        .sortable {{
            cursor: pointer;
            position: relative;
        }}
        .sortable:hover {{
            background-color: #1a252f;
        }}
        .sortable::after {{
            content: '↕';
            position: absolute;
            right: 5px;
            color: #ccc;
        }}
        .sort-asc::after {{
            content: '↑';
            color: white;
        }}
        .sort-desc::after {{
            content: '↓';
            color: white;
        }}
        .savings-calculator {{
            background-color: white;
            padding: 25px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            border-left: 4px solid #43a047;
        }}
        .savings-header {{
            color: #232f3e;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .savings-header::before {{
            content: '💰';
            font-size: 24px;
        }}
        .savings-controls {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 25px;
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
        }}
        .control-group label {{
            margin-bottom: 8px;
            font-weight: bold;
            color: #232f3e;
        }}
        .control-group select, .control-group input {{
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }}
        .time-controls {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        .checkbox-group {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 5px;
        }}
        .checkbox-group input[type="checkbox"] {{
            width: 18px;
            height: 18px;
        }}
        .calculate-btn {{
            background-color: #43a047;
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: background-color 0.3s;
        }}
        .calculate-btn:hover {{
            background-color: #2e7d32;
        }}
        .savings-results {{
            display: none;
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 4px;
            border: 1px solid #e9ecef;
            margin-top: 20px;
        }}
        .savings-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .savings-card {{
            background-color: white;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .savings-card h4 {{
            margin: 0 0 8px 0;
            color: #232f3e;
            font-size: 14px;
        }}
        .savings-card .amount {{
            font-size: 20px;
            font-weight: bold;
            color: #43a047;
        }}
        .savings-breakdown {{
            margin-top: 20px;
        }}
        .breakdown-table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            border-radius: 4px;
            overflow: hidden;
        }}
        .breakdown-table th {{
            background-color: #43a047;
            color: white;
            padding: 10px;
            text-align: left;
            font-size: 14px;
        }}
        .breakdown-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
            font-size: 14px;
        }}
        .breakdown-table tr:hover {{
            background-color: #f5f5f5;
        }}
        .warning-text {{
            color: #e65100;
            font-style: italic;
            font-size: 13px;
            margin-top: 10px;
        }}
        .schedule-preview {{
            background-color: #e3f2fd;
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            font-size: 13px;
            color: #1565c0;
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
    
    <!-- Filters Section -->
    <div class="filters">
        <div class="filter-group">
            <label for="serviceFilter">Filter by Service:</label>
            <select id="serviceFilter">
                <option value="all">All Services</option>
                <option value="EC2">EC2</option>
                <option value="RDS">RDS</option>
                <option value="EKS">EKS</option>
            </select>
        </div>
        <div class="filter-group">
            <label for="envFilter">Filter by Environment:</label>
            <select id="envFilter">
                <option value="all">All Environments</option>
            </select>
        </div>
        <div class="filter-group">
            <label for="instanceFilter">Filter by Instance Type:</label>
            <select id="instanceFilter">
                <option value="all">All Instance Types</option>
            </select>
        </div>
        <div class="filter-group">
            <label for="costFilter">Min Monthly Cost ($):</label>
            <input type="number" id="costFilter" min="0" step="0.01" placeholder="0.00">
        </div>
        <div class="filter-group">
            <button onclick="applyFilters()">Apply Filters</button>
        </div>
        <div class="filter-group">
            <button onclick="clearFilters()">Clear Filters</button>
        </div>
    </div>
    
    <!-- Cost Savings Calculator -->
    <div class="savings-calculator">
        <h2 class="savings-header">Cost Savings Calculator</h2>
        <p>Calculate potential savings by automatically stopping instances during off-hours and weekends.</p>
        
        <div class="savings-controls">
            <div class="control-group">
                <label for="savingsScope">Apply Savings To:</label>
                <select id="savingsScope">
                    <option value="all">All Resources</option>
                    <option value="service">Specific Service</option>
                    <option value="environment">Specific Environment</option>
                    <option value="service-environment">Service + Environment</option>
                </select>
            </div>
            
            <div class="control-group" id="serviceSelection" style="display: none;">
                <label for="savingsService">Select Service:</label>
                <select id="savingsService">
                    <option value="EC2">EC2</option>
                    <option value="RDS">RDS</option>
                    <option value="EKS">EKS</option>
                </select>
            </div>
            
            <div class="control-group" id="environmentSelection" style="display: none;">
                <label for="savingsEnvironment">Select Environment:</label>
                <select id="savingsEnvironment">
                </select>
            </div>
            
            <div class="control-group">
                <label>Running Hours (24h format):</label>
                <div class="time-controls">
                    <div>
                        <label for="startTime" style="font-size: 12px; margin-bottom: 4px;">Start Time:</label>
                        <input type="time" id="startTime" value="08:00">
                    </div>
                    <div>
                        <label for="endTime" style="font-size: 12px; margin-bottom: 4px;">End Time:</label>
                        <input type="time" id="endTime" value="19:00">
                    </div>
                </div>
                <div class="schedule-preview" id="schedulePreview">
                    Instances will run from 08:00 to 19:00 (11 hours/day)
                </div>
            </div>
            
            <div class="control-group">
                <label>Weekend Operation:</label>
                <div class="checkbox-group">
                    <input type="checkbox" id="runWeekends">
                    <label for="runWeekends">Run on weekends</label>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="runSaturday">
                    <label for="runSaturday">Run on Saturday only</label>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="runSunday">
                    <label for="runSunday">Run on Sunday only</label>
                </div>
            </div>
            
            <div class="control-group">
                <label>&nbsp;</label>
                <button class="calculate-btn" onclick="calculateSavings()">Calculate Savings</button>
            </div>
        </div>
        
        <div class="savings-results" id="savingsResults">
            <div class="savings-summary">
                <div class="savings-card">
                    <h4>Current Monthly Cost</h4>
                    <div class="amount" id="currentCost">$0.00</div>
                </div>
                <div class="savings-card">
                    <h4>Optimized Monthly Cost</h4>
                    <div class="amount" id="optimizedCost">$0.00</div>
                </div>
                <div class="savings-card">
                    <h4>Monthly Savings</h4>
                    <div class="amount" id="monthlySavings">$0.00</div>
                </div>
                <div class="savings-card">
                    <h4>Annual Savings</h4>
                    <div class="amount" id="annualSavings">$0.00</div>
                </div>
                <div class="savings-card">
                    <h4>Savings Percentage</h4>
                    <div class="amount" id="savingsPercentage">0%</div>
                </div>
            </div>
            
            <div class="savings-breakdown">
                <h4>Detailed Breakdown</h4>
                <table class="breakdown-table">
                    <thead>
                        <tr>
                            <th>Service</th>
                            <th>Environment</th>
                            <th>Resources</th>
                            <th>Current Monthly</th>
                            <th>Optimized Monthly</th>
                            <th>Monthly Savings</th>
                            <th>Hours Saved/Week</th>
                        </tr>
                    </thead>
                    <tbody id="breakdownTableBody">
                    </tbody>
                </table>
            </div>
            
            <div class="warning-text">
                * Calculations assume instances can be safely stopped during specified hours.<br>
                * RDS instances may have additional considerations for Multi-AZ deployments.<br>
                * EKS node savings depend on cluster auto-scaling configuration.<br>
                * Always test schedule changes in non-production environments first.
            </div>
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
    <table id="summaryTable">
        <thead>
            <tr>
                <th class="sortable" onclick="sortTable('summaryTable', 0)">Service</th>
                <th class="sortable" onclick="sortTable('summaryTable', 1)">Environment</th>
                <th class="sortable" onclick="sortTable('summaryTable', 2)">Resource Count</th>
                <th class="sortable" onclick="sortTable('summaryTable', 3)">Daily Cost</th>
                <th class="sortable" onclick="sortTable('summaryTable', 4)">Monthly Cost</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for item in summary_data:
            row_class = 'total-row' if item['service'] == 'TOTAL' else ''
            html_content += f"""
            <tr class="{row_class}" data-service="{item['service']}" data-environment="{item['environment']}" data-monthly-cost="{item['monthly_cost']}">
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
    <table id="ec2Table">
        <thead>
            <tr>
                <th class="sortable" onclick="sortTable('ec2Table', 0)">Instance ID</th>
                <th class="sortable" onclick="sortTable('ec2Table', 1)">Instance Type</th>
                <th class="sortable" onclick="sortTable('ec2Table', 2)">Environment</th>
                <th class="sortable" onclick="sortTable('ec2Table', 3)">Type</th>
                <th class="sortable" onclick="sortTable('ec2Table', 4)">In ASG</th>
                <th class="sortable" onclick="sortTable('ec2Table', 5)">ASG Name</th>
                <th class="sortable" onclick="sortTable('ec2Table', 6)">Daily Cost</th>
                <th class="sortable" onclick="sortTable('ec2Table', 7)">Monthly Cost</th>
            </tr>
        </thead>
        <tbody>
"""
            for item in ec2_data:
                type_class = 'ec2-ephemeral' if item.get('type') == 'Ephemeral' else 'ec2-managed'
                html_content += f"""
            <tr class="detail-row" data-service="EC2" data-environment="{item['environment']}" data-instance-type="{item['instance_type']}" data-monthly-cost="{item['monthly_cost']}">
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
    <table id="rdsTable">
        <thead>
            <tr>
                <th class="sortable" onclick="sortTable('rdsTable', 0)">Instance ID</th>
                <th class="sortable" onclick="sortTable('rdsTable', 1)">Instance Class</th>
                <th class="sortable" onclick="sortTable('rdsTable', 2)">Environment</th>
                <th class="sortable" onclick="sortTable('rdsTable', 3)">Engine</th>
                <th class="sortable" onclick="sortTable('rdsTable', 4)">Multi-AZ</th>
                <th class="sortable" onclick="sortTable('rdsTable', 5)">Storage Type</th>
                <th class="sortable" onclick="sortTable('rdsTable', 6)">Daily Cost</th>
                <th class="sortable" onclick="sortTable('rdsTable', 7)">Monthly Cost</th>
            </tr>
        </thead>
        <tbody>
"""
            for item in rds_data:
                html_content += f"""
            <tr class="detail-row" data-service="RDS" data-environment="{item['environment']}" data-instance-type="{item['instance_type']}" data-monthly-cost="{item['monthly_cost']}">
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
        
        <table id="eksTable_{cluster_name.replace('-', '_')}" style="margin-top: 15px;">
            <thead>
                <tr>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 0)">Node Group</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 1)">Instance Type</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 2)">Type</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 3)">Node Count</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 4)">Cost per Node (Daily)</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 5)">Cost per Node (Monthly)</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 6)">Total Daily Cost</th>
                    <th class="sortable" onclick="sortTable('eksTable_{cluster_name.replace('-', '_')}', 7)">Total Monthly Cost</th>
                </tr>
            </thead>
            <tbody>
"""
                
                for nodegroup_name, nodegroup_data in cluster_data['nodegroups'].items():
                    node_count = len(nodegroup_data['nodes'])
                    cost_per_node_daily = nodegroup_data['daily_cost'] / node_count if node_count > 0 else 0
                    cost_per_node_monthly = nodegroup_data['monthly_cost'] / node_count if node_count > 0 else 0
                    
                    html_content += f"""
                <tr class="detail-row eks-cluster-row" data-service="EKS" data-environment="{cluster_data['environment']}" data-instance-type="{nodegroup_data['instance_type']}" data-monthly-cost="{nodegroup_data['monthly_cost']}" data-cluster="{cluster_name}">
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
        
        # Collect unique values for filter dropdowns
        unique_environments = set()
        unique_instance_types = set()
        
        for item in detailed_data:
            unique_environments.add(item['environment'])
            unique_instance_types.add(item['instance_type'])
        
        unique_environments = sorted(list(unique_environments))
        unique_instance_types = sorted(list(unique_instance_types))
        
        # Add JavaScript for filtering, sorting, and charts
        html_content += f"""
    <script>
        // Populate filter dropdowns
        document.addEventListener('DOMContentLoaded', function() {{
            const envFilter = document.getElementById('envFilter');
            const instanceFilter = document.getElementById('instanceFilter');
            
            // Add environment options
            {repr(unique_environments)}.forEach(env => {{
                const option = document.createElement('option');
                option.value = env;
                option.textContent = env;
                envFilter.appendChild(option);
            }});
            
            // Add instance type options
            {repr(unique_instance_types)}.forEach(type => {{
                const option = document.createElement('option');
                option.value = type;
                option.textContent = type;
                instanceFilter.appendChild(option);
            }});
        }});
        
        // Filtering functions
        function applyFilters() {{
            const serviceFilter = document.getElementById('serviceFilter').value;
            const envFilter = document.getElementById('envFilter').value;
            const instanceFilter = document.getElementById('instanceFilter').value;
            const costFilter = parseFloat(document.getElementById('costFilter').value) || 0;
            
            // Filter summary table
            const summaryRows = document.querySelectorAll('#summaryTable tbody tr');
            summaryRows.forEach(row => {{
                const service = row.getAttribute('data-service');
                const environment = row.getAttribute('data-environment');
                const monthlyCost = parseFloat(row.getAttribute('data-monthly-cost'));
                
                let show = true;
                if (serviceFilter !== 'all' && service !== serviceFilter) show = false;
                if (envFilter !== 'all' && environment !== envFilter) show = false;
                if (monthlyCost < costFilter) show = false;
                
                row.style.display = show ? '' : 'none';
            }});
            
            // Filter detail tables
            const detailRows = document.querySelectorAll('.detail-row');
            detailRows.forEach(row => {{
                const service = row.getAttribute('data-service');
                const environment = row.getAttribute('data-environment');
                const instanceType = row.getAttribute('data-instance-type');
                const monthlyCost = parseFloat(row.getAttribute('data-monthly-cost'));
                
                let show = true;
                if (serviceFilter !== 'all' && service !== serviceFilter) show = false;
                if (envFilter !== 'all' && environment !== envFilter) show = false;
                if (instanceFilter !== 'all' && instanceType !== instanceFilter) show = false;
                if (monthlyCost < costFilter) show = false;
                
                row.style.display = show ? '' : 'none';
            }});
            
            // Filter EKS clusters
            const eksClusterRows = document.querySelectorAll('.eks-cluster-row');
            eksClusterRows.forEach(row => {{
                const service = row.getAttribute('data-service');
                const environment = row.getAttribute('data-environment');
                const instanceType = row.getAttribute('data-instance-type');
                const monthlyCost = parseFloat(row.getAttribute('data-monthly-cost'));
                
                let show = true;
                if (serviceFilter !== 'all' && service !== serviceFilter) show = false;
                if (envFilter !== 'all' && environment !== envFilter) show = false;
                if (instanceFilter !== 'all' && instanceType !== instanceFilter) show = false;
                if (monthlyCost < costFilter) show = false;
                
                row.style.display = show ? '' : 'none';
                
                // Hide entire cluster div if no rows visible
                const clusterDiv = row.closest('div[style*="border"]');
                if (clusterDiv) {{
                    const visibleRows = clusterDiv.querySelectorAll('.eks-cluster-row:not([style*="display: none"])');
                    clusterDiv.style.display = visibleRows.length > 0 ? '' : 'none';
                }}
            }});
        }}
        
        function clearFilters() {{
            document.getElementById('serviceFilter').value = 'all';
            document.getElementById('envFilter').value = 'all';
            document.getElementById('instanceFilter').value = 'all';
            document.getElementById('costFilter').value = '';
            
            // Show all rows
            const allRows = document.querySelectorAll('tr, div[style*="border"]');
            allRows.forEach(row => {{
                row.style.display = '';
            }});
        }}
        
        // Sorting functions
        let sortDirection = {{}};
        
        function sortTable(tableId, columnIndex) {{
            const table = document.getElementById(tableId);
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isNumeric = columnIndex >= 6; // Cost columns are numeric
            
            const sortKey = tableId + '_' + columnIndex;
            const ascending = !sortDirection[sortKey];
            sortDirection[sortKey] = ascending;
            
            // Update header appearance
            const headers = table.querySelectorAll('th.sortable');
            headers.forEach(header => {{
                header.classList.remove('sort-asc', 'sort-desc');
            }});
            
            const currentHeader = headers[columnIndex];
            currentHeader.classList.add(ascending ? 'sort-asc' : 'sort-desc');
            
            rows.sort((a, b) => {{
                const aValue = a.cells[columnIndex].textContent.trim();
                const bValue = b.cells[columnIndex].textContent.trim();
                
                let aVal, bVal;
                if (isNumeric) {{
                    aVal = parseFloat(aValue.replace(/[$,]/g, '')) || 0;
                    bVal = parseFloat(bValue.replace(/[$,]/g, '')) || 0;
                }} else {{
                    aVal = aValue.toLowerCase();
                    bVal = bValue.toLowerCase();
                }}
                
                if (aVal < bVal) return ascending ? -1 : 1;
                if (aVal > bVal) return ascending ? 1 : -1;
                return 0;
            }});
            
            // Reorder rows
            rows.forEach(row => tbody.appendChild(row));
        }}
        
        // Cost Savings Calculator Functions
        const detailedResourceData = {repr(detailed_data)};
        
        // Initialize savings calculator
        document.addEventListener('DOMContentLoaded', function() {{
            // Populate environment dropdown for savings calculator
            const savingsEnvSelect = document.getElementById('savingsEnvironment');
            {repr(unique_environments)}.forEach(env => {{
                const option = document.createElement('option');
                option.value = env;
                option.textContent = env;
                savingsEnvSelect.appendChild(option);
            }});
            
            // Setup event listeners for savings calculator
            document.getElementById('savingsScope').addEventListener('change', updateSavingsScope);
            document.getElementById('startTime').addEventListener('change', updateSchedulePreview);
            document.getElementById('endTime').addEventListener('change', updateSchedulePreview);
            document.getElementById('runWeekends').addEventListener('change', updateWeekendControls);
            document.getElementById('runSaturday').addEventListener('change', updateWeekendControls);
            document.getElementById('runSunday').addEventListener('change', updateWeekendControls);
            
            updateSchedulePreview();
        }});
        
        function updateSavingsScope() {{
            const scope = document.getElementById('savingsScope').value;
            const serviceSelection = document.getElementById('serviceSelection');
            const environmentSelection = document.getElementById('environmentSelection');
            
            serviceSelection.style.display = (scope === 'service' || scope === 'service-environment') ? 'block' : 'none';
            environmentSelection.style.display = (scope === 'environment' || scope === 'service-environment') ? 'block' : 'none';
        }}
        
        function updateSchedulePreview() {{
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;
            const preview = document.getElementById('schedulePreview');
            
            if (startTime && endTime) {{
                const start = new Date('2000-01-01 ' + startTime);
                const end = new Date('2000-01-01 ' + endTime);
                let hours = (end - start) / (1000 * 60 * 60);
                
                if (hours < 0) {{
                    hours += 24; // Handle overnight schedules
                }}
                
                preview.textContent = `Instances will run from ${{startTime}} to ${{endTime}} (${{hours}} hours/day)`;
            }}
        }}
        
        function updateWeekendControls() {{
            const runWeekends = document.getElementById('runWeekends');
            const runSaturday = document.getElementById('runSaturday');
            const runSunday = document.getElementById('runSunday');
            
            if (runWeekends.checked) {{
                runSaturday.checked = false;
                runSunday.checked = false;
                runSaturday.disabled = true;
                runSunday.disabled = true;
            }} else {{
                runSaturday.disabled = false;
                runSunday.disabled = false;
            }}
        }}
        
        function calculateSavings() {{
            const scope = document.getElementById('savingsScope').value;
            const service = document.getElementById('savingsService').value;
            const environment = document.getElementById('savingsEnvironment').value;
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;
            const runWeekends = document.getElementById('runWeekends').checked;
            const runSaturday = document.getElementById('runSaturday').checked;
            const runSunday = document.getElementById('runSunday').checked;
            
            if (!startTime || !endTime) {{
                alert('Please specify both start and end times.');
                return;
            }}
            
            // Calculate daily running hours
            const start = new Date('2000-01-01 ' + startTime);
            const end = new Date('2000-01-01 ' + endTime);
            let dailyRunningHours = (end - start) / (1000 * 60 * 60);
            if (dailyRunningHours < 0) {{
                dailyRunningHours += 24; // Handle overnight schedules
            }}
            
            // Calculate weekly schedule
            let weekdayHours = dailyRunningHours * 5; // Monday to Friday
            let weekendHours = 0;
            
            if (runWeekends) {{
                weekendHours = dailyRunningHours * 2; // Both Saturday and Sunday
            }} else {{
                if (runSaturday) weekendHours += dailyRunningHours;
                if (runSunday) weekendHours += dailyRunningHours;
            }}
            
            const totalWeeklyHours = weekdayHours + weekendHours;
            const hoursStoppedPerWeek = 168 - totalWeeklyHours; // 168 hours in a week
            const utilizationRatio = totalWeeklyHours / 168;
            
            // Filter resources based on scope
            let filteredResources = detailedResourceData.filter(resource => {{
                if (scope === 'service') {{
                    return resource.service === service;
                }} else if (scope === 'environment') {{
                    return resource.environment === environment;
                }} else if (scope === 'service-environment') {{
                    return resource.service === service && resource.environment === environment;
                }}
                return true; // 'all' scope
            }});
            
            // Calculate savings
            let totalCurrentCost = 0;
            let totalOptimizedCost = 0;
            const breakdownData = {{}};
            
            filteredResources.forEach(resource => {{
                const key = `${{resource.service}}_${{resource.environment}}`;
                
                if (!breakdownData[key]) {{
                    breakdownData[key] = {{
                        service: resource.service,
                        environment: resource.environment,
                        resourceCount: 0,
                        currentMonthlyCost: 0,
                        optimizedMonthlyCost: 0
                    }};
                }}
                
                breakdownData[key].resourceCount++;
                breakdownData[key].currentMonthlyCost += resource.monthly_cost;
                
                // Calculate optimized cost based on utilization ratio
                const optimizedCost = resource.monthly_cost * utilizationRatio;
                breakdownData[key].optimizedMonthlyCost += optimizedCost;
                
                totalCurrentCost += resource.monthly_cost;
                totalOptimizedCost += optimizedCost;
            }});
            
            const totalSavings = totalCurrentCost - totalOptimizedCost;
            const savingsPercentage = totalCurrentCost > 0 ? (totalSavings / totalCurrentCost * 100) : 0;
            const annualSavings = totalSavings * 12;
            
            // Update results display
            document.getElementById('currentCost').textContent = `$${{totalCurrentCost.toFixed(2)}}`;
            document.getElementById('optimizedCost').textContent = `$${{totalOptimizedCost.toFixed(2)}}`;
            document.getElementById('monthlySavings').textContent = `$${{totalSavings.toFixed(2)}}`;
            document.getElementById('annualSavings').textContent = `$${{annualSavings.toFixed(2)}}`;
            document.getElementById('savingsPercentage').textContent = `${{savingsPercentage.toFixed(1)}}%`;
            
            // Update breakdown table
            const tableBody = document.getElementById('breakdownTableBody');
            tableBody.innerHTML = '';
            
            Object.values(breakdownData).forEach(data => {{
                const row = tableBody.insertRow();
                const savings = data.currentMonthlyCost - data.optimizedMonthlyCost;
                
                row.innerHTML = `
                    <td>${{data.service}}</td>
                    <td>${{data.environment}}</td>
                    <td>${{data.resourceCount}}</td>
                    <td>$${{data.currentMonthlyCost.toFixed(2)}}</td>
                    <td>$${{data.optimizedMonthlyCost.toFixed(2)}}</td>
                    <td style="color: #43a047; font-weight: bold;">$${{savings.toFixed(2)}}</td>
                    <td>${{hoursStoppedPerWeek.toFixed(1)}} hrs</td>
                `;
            }});
            
            // Show results
            document.getElementById('savingsResults').style.display = 'block';
            
            // Scroll to results
            document.getElementById('savingsResults').scrollIntoView({{ behavior: 'smooth' }});
        }}
        
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
        
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        logger.info(f"HTML report generated: {output_file}")
    
    def generate_json_data(self, output_file=None):
        """Generate JSON data file for dashboard aggregation"""
        metadata = self.results.get('metadata', {})
        
        # Auto-generate filename based on account ID if not provided
        if output_file is None:
            account_id = metadata.get('account_id', 'unknown')
            output_file = f'reports/data/{account_id}.json'
        
        logger.info(f"Generating JSON data file: {output_file}")
        
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Prepare data for dashboard
        dashboard_data = {
            'account_id': metadata.get('account_id', 'unknown'),
            'account_name': metadata.get('account_name', f"Account {metadata.get('account_id', 'unknown')}"),
            'region': metadata.get('region', 'unknown'),
            'scan_time': metadata.get('scan_time'),
            'estimation_time': metadata.get('estimation_time'),
            'currency': metadata.get('currency', 'USD'),
            'config_last_updated': metadata.get('config_last_updated'),
            'summary': self.results.get('summary', []),
            'detailed': self.results.get('detailed', [])
        }
        
        with open(output_file, 'w') as f:
            json.dump(dashboard_data, f, indent=2, default=str)
        
        logger.info(f"JSON data file generated: {output_file}")
        return output_file

if __name__ == "__main__":
    generator = ReportGenerator()
    generator.generate_csv_report()
    generator.generate_html_report()
    generator.generate_json_data()