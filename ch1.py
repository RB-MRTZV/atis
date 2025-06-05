import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

class AWSCostAnalyzer:
    def __init__(self, file_path):
        """
        Initialize the AWS Cost Analyzer
        
        Args:
            file_path (str): Path to the Excel file containing cost data
        """
        self.file_path = file_path
        self.df = None
        self.analysis_results = {}
        
    def load_data(self, sheet_name=0):
        """Load and validate data from Excel file"""
        try:
            self.df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            print(f"✓ Data loaded successfully: {len(self.df)} rows")
            
            # Expected columns
            expected_columns = ['Environment', 'Service', 'Instance Type', 'Count', 
                              'Cost/Instance', 'Monthly Cost', 'Estimated Savings']
            
            # Validate columns
            missing_columns = set(expected_columns) - set(self.df.columns)
            if missing_columns:
                print(f"⚠ Warning: Missing columns: {missing_columns}")
            
            # Display data info
            print(f"✓ Columns found: {list(self.df.columns)}")
            print(f"✓ Shape: {self.df.shape}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error loading data: {e}")
            return False
    
    def clean_and_validate_data(self):
        """Clean and validate the loaded data"""
        if self.df is None:
            print("✗ No data loaded")
            return False
            
        # Remove any completely empty rows
        initial_rows = len(self.df)
        self.df = self.df.dropna(how='all')
        
        # Convert numeric columns
        numeric_columns = ['Count', 'Cost/Instance', 'Monthly Cost', 'Estimated Savings']
        for col in numeric_columns:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        
        # Fill NaN values in savings with 0
        if 'Estimated Savings' in self.df.columns:
            self.df['Estimated Savings'] = self.df['Estimated Savings'].fillna(0)
        
        # Add calculated fields
        self.df['Net Cost After Savings'] = self.df['Monthly Cost'] - self.df['Estimated Savings']
        self.df['Savings Percentage'] = (self.df['Estimated Savings'] / self.df['Monthly Cost'] * 100).round(2)
        self.df['Cost Per Instance Actual'] = (self.df['Monthly Cost'] / self.df['Count']).round(2)
        
        # Data quality checks
        print(f"✓ Data cleaned: {initial_rows - len(self.df)} empty rows removed")
        print(f"✓ Added calculated fields: Net Cost After Savings, Savings Percentage, Cost Per Instance Actual")
        
        # Check for data quality issues
        quality_issues = []
        if (self.df['Monthly Cost'] < 0).any():
            quality_issues.append("Negative monthly costs found")
        if (self.df['Count'] <= 0).any():
            quality_issues.append("Zero or negative instance counts found")
            
        if quality_issues:
            print(f"⚠ Data quality issues: {quality_issues}")
        else:
            print("✓ Data quality checks passed")
            
        return True
    
    def analyze_by_environment(self):
        """Analyze costs by environment"""
        env_analysis = self.df.groupby('Environment').agg({
            'Monthly Cost': ['sum', 'mean', 'count'],
            'Estimated Savings': 'sum',
            'Count': 'sum',
            'Net Cost After Savings': 'sum'
        }).round(2)
        
        # Flatten column names
        env_analysis.columns = ['Total Monthly Cost', 'Average Monthly Cost', 'Number of Services', 
                               'Total Estimated Savings', 'Total Instance Count', 'Net Cost After Savings']
        
        # Add percentage calculations
        total_cost = env_analysis['Total Monthly Cost'].sum()
        env_analysis['Cost Percentage'] = (env_analysis['Total Monthly Cost'] / total_cost * 100).round(2)
        env_analysis['Savings Rate %'] = (env_analysis['Total Estimated Savings'] / env_analysis['Total Monthly Cost'] * 100).round(2)
        
        # Sort by total cost descending
        env_analysis = env_analysis.sort_values('Total Monthly Cost', ascending=False)
        
        self.analysis_results['environment'] = env_analysis
        print("✓ Environment analysis completed")
        return env_analysis
    
    def analyze_by_service(self):
        """Analyze costs by service type"""
        service_analysis = self.df.groupby('Service').agg({
            'Monthly Cost': ['sum', 'mean', 'count'],
            'Estimated Savings': 'sum',
            'Count': 'sum',
            'Net Cost After Savings': 'sum',
            'Cost/Instance': 'mean'
        }).round(2)
        
        # Flatten column names
        service_analysis.columns = ['Total Monthly Cost', 'Average Monthly Cost', 'Number of Instances Types', 
                                   'Total Estimated Savings', 'Total Instance Count', 'Net Cost After Savings',
                                   'Average Cost Per Instance']
        
        # Add percentage calculations
        total_cost = service_analysis['Total Monthly Cost'].sum()
        service_analysis['Cost Percentage'] = (service_analysis['Total Monthly Cost'] / total_cost * 100).round(2)
        service_analysis['Savings Rate %'] = (service_analysis['Total Estimated Savings'] / service_analysis['Total Monthly Cost'] * 100).round(2)
        
        # Sort by total cost descending
        service_analysis = service_analysis.sort_values('Total Monthly Cost', ascending=False)
        
        self.analysis_results['service'] = service_analysis
        print("✓ Service analysis completed")
        return service_analysis
    
    def analyze_environment_service_matrix(self):
        """Create environment x service cost matrix"""
        # Pivot table for monthly costs
        cost_matrix = self.df.pivot_table(
            values='Monthly Cost', 
            index='Environment', 
            columns='Service', 
            aggfunc='sum', 
            fill_value=0
        ).round(2)
        
        # Pivot table for savings
        savings_matrix = self.df.pivot_table(
            values='Estimated Savings', 
            index='Environment', 
            columns='Service', 
            aggfunc='sum', 
            fill_value=0
        ).round(2)
        
        # Instance count matrix
        count_matrix = self.df.pivot_table(
            values='Count', 
            index='Environment', 
            columns='Service', 
            aggfunc='sum', 
            fill_value=0
        )
        
        self.analysis_results['cost_matrix'] = cost_matrix
        self.analysis_results['savings_matrix'] = savings_matrix
        self.analysis_results['count_matrix'] = count_matrix
        
        print("✓ Environment x Service matrix analysis completed")
        return cost_matrix, savings_matrix, count_matrix
    
    def analyze_optimization_opportunities(self):
        """Identify top optimization opportunities"""
        # Calculate savings potential by service and environment
        optimization = self.df.groupby(['Environment', 'Service']).agg({
            'Monthly Cost': 'sum',
            'Estimated Savings': 'sum',
            'Count': 'sum'
        }).round(2)
        
        optimization['Savings Rate %'] = (optimization['Estimated Savings'] / optimization['Monthly Cost'] * 100).round(2)
        optimization['Net Cost'] = optimization['Monthly Cost'] - optimization['Estimated Savings']
        
        # Sort by estimated savings descending
        optimization = optimization.sort_values('Estimated Savings', ascending=False)
        
        # Top opportunities
        top_opportunities = optimization.head(10).copy()
        top_opportunities['Priority Rank'] = range(1, len(top_opportunities) + 1)
        
        self.analysis_results['optimization'] = top_opportunities
        print("✓ Optimization opportunities analysis completed")
        return top_opportunities
    
    def generate_summary_statistics(self):
        """Generate overall summary statistics"""
        summary = {
            'Total Monthly Cost': self.df['Monthly Cost'].sum(),
            'Total Estimated Savings': self.df['Estimated Savings'].sum(),
            'Total Net Cost': self.df['Net Cost After Savings'].sum(),
            'Overall Savings Rate %': (self.df['Estimated Savings'].sum() / self.df['Monthly Cost'].sum() * 100),
            'Total Instance Count': self.df['Count'].sum(),
            'Number of Environments': self.df['Environment'].nunique(),
            'Number of Service Types': self.df['Service'].nunique(),
            'Number of Instance Types': self.df['Instance Type'].nunique(),
            'Average Cost per Instance': (self.df['Monthly Cost'].sum() / self.df['Count'].sum()),
            'Highest Cost Environment': self.df.groupby('Environment')['Monthly Cost'].sum().idxmax(),
            'Highest Cost Service': self.df.groupby('Service')['Monthly Cost'].sum().idxmax()
        }
        
        # Round numeric values
        for key, value in summary.items():
            if isinstance(value, (int, float)) and key != 'Total Instance Count':
                summary[key] = round(value, 2)
        
        self.analysis_results['summary'] = summary
        print("✓ Summary statistics generated")
        return summary
    
    def run_complete_analysis(self):
        """Run all analysis functions"""
        print("🚀 Starting AWS Cost Analysis...")
        print("=" * 50)
        
        if not self.load_data():
            return False
            
        if not self.clean_and_validate_data():
            return False
        
        # Run all analyses
        self.analyze_by_environment()
        self.analyze_by_service()
        self.analyze_environment_service_matrix()
        self.analyze_optimization_opportunities()
        self.generate_summary_statistics()
        
        print("=" * 50)
        print("✅ Analysis completed successfully!")
        return True
    
    def export_to_excel(self, output_file='aws_cost_analysis_results.xlsx'):
        """Export all analysis results to Excel with multiple sheets"""
        if not self.analysis_results:
            print("✗ No analysis results to export")
            return False
        
        try:
            with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                # Write original data
                self.df.to_excel(writer, sheet_name='Raw Data', index=False)
                
                # Write summary statistics
                if 'summary' in self.analysis_results:
                    summary_df = pd.DataFrame(list(self.analysis_results['summary'].items()), 
                                            columns=['Metric', 'Value'])
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Write environment analysis
                if 'environment' in self.analysis_results:
                    self.analysis_results['environment'].to_excel(writer, sheet_name='Environment Analysis')
                
                # Write service analysis
                if 'service' in self.analysis_results:
                    self.analysis_results['service'].to_excel(writer, sheet_name='Service Analysis')
                
                # Write cost matrix
                if 'cost_matrix' in self.analysis_results:
                    self.analysis_results['cost_matrix'].to_excel(writer, sheet_name='Cost Matrix')
                
                # Write savings matrix
                if 'savings_matrix' in self.analysis_results:
                    self.analysis_results['savings_matrix'].to_excel(writer, sheet_name='Savings Matrix')
                
                # Write instance count matrix
                if 'count_matrix' in self.analysis_results:
                    self.analysis_results['count_matrix'].to_excel(writer, sheet_name='Instance Count Matrix')
                
                # Write optimization opportunities
                if 'optimization' in self.analysis_results:
                    self.analysis_results['optimization'].to_excel(writer, sheet_name='Optimization Opportunities')
            
            print(f"✅ Results exported to: {output_file}")
            return True
            
        except Exception as e:
            print(f"✗ Error exporting to Excel: {e}")
            return False
    
    def print_key_insights(self):
        """Print key insights from the analysis"""
        if not self.analysis_results:
            print("No analysis results available")
            return
        
        print("\n" + "=" * 60)
        print("📊 KEY INSIGHTS")
        print("=" * 60)
        
        if 'summary' in self.analysis_results:
            summary = self.analysis_results['summary']
            print(f"💰 Total Monthly Cost: ${summary['Total Monthly Cost']:,.2f}")
            print(f"💡 Total Potential Savings: ${summary['Total Estimated Savings']:,.2f}")
            print(f"📈 Overall Savings Rate: {summary['Overall Savings Rate %']:.1f}%")
            print(f"🏗️  Total Instances: {summary['Total Instance Count']:,}")
            print(f"🌍 Environments: {summary['Number of Environments']}")
            print(f"⚙️  Service Types: {summary['Number of Service Types']}")
        
        if 'environment' in self.analysis_results:
            env_analysis = self.analysis_results['environment']
            print(f"\n🏆 Highest Cost Environment: {env_analysis.index[0]} (${env_analysis.iloc[0]['Total Monthly Cost']:,.2f})")
            print(f"🎯 Best Savings Opportunity: {env_analysis['Savings Rate %'].idxmax()} ({env_analysis['Savings Rate %'].max():.1f}% savings rate)")
        
        if 'service' in self.analysis_results:
            service_analysis = self.analysis_results['service']
            print(f"\n🔧 Highest Cost Service: {service_analysis.index[0]} (${service_analysis.iloc[0]['Total Monthly Cost']:,.2f})")
        
        print("=" * 60)


def main():
    """Main function to run the analysis"""
    # Initialize analyzer
    analyzer = AWSCostAnalyzer('your_cost_data.xlsx')  # Replace with your file path
    
    # Run complete analysis
    if analyzer.run_complete_analysis():
        # Print key insights
        analyzer.print_key_insights()
        
        # Export results
        analyzer.export_to_excel('aws_cost_analysis_results.xlsx')
        
        print("\n📋 Next Steps for Excel Visualization:")
        print("1. Open 'aws_cost_analysis_results.xlsx'")
        print("2. Use 'Environment Analysis' sheet for environment cost charts")
        print("3. Use 'Service Analysis' sheet for service distribution charts")
        print("4. Use 'Cost Matrix' sheet for environment vs service heatmaps")
        print("5. Use 'Optimization Opportunities' sheet for savings priority charts")


if __name__ == "__main__":
    main()