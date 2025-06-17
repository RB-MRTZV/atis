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
    
    # Load all account data
    all_account_data = []
    for account in manifest['accounts']:
        data_file = Path(f"reports/data/{account['file_name']}")
        if data_file.exists():
            with open(data_file, 'r') as f:
                account_data = json.load(f)
                all_account_data.append(account_data)
    
    # Read the original dashboard HTML
    dashboard_path = Path('dashboard.html')
    if not dashboard_path.exists():
        print("Error: dashboard.html not found.")
        return
    
    with open(dashboard_path, 'r') as f:
        dashboard_html = f.read()
    
    # Find where to inject the data (before the script that loads data)
    inject_point = dashboard_html.find('async function discoverAccountFiles()')
    if inject_point == -1:
        print("Error: Could not find injection point in dashboard.html")
        return
    
    # Create the embedded data script
    embedded_data_script = f"""
    <script>
        // Embedded data - no external files needed
        const EMBEDDED_MANIFEST = {json.dumps(manifest, indent=2)};
        const EMBEDDED_ACCOUNT_DATA = {json.dumps(all_account_data, indent=2)};
        
        // Override the data loading functions
        async function discoverAccountFiles() {{
            return EMBEDDED_MANIFEST.accounts.map(account => account.file_name);
        }}
        
        async function loadAccountData(accountFiles) {{
            const data = [];
            for (const accountData of EMBEDDED_ACCOUNT_DATA) {{
                data.push({{
                    account_id: accountData.account_id,
                    account_name: accountData.account_name || accountData.account_id,
                    region: accountData.region,
                    total_monthly_cost: accountData.total_monthly_cost,
                    detailed: accountData.detailed,
                    summary: accountData.summary
                }});
            }}
            return data;
        }}
        
        // Original functions follow below (they will be overridden by the above)
    </script>
    <script>
"""
    
    # Insert the embedded data before the original script
    script_start = dashboard_html.rfind('<script>', 0, inject_point)
    modified_html = (
        dashboard_html[:script_start] + 
        embedded_data_script + 
        dashboard_html[script_start+8:]  # Skip the original <script> tag
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