# Simple usage example
import pandas as pd

def quick_aws_analysis(file_path):
    """Quick and simple AWS cost analysis"""
    
    # Load data
    df = pd.read_excel(file_path)
    
    # Basic analysis
    print("=== ENVIRONMENT SUMMARY ===")
    env_summary = df.groupby('Environment').agg({
        'Monthly Cost': 'sum',
        'Estimated Savings': 'sum',
        'Count': 'sum'
    }).round(2)
    env_summary['Net Cost'] = env_summary['Monthly Cost'] - env_summary['Estimated Savings']
    print(env_summary)
    
    print("\n=== SERVICE SUMMARY ===")
    service_summary = df.groupby('Service').agg({
        'Monthly Cost': 'sum',
        'Estimated Savings': 'sum',
        'Count': 'sum'
    }).round(2)
    service_summary['Net Cost'] = service_summary['Monthly Cost'] - service_summary['Estimated Savings']
    print(service_summary)
    
    print("\n=== COST MATRIX (Environment vs Service) ===")
    cost_matrix = df.pivot_table(values='Monthly Cost', index='Environment', columns='Service', aggfunc='sum', fill_value=0)
    print(cost_matrix)
    
    # Export for Excel charts
    with pd.ExcelWriter('quick_analysis.xlsx') as writer:
        env_summary.to_excel(writer, sheet_name='Environment_Summary')
        service_summary.to_excel(writer, sheet_name='Service_Summary')
        cost_matrix.to_excel(writer, sheet_name='Cost_Matrix')
        df.to_excel(writer, sheet_name='Raw_Data', index=False)
    
    print("\n✅ Results saved to 'quick_analysis.xlsx'")

# Usage
if __name__ == "__main__":
    quick_aws_analysis('your_file.xlsx')  # Replace with your file path