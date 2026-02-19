import pandas as pd

filename = 'prediction_tracker.xlsx'
df = pd.read_excel(filename, sheet_name='Predictions')

# Remove old Rayo entry
df = df[~df['Match'].str.contains('Rayo', case=False)]

# Preserve Summary
try:
    summary_df = pd.read_excel(filename, sheet_name='Summary')
except:
    summary_df = None

with pd.ExcelWriter(filename, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Predictions', index=False)
    if summary_df is not None:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

print(f"Removed old Rayo entry. Rows: {len(df)}")
