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
    """Handles reporting of RDS and Aurora operations."""
    
    def __init__(self, reports_dir="reports"):
        """Initialize the reporter.
        
        Args:
            reports_dir (str): Directory to save reports
        """
        self.logger = logging.getLogger(__name__)
        self.reports_dir = reports_dir
        self.results = []
        
        # Create reports directory if it doesn't exist
        if not os.path.exists(reports_dir):
            try:
                os.makedirs(reports_dir)
                self.logger.info(f"Created reports directory: {reports_dir}")
            except Exception as e:
                self.logger.error(f"Failed to create reports directory: {str(e)}")
                raise ReportingError(f"Failed to create reports directory: {str(e)}")
    
    def add_result(self, account, region, resource_type, resource_id, previous_state, new_state, action, timestamp, status, error=None):
        """Add a result to the report.
        
        Args:
            account (str): Account name
            region (str): AWS region
            resource_type (str): Type of resource (Aurora Cluster, RDS Instance)
            resource_id (str): Resource identifier
            previous_state (str): Previous state
            new_state (str): New state
            action (str): Action performed
            timestamp (str): Timestamp of action
            status (str): Status of action
            error (str, optional): Error message if any
        """
        result = {
            'Account': account,
            'Region': region,
            'ResourceType': resource_type,
            'ResourceId': resource_id,
            'PreviousState': previous_state,
            'NewState': new_state,
            'Action': action,
            'Timestamp': timestamp,
            'Status': status,
            'Error': error or ''
        }
        self.results.append(result)
        self.logger.debug(f"Added result: {resource_type} {resource_id} - {action} - {status}")
    
    def generate_csv_report(self):
        """Generate CSV report.
        
        Returns:
            str: Path to generated CSV file
        """
        try:
            if not self.results:
                self.logger.warning("No results to generate CSV report")
                return None
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/rds_scheduler_report_{timestamp}.csv"
            
            fieldnames = ['Account', 'Region', 'ResourceType', 'ResourceId', 'PreviousState', 'NewState', 'Action', 'Timestamp', 'Status', 'Error']
            
            with open(filename, 'w', newline='') as csvfile:
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
        """Generate JSON report.
        
        Returns:
            str: Path to generated JSON file
        """
        try:
            if not self.results:
                self.logger.warning("No results to generate JSON report")
                return None
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/rds_scheduler_report_{timestamp}.json"
            
            report_data = {
                'generated_at': datetime.now().isoformat(),
                'total_results': len(self.results),
                'summary': self._generate_summary_stats(),
                'results': self.results
            }
            
            with open(filename, 'w') as jsonfile:
                json.dump(report_data, jsonfile, indent=2)
                
            self.logger.info(f"JSON report generated: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Failed to generate JSON report: {str(e)}")
            raise ReportingError(f"Failed to generate JSON report: {str(e)}")
    
    def generate_table_report(self):
        """Generate table report.
        
        Returns:
            str: Table as string
        """
        try:
            if not self.results:
                return "No results to display"
                
            headers = ['Account', 'Region', 'Resource Type', 'Resource ID', 'Previous State', 'New State', 'Action', 'Status', 'Error']
            rows = []
            
            for result in self.results:
                # Truncate long resource IDs for better table formatting
                resource_id = result['ResourceId']
                if len(resource_id) > 25:
                    resource_id = resource_id[:22] + "..."
                    
                # Truncate error messages
                error = result['Error']
                if len(error) > 30:
                    error = error[:27] + "..."
                
                rows.append([
                    result['Account'],
                    result['Region'],
                    result['ResourceType'],
                    resource_id,
                    result['PreviousState'],
                    result['NewState'],
                    result['Action'],
                    result['Status'],
                    error
                ])
            
            table = tabulate(rows, headers=headers, tablefmt='grid')
            
            # Save table to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/rds_scheduler_report_{timestamp}.txt"
            
            with open(filename, 'w') as txtfile:
                txtfile.write(f"RDS Scheduler Report - Generated at {datetime.now().isoformat()}\n")
                txtfile.write("=" * 80 + "\n\n")
                txtfile.write(self._generate_summary_text())
                txtfile.write("\n\nDetailed Results:\n")
                txtfile.write(table)
                
            self.logger.info(f"Table report generated: {filename}")
            return table
            
        except Exception as e:
            self.logger.error(f"Failed to generate table report: {str(e)}")
            raise ReportingError(f"Failed to generate table report: {str(e)}")
    
    def generate_summary(self):
        """Generate a summary of results.
        
        Returns:
            str: Summary text
        """
        if not self.results:
            return "No operations performed"
            
        return self._generate_summary_text()
    
    def _generate_summary_stats(self):
        """Generate summary statistics.
        
        Returns:
            dict: Summary statistics
        """
        if not self.results:
            return {}
            
        stats = {
            'total_operations': len(self.results),
            'successful_operations': len([r for r in self.results if r['Status'] in ['Success', 'Verified', 'DryRun']]),
            'failed_operations': len([r for r in self.results if r['Status'] == 'Failed']),
            'by_resource_type': {},
            'by_action': {},
            'by_account': {},
            'by_region': {}
        }
        
        for result in self.results:
            # Count by resource type
            resource_type = result['ResourceType']
            if resource_type not in stats['by_resource_type']:
                stats['by_resource_type'][resource_type] = 0
            stats['by_resource_type'][resource_type] += 1
            
            # Count by action
            action = result['Action']
            if action not in stats['by_action']:
                stats['by_action'][action] = 0
            stats['by_action'][action] += 1
            
            # Count by account
            account = result['Account']
            if account not in stats['by_account']:
                stats['by_account'][account] = 0
            stats['by_account'][account] += 1
            
            # Count by region
            region = result['Region']
            if region not in stats['by_region']:
                stats['by_region'][region] = 0
            stats['by_region'][region] += 1
        
        return stats
    
    def _generate_summary_text(self):
        """Generate summary text.
        
        Returns:
            str: Summary as text
        """
        stats = self._generate_summary_stats()
        
        if not stats:
            return "No operations performed"
        
        summary_lines = [
            f"Total Operations: {stats['total_operations']}",
            f"Successful: {stats['successful_operations']}",
            f"Failed: {stats['failed_operations']}",
            "",
            "By Resource Type:"
        ]
        
        for resource_type, count in stats['by_resource_type'].items():
            summary_lines.append(f"  {resource_type}: {count}")
        
        summary_lines.append("")
        summary_lines.append("By Action:")
        for action, count in stats['by_action'].items():
            summary_lines.append(f"  {action}: {count}")
        
        summary_lines.append("")
        summary_lines.append("By Account:")
        for account, count in stats['by_account'].items():
            summary_lines.append(f"  {account}: {count}")
        
        return "\n".join(summary_lines)

    def generate_html_report(self):
        """Generate an HTML report of results with environment tags and styling.
        
        Returns:
            str: Path to the generated HTML file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/rds_scheduler_report_{timestamp}.html"
            
            # HTML template with Bootstrap styling
            html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RDS Scheduler Report - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        .header {{ background: linear-gradient(135deg, #ffc107 0%, #fd7e14 100%); color: white; padding: 2rem 0; }}
        .summary-card {{ box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075); }}
        .status-success {{ color: #198754; font-weight: bold; }}
        .status-failed {{ color: #dc3545; font-weight: bold; }}
        .status-simulated {{ color: #fd7e14; font-weight: bold; }}
        .resource-aurora {{ border-left: 4px solid #ffc107; }}
        .resource-rds {{ border-left: 4px solid #fd7e14; }}
        .footer {{ background-color: #f8f9fa; border-top: 1px solid #dee2e6; }}
        .timestamp {{ font-family: 'Courier New', monospace; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1 class="mb-0"><i class="fas fa-database me-2"></i>RDS Scheduler Report</h1>
                    <p class="mb-0 mt-2">Generated on {datetime.now().strftime("%Y-%m-%d at %H:%M:%S UTC")}</p>
                </div>
                <div class="col-md-4 text-md-end">
                    <i class="fas fa-server fa-3x"></i>
                </div>
            </div>
        </div>
    </div>

    <div class="container my-4">
        {self._generate_rds_summary_cards()}
        
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
                    <option value="Aurora Cluster">Aurora Clusters</option>
                    <option value="RDS Instance">RDS Instances</option>
                </select>
            </div>
        </div>

        <div class="row">
            <div class="col-12">
                <h2 class="mb-3"><i class="fas fa-table me-2"></i>Database Operations Detail</h2>
                <div class="table-responsive">
                    <table class="table table-hover" id="resultsTable">
                        <thead class="table-dark">
                            <tr>
                                <th><i class="fas fa-cog me-1"></i>Type</th>
                                <th><i class="fas fa-user-circle me-1"></i>Account</th>
                                <th><i class="fas fa-globe me-1"></i>Region</th>
                                <th><i class="fas fa-tag me-1"></i>Resource ID</th>
                                <th><i class="fas fa-tags me-1"></i>Environment</th>
                                <th><i class="fas fa-arrow-right me-1"></i>State Change</th>
                                <th><i class="fas fa-play-circle me-1"></i>Action</th>
                                <th><i class="fas fa-clock me-1"></i>Timestamp</th>
                                <th><i class="fas fa-check-circle me-1"></i>Status</th>
                                <th><i class="fas fa-exclamation-triangle me-1"></i>Error</th>
                            </tr>
                        </thead>
                        <tbody>
                            {self._generate_rds_table_rows()}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <footer class="footer mt-5 py-3">
        <div class="container">
            <div class="row">
                <div class="col-md-6">
                    <small class="text-muted">
                        <i class="fas fa-info-circle me-1"></i>
                        Generated by RDS Scheduler v1.3
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

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Search and filter functionality
        document.getElementById('searchInput').addEventListener('keyup', function() {{ filterTable(); }});
        document.getElementById('filterSelect').addEventListener('change', function() {{ filterTable(); }});

        function filterTable() {{
            const searchValue = document.getElementById('searchInput').value.toLowerCase();
            const filterValue = document.getElementById('filterSelect').value;
            const table = document.getElementById('resultsTable');
            const rows = table.getElementsByTagName('tr');

            for (let i = 1; i < rows.length; i++) {{
                const row = rows[i];
                const cells = row.getElementsByTagName('td');
                let showRow = true;

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

                if (filterValue && showRow) {{
                    const typeCell = cells[0];
                    if (!typeCell.textContent.includes(filterValue)) {{
                        showRow = false;
                    }}
                }}

                row.style.display = showRow ? '' : 'none';
            }}
        }}
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

    def _generate_rds_summary_cards(self):
        """Generate RDS-specific summary cards."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['Status'] == 'Success')
        failed = sum(1 for r in self.results if r['Status'] == 'Failed')
        simulated = sum(1 for r in self.results if r['Status'] == 'Simulated')
        
        aurora_count = sum(1 for r in self.results if 'Aurora' in r['ResourceType'])
        rds_count = sum(1 for r in self.results if 'RDS' in r['ResourceType'])
        
        return f"""
        <div class="row mb-4">
            <div class="col-12"><h2><i class="fas fa-chart-pie me-2"></i>Summary</h2></div>
            <div class="col-md-2 mb-3">
                <div class="card summary-card h-100">
                    <div class="card-body text-center">
                        <h1 class="text-primary">{total}</h1>
                        <p>Total</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2 mb-3">
                <div class="card summary-card h-100">
                    <div class="card-body text-center">
                        <h1 class="text-success">{successful}</h1>
                        <p>Success</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2 mb-3">
                <div class="card summary-card h-100">
                    <div class="card-body text-center">
                        <h1 class="text-danger">{failed}</h1>
                        <p>Failed</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2 mb-3">
                <div class="card summary-card h-100">
                    <div class="card-body text-center">
                        <h1 class="text-warning">{simulated}</h1>
                        <p>Simulated</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2 mb-3">
                <div class="card summary-card h-100">
                    <div class="card-body text-center">
                        <h1 class="text-info">{aurora_count}</h1>
                        <p>Aurora</p>
                    </div>
                </div>
            </div>
            <div class="col-md-2 mb-3">
                <div class="card summary-card h-100">
                    <div class="card-body text-center">
                        <h1 class="text-secondary">{rds_count}</h1>
                        <p>RDS</p>
                    </div>
                </div>
            </div>
        </div>
        """

    def _generate_rds_table_rows(self):
        """Generate HTML table rows for RDS results."""
        rows = []
        
        for result in self.results:
            resource_class = "resource-aurora" if "Aurora" in result['ResourceType'] else "resource-rds"
            
            status_class = ""
            status_icon = ""
            if result['Status'] == 'Success':
                status_class, status_icon = "status-success", "fas fa-check-circle"
            elif result['Status'] == 'Failed':
                status_class, status_icon = "status-failed", "fas fa-times-circle"
            elif result['Status'] == 'Simulated':
                status_class, status_icon = "status-simulated", "fas fa-flask"
            
            environment_tag = self._extract_rds_environment_tag(result)
            
            state_change = f"""
            <span class="badge bg-light text-dark me-1">{result['PreviousState']}</span>
            <i class="fas fa-arrow-right text-muted mx-1"></i>
            <span class="badge bg-primary">{result['NewState']}</span>
            """
            
            timestamp_formatted = result['Timestamp'][:16] if result['Timestamp'] else 'N/A'
            
            row = f"""
            <tr class="{resource_class}">
                <td><span class="badge bg-secondary">{result['ResourceType']}</span></td>
                <td><strong>{result['Account']}</strong></td>
                <td>{result['Region']}</td>
                <td><code class="small">{result['ResourceId'][:25]}{'...' if len(result['ResourceId']) > 25 else ''}</code></td>
                <td>{environment_tag}</td>
                <td>{state_change}</td>
                <td><span class="badge bg-info">{result['Action'].title()}</span></td>
                <td><span class="timestamp">{timestamp_formatted}</span></td>
                <td><span class="{status_class}"><i class="{status_icon} me-1"></i>{result['Status']}</span></td>
                <td><span class="text-danger small">{result['Error'][:30]}{'...' if len(result['Error']) > 30 else ''}</span></td>
            </tr>
            """
            rows.append(row)
        
        return "".join(rows)
    
    def _extract_rds_environment_tag(self, result):
        """Extract environment tag for RDS resources."""
        environment = "Unknown"
        
        # Check account name for environment
        account = result.get('Account', '').lower()
        if 'prod' in account:
            environment = "production"
        elif 'staging' in account or 'stage' in account:
            environment = "staging"
        elif 'dev' in account:
            environment = "development"
        elif 'test' in account:
            environment = "testing"
        
        env_colors = {
            'production': 'bg-danger',
            'staging': 'bg-warning text-dark',
            'development': 'bg-success',
            'testing': 'bg-info',
            'unknown': 'bg-secondary'
        }
        
        color_class = env_colors.get(environment.lower(), 'bg-secondary')
        return f'<span class="badge {color_class}">{environment.title()}</span>' 