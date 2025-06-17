#!/usr/bin/env python3
"""
AWS Cost Analyzer - Main orchestration script
Coordinates scanning, cost estimation, and report generation for AWS accounts
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Import our modules
from aws_scanner import AWSResourceScanner
from cost_estimator import CostEstimator
from report_generator import ReportGenerator
from generate_manifest import generate_manifest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AWSCostAnalyzer:
    def __init__(self, region='ap-southeast-2', account_name=None):
        self.region = region
        self.account_name = account_name
        
        # Initialize components
        self.scanner = AWSResourceScanner(region=region)
        self.estimator = CostEstimator()
        
        # Ensure output directories exist
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            'reports',
            'reports/data', 
            'reports/csv',
            'logs'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def run_full_analysis(self):
        """Run complete cost analysis workflow"""
        logger.info("Starting AWS cost analysis workflow")
        
        try:
            # Step 1: Scan AWS resources
            logger.info("Step 1: Scanning AWS resources...")
            scan_results = self.scanner.scan_all_resources()
            
            if not scan_results:
                raise Exception("Failed to scan AWS resources")
            
            account_id = scan_results.get('account_id', 'unknown')
            
            # Add account name if provided
            if self.account_name:
                scan_results['account_name'] = self.account_name
            
            # Save scan results with account-specific filename
            scan_file = f'aws_scan_results_{account_id}.json'
            with open(scan_file, 'w') as f:
                json.dump(scan_results, f, indent=2, default=str)
            logger.info(f"Scan results saved to: {scan_file}")
            
            # Step 2: Estimate costs
            logger.info("Step 2: Estimating costs...")
            results, detailed_results = self.estimator.estimate_all_costs(scan_results)
            
            # Step 3: Generate reports
            logger.info("Step 3: Generating reports...")
            report_data = {
                'summary': self.estimator.get_summary(),
                'detailed': detailed_results,
                'metadata': results['metadata']
            }
            
            # Save estimation results
            estimation_file = f'cost_estimation_results_{account_id}.json'
            with open(estimation_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            logger.info(f"Cost estimation saved to: {estimation_file}")
            
            # Generate all report formats
            generator = ReportGenerator(estimation_file)
            
            # Generate CSV reports
            generator.generate_csv_report()
            logger.info("CSV reports generated")
            
            # Generate HTML report
            generator.generate_html_report()
            logger.info("HTML report generated")
            
            # Generate JSON data for dashboard
            generator.generate_json_data()
            logger.info("JSON data file generated")
            
            # Step 4: Update manifest
            logger.info("Step 4: Updating manifest...")
            generate_manifest()
            
            # Summary
            summary = self.get_analysis_summary(report_data)
            logger.info("Analysis completed successfully!")
            logger.info(f"Account: {account_id} ({self.account_name or 'No name provided'})")
            logger.info(f"Region: {self.region}")
            logger.info(f"Total monthly cost: ${summary['total_monthly_cost']:.2f}")
            logger.info(f"Total resources: {summary['total_resources']}")
            logger.info(f"Services: {', '.join(summary['services'])}")
            
            return {
                'success': True,
                'account_id': account_id,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_analysis_summary(self, report_data):
        """Extract key metrics from report data"""
        detailed_data = report_data.get('detailed', [])
        
        total_monthly_cost = sum(item.get('monthly_cost', 0) for item in detailed_data)
        total_resources = len(detailed_data)
        services = list(set(item.get('service') for item in detailed_data if item.get('service')))
        environments = list(set(item.get('environment') for item in detailed_data if item.get('environment')))
        
        return {
            'total_monthly_cost': total_monthly_cost,
            'total_resources': total_resources,
            'services': services,
            'environments': environments
        }

def main():
    parser = argparse.ArgumentParser(description='AWS Cost Analyzer')
    parser.add_argument('--region', default='ap-southeast-2', 
                       help='AWS region to analyze (default: ap-southeast-2)')
    parser.add_argument('--account-name', 
                       help='Friendly name for the AWS account')
    parser.add_argument('--generate-manifest-only', action='store_true',
                       help='Only generate manifest file from existing data')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle manifest-only generation
    if args.generate_manifest_only:
        logger.info("Generating manifest file only...")
        try:
            manifest = generate_manifest()
            if manifest:
                print("\nManifest generated successfully!")
                print(f"Found {len(manifest['accounts'])} accounts:")
                for account in manifest['accounts']:
                    print(f"  - {account['account_name']} ({account['account_id']}) - ${account['total_monthly_cost']:.2f}/month")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to generate manifest: {e}")
            sys.exit(1)
    
    # Run full analysis
    analyzer = AWSCostAnalyzer(region=args.region, account_name=args.account_name)
    result = analyzer.run_full_analysis()
    
    if result['success']:
        print("\n" + "="*60)
        print("AWS COST ANALYSIS COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"Account ID: {result['account_id']}")
        print(f"Region: {args.region}")
        if args.account_name:
            print(f"Account Name: {args.account_name}")
        print(f"Total Monthly Cost: ${result['summary']['total_monthly_cost']:.2f}")
        print(f"Total Resources: {result['summary']['total_resources']}")
        print(f"Services: {', '.join(result['summary']['services'])}")
        print(f"Environments: {', '.join(result['summary']['environments'])}")
        print("\nTo view the multi-account dashboard, open: dashboard.html")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("AWS COST ANALYSIS FAILED")
        print("="*60)
        print(f"Error: {result['error']}")
        print("="*60)
        sys.exit(1)

if __name__ == "__main__":
    main()