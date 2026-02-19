import pandas as pd
import os

INPUT_FILE = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\charts\final_chart_data.xlsx"
OUTPUT_FILE = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\charts\final_chart_data_long.xlsx"

# Define the groups
METRIC_GROUPS = {
    'Attacking': [
        'Non_Penalty_Goals', 'npxG', 'Shots_Total', 'Assists', 'xAG', 'npxG_plus_xAG', 'Shot_Creating_Actions'
    ],
    'Possession': [
        'Passes_Attempted', 'Pass_Completion_Pct', 'Progressive_Passes', 'Progressive_Carries', 
        'Successful_Take_Ons', 'Touches_Att_Pen', 'Progressive_Passes_Received'
    ],
    'Defending': [
        'Tackles', 'Interceptions', 'Blocks', 'Clearances', 'Aerials_Won'
    ]
}

def unpivot_data():
    if not os.path.exists(INPUT_FILE):
        print("Input file not found.")
        return

    import shutil
    temp_file = INPUT_FILE + ".tmp.xlsx"
    try:
        shutil.copy2(INPUT_FILE, temp_file)
        print("Reading wide data (from temp copy)...")
        df = pd.read_excel(temp_file)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # Base columns to keep fixed
    id_vars = ['Player', 'Nation', 'Pos', 'Squad', 'League', 'Playing Time_90s']
    
    long_rows = []
    
    # Iterate through groups and metrics to build the long format
    # This approach is explicit and safe
    print("Transforming to long format...")
    
    # We will build a list of DataFrames to concat
    dfs_to_concat = []
    
    for category, metrics in METRIC_GROUPS.items():
        for metric in metrics:
            # Construct column names expected in the wide file
            col_raw = metric
            col_per90 = f"{metric}_Per90"
            col_pct = f"{metric}_Per90_Pct"
            
            # Check if columns exist
            cols_to_check = [col_raw, col_per90, col_pct]
            if not all(c in df.columns for c in cols_to_check):
                print(f"Warning: Missing columns for {metric}. Skipping.")
                continue
            
            # Create a subset DataFrame for this metric
            sub_df = df[id_vars].copy()
            sub_df['Category'] = category
            sub_df['Metric'] = metric
            sub_df['Raw'] = df[col_raw]
            sub_df['Per90'] = df[col_per90]
            sub_df['Percentile'] = df[col_pct]
            
            dfs_to_concat.append(sub_df)
    
    if dfs_to_concat:
        final_long_df = pd.concat(dfs_to_concat, ignore_index=True)
        
        # Sort for readability: Player -> Category -> Metric
        final_long_df.sort_values(by=['Player', 'Category', 'Metric'], inplace=True)
        
        print("Saving rows to Excel...")
        final_long_df.to_excel(OUTPUT_FILE, index=False)
        print("Done!")
    else:
        print("No data processed.")

if __name__ == "__main__":
    unpivot_data()
