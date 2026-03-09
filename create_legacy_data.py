import pandas as pd
import numpy as np

# Creating an "Enterprise-Messy" Excel file for 2026
data = {
    # Testing mixed formats, different months, and a "wrong year" (2022)
    'Date': [
        '2026-01-15',      # Standard
        '15/01/2026',      # European (Tests January Slovak query)
        'March 10, 2026',  # Text-based
        '2022-01-01',      # Wrong Year (Tests Case #8: Empty results)
        '2026.04.12',      # Dot-separated
        None               # Missing (Tests fillna logic)
    ],
    # Testing leading/trailing spaces and inconsistent casing
    'Region': ['North', ' south ', 'West', 'NORTH', 'East', 'North'], 
    
    # Testing N/A handling and specific categories for French/Slovak queries
    'Product_Category': ['Electronics', 'Furniture', 'Electronics', 'Electronics', 'Appliances', 'N/A'],
    
    # Testing text-in-numbers and nulls
    'Units_Sold': [10, '12 pieces', '5 units', 100, 8, None],
    
    # Testing currency symbols and text errors
    'Unit_Price': [500, '$1200', 300, 150, 'Check with Finance', 450],
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to your working directory
df.to_excel("legacy_sales_data.xlsx", index=False)

print("🚀 'legacy_sales_data.xlsx' updated with 6 complex test rows.")
print("Now go to your Streamlit app and upload this file to start the 10-point test.")