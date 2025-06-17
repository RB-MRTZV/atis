#!/usr/bin/env python3
import os
import json
import glob
from datetime import datetime

def generate_manifest():
    """Generate a manifest file listing all available account reports"""
    data_dir = 'reports/data'
    manifest = {
        'generated_at': datetime.utcnow().isoformat(),
        'accounts': []
    }
    
    if not os.path.exists(data_dir):
        print(f"Data directory {data_dir} does not exist")
        return
    
    # Find all JSON files in the data directory
    json_files = glob.glob(os.path.join(data_dir, '*.json'))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
            account_info = {
                'account_id': data.get('account_id', 'unknown'),
                'account_name': data.get('account_name', f"Account {data.get('account_id', 'unknown')}"),
                'region': data.get('region', 'unknown'),
                'scan_time': data.get('scan_time'),
                'estimation_time': data.get('estimation_time'),
                'file_name': os.path.basename(json_file),
                'total_monthly_cost': sum(item.get('monthly_cost', 0) for item in data.get('detailed', [])),
                'resource_count': len(data.get('detailed', []))
            }
            
            manifest['accounts'].append(account_info)
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
    
    # Sort accounts by total cost (descending)
    manifest['accounts'].sort(key=lambda x: x['total_monthly_cost'], reverse=True)
    
    # Save manifest
    manifest_file = os.path.join(data_dir, 'manifest.json')
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Generated manifest with {len(manifest['accounts'])} accounts")
    print(f"Manifest saved to: {manifest_file}")
    
    return manifest

if __name__ == "__main__":
    generate_manifest()