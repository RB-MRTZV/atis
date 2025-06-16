# src/reporting.py
import csv
import json
import logging
import os
from datetime import datetime
from tabulate import tabulate

class ReportingError(Exception):
    """Exception raised for reporting errors."""
    pass

class Reporter:
    """Handles reporting of instance and ASG operations."""
    
    def __init__(self, reports_dir="reports"):
        """Initialize reporter.
        
        Args:
            reports_dir (str): Directory for reports
        """
        self.logger = logging.getLogger(__name__)
        self.reports_dir = reports_dir
        self.results = []
        
        # Create reports directory if it doesn't exist
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
            
    def add_result(self, resource_type, account, region, resource_id, resource_name, 
                   previous_state, new_state, action, timestamp, status, error=None, details=None):
        """Add a result to the report.
        
        Args:
            resource_type (str): Type of resource (EC2, ASG, EC2-ASG)
            account (str): AWS account name
            region (str): AWS region
            resource_id (str): Resource ID (instance ID or ASG name)
            resource_name (str): Resource name
            previous_state (str): Previous resource state
            new_state (str): New resource state
            action (str): Action performed (start/stop)
            timestamp (str): Timestamp of action
            status (str): Status of action (Success/Failed/Simulated)
            error (str): Error message if failed
            details (str): Additional details
        """
        result = {
            'ResourceType': resource_type,
            'Account': account,
            'Region': region,
            'ResourceId': resource_id,
            'Name': resource_name,
            'PreviousState': previous_state,
            'NewState': new_state,
            'Action': action,
            'Timestamp': timestamp,
            'Status': status,
            'Error': error or '',
            'Details': details or ''
        }
        
        self.results.append(result)
        
    def generate_csv_report(self):
        """Generate a CSV report of results.
        
        Returns:
            str: Path to the generated CSV file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/scheduler_report_{timestamp}.csv"
            
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['ResourceType', 'Account', 'Region', 'ResourceId', 'Name', 
                              'PreviousState', 'NewState', 'Action', 'Timestamp', 'Status', 'Error', 'Details']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result)
                    
            self.logger.info(f"CSV report generated: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Failed to generate CSV report: {str(e)}")
            raise ReportingError(f"Failed to generate CSV report: {str(e)}")
            
    def generate_json_report(self):
        """Generate a JSON report of results.
        
        Returns:
            str: Path to the generated JSON file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/scheduler_report_{timestamp}.json"
            
            with open(filename, 'w') as jsonfile:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'results': self.results
                }, jsonfile, indent=2)
                
            self.logger.info(f"JSON report generated: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Failed to generate JSON report: {str(e)}")
            raise ReportingError(f"Failed to generate JSON report: {str(e)}")
            
    def generate_table_report(self):
        """Generate a tabular text report of results.
        
        Returns:
            str: Tabular text report
        """
        try:
            headers = ['Type', 'Account', 'Region', 'Resource ID', 'Name', 'Previous State', 
                       'New State', 'Action', 'Timestamp', 'Status', 'Error', 'Details']
                       
            rows = []
            for result in self.results:
                # Truncate long resource IDs for better table formatting
                resource_id = result['ResourceId']
                if len(resource_id) > 20:
                    resource_id = resource_id[:17] + "..."
                    
                rows.append([
                    result['ResourceType'],
                    result['Account'],
                    result['Region'],
                    resource_id,
                    result['Name'][:15] + "..." if len(result['Name']) > 15 else result['Name'],
                    result['PreviousState'],
                    result['NewState'],
                    result['Action'],
                    result['Timestamp'][:16],  # Show only date and time, no seconds
                    result['Status'],
                    result['Error'][:20] + "..." if len(result['Error']) > 20 else result['Error'],
                    result['Details'][:15] + "..." if len(result['Details']) > 15 else result['Details']
                ])
                
            table = tabulate(rows, headers=headers, tablefmt='grid')
            
            # Also save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/scheduler_report_{timestamp}.txt"
            
            with open(filename, 'w') as txtfile:
                txtfile.write(table)
                
            self.logger.info(f"Table report generated: {filename}")
            return table
            
        except Exception as e:
            self.logger.error(f"Failed to generate table report: {str(e)}")
            raise ReportingError(f"Failed to generate table report: {str(e)}")
            
    def generate_summary(self):
        """Generate a summary of the results.
        
        Returns:
            str: Summary text
        """
        total = len(self.results)
        successful = sum(1 for r in self.results if r['Status'] == 'Success')
        failed = sum(1 for r in self.results if r['Status'] == 'Failed')
        simulated = sum(1 for r in self.results if r['Status'] == 'Simulated')
        
        # Group by resource type
        resource_types = {}
        for result in self.results:
            resource_type = result['ResourceType']
            if resource_type not in resource_types:
                resource_types[resource_type] = {'total': 0, 'successful': 0, 'failed': 0, 'simulated': 0}
            
            resource_types[resource_type]['total'] += 1
            if result['Status'] == 'Success':
                resource_types[resource_type]['successful'] += 1
            elif result['Status'] == 'Failed':
                resource_types[resource_type]['failed'] += 1
            elif result['Status'] == 'Simulated':
                resource_types[resource_type]['simulated'] += 1
        
        # Group by action
        actions = {}
        for result in self.results:
            action = result['Action']
            if action not in actions:
                actions[action] = {'total': 0, 'successful': 0, 'failed': 0, 'simulated': 0}
            
            actions[action]['total'] += 1
            if result['Status'] == 'Success':
                actions[action]['successful'] += 1
            elif result['Status'] == 'Failed':
                actions[action]['failed'] += 1
            elif result['Status'] == 'Simulated':
                actions[action]['simulated'] += 1
        
        # Group by account
        accounts = {}
        for result in self.results:
            account = result['Account']
            if account not in accounts:
                accounts[account] = {'total': 0, 'successful': 0, 'failed': 0, 'simulated': 0}
            
            accounts[account]['total'] += 1
            if result['Status'] == 'Success':
                accounts[account]['successful'] += 1
            elif result['Status'] == 'Failed':
                accounts[account]['failed'] += 1
            elif result['Status'] == 'Simulated':
                accounts[account]['simulated'] += 1
                
        summary = [
            f"EC2/ASG Scheduler Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Total resources processed: {total}",
            f"Successful operations: {successful}",
            f"Failed operations: {failed}"
        ]
        
        if simulated > 0:
            summary.append(f"Simulated operations: {simulated}")
        
        summary.append("\nResource Types:")
        for resource_type, stats in resource_types.items():
            summary.append(f"  {resource_type}: {stats['total']} total, {stats['successful']} successful, {stats['failed']} failed")
            if stats['simulated'] > 0:
                summary.append(f"    {stats['simulated']} simulated")
        
        summary.append("\nOperations summary:")
        for action, stats in actions.items():
            summary.append(f"  {action.capitalize()}: {stats['total']} total, {stats['successful']} successful, {stats['failed']} failed")
            if stats['simulated'] > 0:
                summary.append(f"    {stats['simulated']} simulated")
            
        summary.append("\nAccounts summary:")
        for account, stats in accounts.items():
            summary.append(f"  {account}: {stats['total']} total, {stats['successful']} successful, {stats['failed']} failed")
            if stats['simulated'] > 0:
                summary.append(f"    {stats['simulated']} simulated")
        
        # Add failure details if any
        failures = [r for r in self.results if r['Status'] == 'Failed']
        if failures:
            summary.append("\nFailure Details:")
            for failure in failures[:5]:  # Show first 5 failures
                summary.append(f"  {failure['ResourceType']} {failure['ResourceId']}: {failure['Error']}")
            if len(failures) > 5:
                summary.append(f"  ... and {len(failures) - 5} more failures")
            
        return "\n".join(summary)

    def generate_html_report(self):
        """Generate an HTML report of results with environment tags and styling.
        
        Returns:
            str: Path to the generated HTML file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/scheduler_report_{timestamp}.html"
            
            # HTML template with Bootstrap styling
            html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AWS Instance Scheduler Report - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem 0; }}
        .summary-card {{ box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075); }}
        .status-success {{ color: #198754; font-weight: bold; }}
        .status-failed {{ color: #dc3545; font-weight: bold; }}
        .status-simulated {{ color: #fd7e14; font-weight: bold; }}
        .resource-ec2 {{ border-left: 4px solid #17a2b8; }}
        .resource-eks {{ border-left: 4px solid #28a745; }}
        .resource-rds {{ border-left: 4px solid #ffc107; }}
        .resource-asg {{ border-left: 4px solid #6f42c1; }}
        .tag-badge {{ background-color: #e9ecef; color: #495057; padding: 0.25rem 0.5rem; border-radius: 0.25rem; font-size: 0.875rem; }}
        .footer {{ background-color: #f8f9fa; border-top: 1px solid #dee2e6; }}
        .timestamp {{ font-family: 'Courier New', monospace; font-size: 0.9rem; }}
        @media (max-width: 768px) {{
            .table-responsive {{ font-size: 0.8rem; }}
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <div class="header">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1 class="mb-0"><i class="fas fa-cloud-server-speed me-2"></i>AWS Instance Scheduler Report</h1>
                    <p class="mb-0 mt-2">Generated on {datetime.now().strftime("%Y-%m-%d at %H:%M:%S UTC")}</p>
                </div>
                <div class="col-md-4 text-md-end">
                    <div class="d-flex justify-content-md-end">
                        <div class="me-3">
                            <i class="fas fa-server fa-2x"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="container my-4">
        <!-- Summary Section -->
        <div class="row mb-4">
            <div class="col-12">
                <h2 class="mb-3"><i class="fas fa-chart-pie me-2"></i>Executive Summary</h2>
            </div>
            
            {self._generate_summary_cards()}
        </div>

        <!-- Filter and Search -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="input-group">
                    <span class="input-group-text"><i class="fas fa-search"></i></span>
                    <input type="text" class="form-control" id="searchInput" placeholder="Search resources...">
                </div>
            </div>
            <div class="col-md-6">
                <select class="form-select" id="filterSelect">
                    <option value="">All Resource Types</option>
                    <option value="EC2">EC2 Instances</option>
                    <option value="ASG">Auto Scaling Groups</option>
                    <option value="EKS">EKS Clusters</option>
                    <option value="Aurora Cluster">Aurora Clusters</option>
                    <option value="RDS Instance">RDS Instances</option>
                </select>
            </div>
        </div>

        <!-- Results Table -->
        <div class="row">
            <div class="col-12">
                <h2 class="mb-3"><i class="fas fa-table me-2"></i>Resource Operations Detail</h2>
                <div class="table-responsive">
                    <table class="table table-hover" id="resultsTable">
                        <thead class="table-dark">
                            <tr>
                                <th><i class="fas fa-cog me-1"></i>Type</th>
                                <th><i class="fas fa-user-circle me-1"></i>Account</th>
                                <th><i class="fas fa-globe me-1"></i>Region</th>
                                <th><i class="fas fa-tag me-1"></i>Resource ID</th>
                                <th><i class="fas fa-id-card me-1"></i>Name</th>
                                <th><i class="fas fa-tags me-1"></i>Environment</th>
                                <th><i class="fas fa-arrow-right me-1"></i>State Change</th>
                                <th><i class="fas fa-play-circle me-1"></i>Action</th>
                                <th><i class="fas fa-clock me-1"></i>Timestamp</th>
                                <th><i class="fas fa-check-circle me-1"></i>Status</th>
                                <th><i class="fas fa-exclamation-triangle me-1"></i>Error</th>
                            </tr>
                        </thead>
                        <tbody>
                            {self._generate_table_rows()}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer mt-5 py-3">
        <div class="container">
            <div class="row">
                <div class="col-md-6">
                    <small class="text-muted">
                        <i class="fas fa-info-circle me-1"></i>
                        Generated by AWS Instance Scheduler v1.3
                    </small>
                </div>
                <div class="col-md-6 text-md-end">
                    <small class="text-muted">
                        <i class="fas fa-download me-1"></i>
                        Available as GitLab CI/CD Artifact
                    </small>
                </div>
            </div>
        </div>
    </footer>

    <!-- JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Search functionality
        document.getElementById('searchInput').addEventListener('keyup', function() {{
            filterTable();
        }});

        // Filter functionality
        document.getElementById('filterSelect').addEventListener('change', function() {{
            filterTable();
        }});

        function filterTable() {{
            const searchValue = document.getElementById('searchInput').value.toLowerCase();
            const filterValue = document.getElementById('filterSelect').value;
            const table = document.getElementById('resultsTable');
            const rows = table.getElementsByTagName('tr');

            for (let i = 1; i < rows.length; i++) {{
                const row = rows[i];
                const cells = row.getElementsByTagName('td');
                let showRow = true;

                // Apply search filter
                if (searchValue) {{
                    let found = false;
                    for (let j = 0; j < cells.length; j++) {{
                        if (cells[j].textContent.toLowerCase().includes(searchValue)) {{
                            found = true;
                            break;
                        }}
                    }}
                    if (!found) showRow = false;
                }}

                // Apply type filter
                if (filterValue && showRow) {{
                    const typeCell = cells[0];
                    if (!typeCell.textContent.includes(filterValue)) {{
                        showRow = false;
                    }}
                }}

                row.style.display = showRow ? '' : 'none';
            }}
        }}

        // Auto-refresh timestamp display
        function updateTimestamps() {{
            const now = new Date();
            document.querySelectorAll('.timestamp').forEach(function(elem) {{
                const timestamp = new Date(elem.getAttribute('data-timestamp'));
                const diffMs = now - timestamp;
                const diffMins = Math.floor(diffMs / 60000);
                
                if (diffMins < 1) {{
                    elem.innerHTML = '<i class="fas fa-clock me-1"></i>Just now';
                }} else if (diffMins < 60) {{
                    elem.innerHTML = `<i class="fas fa-clock me-1"></i>${{diffMins}} minutes ago`;
                }} else {{
                    const diffHours = Math.floor(diffMins / 60);
                    elem.innerHTML = `<i class="fas fa-clock me-1"></i>${{diffHours}} hours ago`;
                }}
            }});
        }}

        // Update timestamps every minute
        setInterval(updateTimestamps, 60000);
        updateTimestamps(); // Initial update
    </script>
</body>
</html>
            """
            
            with open(filename, 'w', encoding='utf-8') as htmlfile:
                htmlfile.write(html_content)
                
            self.logger.info(f"HTML report generated: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Failed to generate HTML report: {str(e)}")
            raise ReportingError(f"Failed to generate HTML report: {str(e)}")

    def _generate_summary_cards(self):
        """Generate HTML summary cards."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['Status'] == 'Success')
        failed = sum(1 for r in self.results if r['Status'] == 'Failed')
        simulated = sum(1 for r in self.results if r['Status'] == 'Simulated')
        
        # Count by resource type
        resource_counts = {}
        for result in self.results:
            resource_type = result['ResourceType']
            resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
        
        # Count by action
        action_counts = {}
        for result in self.results:
            action = result['Action']
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return f"""
        <div class="col-md-3 mb-3">
            <div class="card summary-card h-100">
                <div class="card-body text-center">
                    <h1 class="card-title text-primary">{total}</h1>
                    <p class="card-text">Total Resources</p>
                    <i class="fas fa-server fa-2x text-muted"></i>
                </div>
            </div>
        </div>
        <div class="col-md-3 mb-3">
            <div class="card summary-card h-100">
                <div class="card-body text-center">
                    <h1 class="card-title text-success">{successful}</h1>
                    <p class="card-text">Successful</p>
                    <i class="fas fa-check-circle fa-2x text-success"></i>
                </div>
            </div>
        </div>
        <div class="col-md-3 mb-3">
            <div class="card summary-card h-100">
                <div class="card-body text-center">
                    <h1 class="card-title text-danger">{failed}</h1>
                    <p class="card-text">Failed</p>
                    <i class="fas fa-times-circle fa-2x text-danger"></i>
                </div>
            </div>
        </div>
        <div class="col-md-3 mb-3">
            <div class="card summary-card h-100">
                <div class="card-body text-center">
                    <h1 class="card-title text-warning">{simulated}</h1>
                    <p class="card-text">Simulated</p>
                    <i class="fas fa-flask fa-2x text-warning"></i>
                </div>
            </div>
        </div>
        
        <!-- Resource Type Breakdown -->
        <div class="col-12 mb-3">
            <div class="card summary-card">
                <div class="card-body">
                    <h5 class="card-title"><i class="fas fa-chart-bar me-2"></i>Resource Type Breakdown</h5>
                    <div class="row">
                        {"".join([f'''
                        <div class="col-md-2 col-sm-4 mb-2">
                            <div class="text-center p-2 border rounded">
                                <strong>{count}</strong><br>
                                <small class="text-muted">{resource_type}</small>
                            </div>
                        </div>
                        ''' for resource_type, count in resource_counts.items()])}
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_table_rows(self):
        """Generate HTML table rows for results."""
        rows = []
        
        for result in self.results:
            # Determine resource type CSS class
            resource_class = ""
            if "EC2" in result['ResourceType']:
                resource_class = "resource-ec2"
            elif "EKS" in result['ResourceType']:
                resource_class = "resource-eks"
            elif "RDS" in result['ResourceType'] or "Aurora" in result['ResourceType']:
                resource_class = "resource-rds"
            elif "ASG" in result['ResourceType']:
                resource_class = "resource-asg"
            
            # Format status with appropriate styling
            status_class = ""
            status_icon = ""
            if result['Status'] == 'Success':
                status_class = "status-success"
                status_icon = "fas fa-check-circle"
            elif result['Status'] == 'Failed':
                status_class = "status-failed"
                status_icon = "fas fa-times-circle"
            elif result['Status'] == 'Simulated':
                status_class = "status-simulated"
                status_icon = "fas fa-flask"
            
            # Extract environment tag (assuming it's stored in Details or we'll enhance this)
            environment_tag = self._extract_environment_tag(result)
            
            # Format state change with visual indicator
            state_change = f"""
            <span class="badge bg-light text-dark me-1">{result['PreviousState']}</span>
            <i class="fas fa-arrow-right text-muted mx-1"></i>
            <span class="badge bg-primary">{result['NewState']}</span>
            """
            
            # Format timestamp
            timestamp_formatted = f"""
            <span class="timestamp" data-timestamp="{result['Timestamp']}">
                {result['Timestamp'][:16] if result['Timestamp'] else 'N/A'}
            </span>
            """
            
            row = f"""
            <tr class="{resource_class}">
                <td>
                    <span class="badge bg-secondary">{result['ResourceType']}</span>
                </td>
                <td>
                    <i class="fas fa-user-circle me-1 text-muted"></i>
                    <strong>{result['Account']}</strong>
                </td>
                <td>
                    <i class="fas fa-globe me-1 text-muted"></i>
                    {result['Region']}
                </td>
                <td>
                    <code class="small">{result['ResourceId'][:20]}{'...' if len(result['ResourceId']) > 20 else ''}</code>
                </td>
                <td>
                    <span title="{result['Name']}">
                        {result['Name'][:25]}{'...' if len(result['Name']) > 25 else ''}
                    </span>
                </td>
                <td>{environment_tag}</td>
                <td>{state_change}</td>
                <td>
                    <span class="badge bg-info">{result['Action'].title()}</span>
                </td>
                <td>{timestamp_formatted}</td>
                <td>
                    <span class="{status_class}">
                        <i class="{status_icon} me-1"></i>{result['Status']}
                    </span>
                </td>
                <td>
                    <span class="text-danger small" title="{result['Error']}">
                        {result['Error'][:30]}{'...' if len(result['Error']) > 30 else ''}
                    </span>
                </td>
            </tr>
            """
            rows.append(row)
        
        return "".join(rows)
    
    def _extract_environment_tag(self, result):
        """Extract environment tag from result details."""
        # For now, we'll check the Details field for environment info
        # This can be enhanced to parse actual tag data
        environment = "Unknown"
        
        # Check if environment info is in Details
        details = result.get('Details', '')
        if 'Environment:' in details:
            # Extract environment value
            try:
                env_start = details.find('Environment:') + len('Environment:')
                env_end = details.find(',', env_start)
                if env_end == -1:
                    env_end = len(details)
                environment = details[env_start:env_end].strip()
            except:
                environment = "Unknown"
        
        # Default environment detection based on account name
        account = result.get('Account', '').lower()
        if 'prod' in account:
            environment = "production"
        elif 'staging' in account or 'stage' in account:
            environment = "staging"
        elif 'dev' in account:
            environment = "development"
        elif 'test' in account:
            environment = "testing"
        
        # Return styled environment badge
        env_colors = {
            'production': 'bg-danger',
            'staging': 'bg-warning text-dark',
            'development': 'bg-success',
            'testing': 'bg-info',
            'unknown': 'bg-secondary'
        }
        
        color_class = env_colors.get(environment.lower(), 'bg-secondary')
        
        return f'<span class="badge {color_class}">{environment.title()}</span>'