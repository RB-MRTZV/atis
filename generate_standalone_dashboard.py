#!/usr/bin/env python3
"""
Generate a standalone dashboard HTML file with all account data embedded.
This avoids CORS issues when opening the file directly without a web server.
"""

import json
import os
from pathlib import Path
from datetime import datetime

def generate_standalone_dashboard():
    """Generate a standalone dashboard with embedded data"""
    
    # Load manifest
    manifest_path = Path('reports/data/manifest.json')
    if not manifest_path.exists():
        print("Error: Manifest file not found. Run aws_cost_analyzer.py first.")
        return
    
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    
    # Load all account data (excluding invalid entries)
    all_account_data = {}
    for account in manifest['accounts']:
        account_id = account['account_id']
        # Skip invalid entries
        if account_id == 'unknown' or account['file_name'] == 'manifest.json':
            continue
            
        data_file = Path(f"reports/data/{account['file_name']}")
        if data_file.exists():
            with open(data_file, 'r') as f:
                account_data = json.load(f)
                all_account_data[account_id] = account_data
    
    # Read the original dashboard HTML template
    dashboard_path = Path('dashboard.html')
    if not dashboard_path.exists():
        print("Error: dashboard.html not found.")
        return
    
    with open(dashboard_path, 'r') as f:
        dashboard_html = f.read()
    
    # Find where to replace the embedded data
    start_marker = '// Embedded data (eliminates CORS issues)'
    end_marker = '// Global variables'
    
    start_idx = dashboard_html.find(start_marker)
    end_idx = dashboard_html.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print("Error: Could not find data injection points in dashboard.html")
        return
    
    # Filter manifest to exclude invalid entries
    filtered_manifest = {
        'generated_at': manifest['generated_at'],
        'accounts': [account for account in manifest['accounts'] 
                    if account['account_id'] != 'unknown' and account['file_name'] != 'manifest.json']
    }
    
    # Create the embedded data section
    embedded_data_section = f"""// Embedded data (eliminates CORS issues)
        const EMBEDDED_MANIFEST = {json.dumps(filtered_manifest)};
        
        const EMBEDDED_ACCOUNT_DATA = {json.dumps(all_account_data)};
        
        """
    
    # Replace the embedded data section
    modified_html = (
        dashboard_html[:start_idx] + 
        embedded_data_section + 
        dashboard_html[end_idx:]
    )
    
    # Save the standalone dashboard
    output_path = Path('dashboard_standalone.html')
    with open(output_path, 'w') as f:
        f.write(modified_html)
    
    print(f"Standalone dashboard created: {output_path}")
    print(f"Embedded data for {len(all_account_data)} accounts")
    print("You can now open dashboard_standalone.html directly in your browser without a web server.")

if __name__ == "__main__":
    generate_standalone_dashboard()