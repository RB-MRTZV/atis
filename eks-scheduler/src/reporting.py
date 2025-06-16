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
    """Handles reporting of EKS cluster operations."""
    
    def __init__(self, reports_dir="reports"):
        self.logger = logging.getLogger(__name__)
        self.reports_dir = reports_dir
        self.results = []
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
    
    def add_result(self, account, region, cluster_name, previous_state, new_state, action, timestamp, status, error=None):
        result = {
            'Account': account,
            'Region': region,
            'ClusterName': cluster_name,
            'PreviousState': previous_state,
            'NewState': new_state,
            'Action': action,
            'Timestamp': timestamp,
            'Status': status,
            'Error': error or ''
        }
        self.results.append(result)
    
    def generate_csv_report(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/eks_scheduler_report_{timestamp}.csv"
            with open(filename, 'w', newline='') as csvfile:
                fieldnames = ['Account', 'Region', 'ClusterName', 'PreviousState', 'NewState', 'Action', 'Timestamp', 'Status', 'Error']
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
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/eks_scheduler_report_{timestamp}.json"
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
        try:
            headers = ['Account', 'Region', 'Cluster Name', 'Previous State', 'New State', 'Action', 'Timestamp', 'Status', 'Error']
            rows = []
            for result in self.results:
                rows.append([
                    result['Account'],
                    result['Region'],
                    result['ClusterName'],
                    result['PreviousState'],
                    result['NewState'],
                    result['Action'],
                    result['Timestamp'],
                    result['Status'],
                    result['Error']
                ])
            table = tabulate(rows, headers=headers, tablefmt='grid')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.reports_dir}/eks_scheduler_report_{timestamp}.txt"
            with open(filename, 'w') as txtfile:
                txtfile.write(table)
            self.logger.info(f"Table report generated: {filename}")
            return table
        except Exception as e:
            self.logger.error(f"Failed to generate table report: {str(e)}")
            raise ReportingError(f"Failed to generate table report: {str(e)}") 