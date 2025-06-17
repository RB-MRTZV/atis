#!/usr/bin/env python3
"""
AWS Cost Analyzer - Main orchestrator script
Scans AWS resources and generates cost estimation reports
"""

import argparse
import logging
import sys
from aws_scanner import AWSResourceScanner
from cost_estimator import CostEstimator
from report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='AWS Cost Analyzer - Scan resources and estimate costs')
    parser.add_argument('--region', default='ap-southeast-2', help='AWS region to scan (default: ap-southeast-2)')
    parser.add_argument('--config', default='cost_config.json', help='Cost configuration file (default: cost_config.json)')
    parser.add_argument('--output-prefix', default='cost_report', help='Output file prefix (default: cost_report)')
    parser.add_argument('--skip-scan', action='store_true', help='Skip scanning and use existing scan results')
    parser.add_argument('--skip-html', action='store_true', help='Skip HTML report generation')
    parser.add_argument('--skip-csv', action='store_true', help='Skip CSV report generation')
    
    args = parser.parse_args()
    
    try:
        # Stage 1: Scan AWS resources
        if not args.skip_scan:
            logger.info("=== Stage 1: Scanning AWS Resources ===")
            scanner = AWSResourceScanner(region=args.region)
            scan_results = scanner.scan_all_resources()
        else:
            logger.info("Skipping scan stage, using existing scan results...")
            import json
            with open('aws_scan_results.json', 'r') as f:
                scan_results = json.load(f)
        
        # Stage 2: Estimate costs
        logger.info("\n=== Stage 2: Estimating Costs ===")
        estimator = CostEstimator(config_file=args.config)
        results, detailed_results = estimator.estimate_all_costs(scan_results)
        
        # Save estimation results
        import json
        with open('cost_estimation_results.json', 'w') as f:
            json.dump({
                'summary': estimator.get_summary(),
                'detailed': detailed_results,
                'metadata': results['metadata']
            }, f, indent=2)
        
        # Stage 3: Generate reports
        logger.info("\n=== Stage 3: Generating Reports ===")
        generator = ReportGenerator()
        
        if not args.skip_csv:
            csv_file = f"{args.output_prefix}.csv"
            generator.generate_csv_report(output_file=csv_file)
        
        if not args.skip_html:
            html_file = f"{args.output_prefix}.html"
            generator.generate_html_report(output_file=html_file)
        
        # Print summary to console
        logger.info("\n=== Cost Summary ===")
        summary = estimator.get_summary()
        
        print("\nCost Summary by Service and Environment:")
        print("-" * 80)
        print(f"{'Service':<10} {'Environment':<15} {'Resources':<10} {'Daily Cost':<15} {'Monthly Cost':<15}")
        print("-" * 80)
        
        for item in summary:
            if item['service'] != 'TOTAL':
                print(f"{item['service']:<10} {item['environment']:<15} {item['resource_count']:<10} "
                      f"${item['daily_cost']:<14.2f} ${item['monthly_cost']:<14.2f}")
        
        print("-" * 80)
        total = next(item for item in summary if item['service'] == 'TOTAL')
        print(f"{'TOTAL':<10} {'ALL':<15} {total['resource_count']:<10} "
              f"${total['daily_cost']:<14.2f} ${total['monthly_cost']:<14.2f}")
        
        logger.info("\n✅ AWS Cost Analysis completed successfully!")
        logger.info(f"Reports generated: {args.output_prefix}.csv, {args.output_prefix}_summary.csv, {args.output_prefix}.html")
        
    except Exception as e:
        logger.error(f"Error during cost analysis: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()