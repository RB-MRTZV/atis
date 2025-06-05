import sys
import subprocess
import pkg_resources

def check_versions():
    """Check Python and package versions"""
    print(f"Python version: {sys.version}")
    
    packages_to_check = ['pandas', 'openpyxl', 'xlsxwriter', 'numpy']
    
    for package in packages_to_check:
        try:
            version = pkg_resources.get_distribution(package).version
            print(f"{package}: {version}")
        except pkg_resources.DistributionNotFound:
            print(f"{package}: NOT INSTALLED")

def install_compatible_versions():
    """Install compatible package versions"""
    
    # Compatible versions that work well together
    packages = [
        'pandas>=1.3.0,<2.0.0',
        'openpyxl>=3.0.9',
        'xlsxwriter>=3.0.0',
        'numpy>=1.21.0'
    ]
    
    for package in packages:
        try:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {package}: {e}")

def simple_excel_export_test():
    """Test if Excel export works"""
    import pandas as pd
    
    # Create test data
    test_df = pd.DataFrame({
        'Environment': ['prod', 'dev', 'test'],
        'Cost': [100, 50, 25]
    })
    
    engines_to_test = ['openpyxl', 'xlsxwriter']
    
    for engine in engines_to_test:
        try:
            test_df.to_excel(f'test_{engine}.xlsx', engine=engine, index=False)
            print(f"✅ {engine} engine works")
        except Exception as e:
            print(f"❌ {engine} engine failed: {e}")

if __name__ == "__main__":
    print("=== CHECKING CURRENT VERSIONS ===")
    check_versions()
    
    print("\n=== TESTING EXCEL EXPORT ===")
    simple_excel_export_test()
    
    print("\nIf you see failures above, run:")
    print("pip install --upgrade pandas openpyxl xlsxwriter")
    print("Or uncomment the line below and run this script again")
    
    # Uncomment the next line if you want to auto-install compatible versions
    # install_compatible_versions()