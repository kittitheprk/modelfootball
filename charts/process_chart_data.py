import pandas as pd
import os
import glob
import warnings

warnings.filterwarnings('ignore')

# Settings
INPUT_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\all stats"
OUTPUT_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\charts"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "final_chart_data.xlsx")

# Format: (Sheet Name, Raw Column Name, New Column Name)
METRICS_TO_LOAD = [
    # 1. Attacking
    ('Player_Stats', 'Performance_G-PK', 'Non_Penalty_Goals'),
    ('Player_Stats', 'Expected_npxG', 'npxG'),
    ('Shooting', 'Standard_Sh', 'Shots_Total'),
    ('Player_Stats', 'Performance_Ast', 'Assists'),
    ('Player_Stats', 'Expected_xAG', 'xAG'),
    ('Player_Stats', 'Expected_npxG+xAG', 'npxG_plus_xAG'),
    ('Goal and Shot Creation', 'SCA_SCA', 'Shot_Creating_Actions'),

    # 2. Possession
    ('Passing', 'Total_Att', 'Passes_Attempted'),
    ('Passing', 'Total_Cmp%', 'Pass_Completion_Pct'), # Already a %, do NOT divide by 90
    ('Passing', 'PrgP', 'Progressive_Passes'),
    ('Possession', 'Carries_PrgC', 'Progressive_Carries'),
    ('Possession', 'Take-Ons_Succ', 'Successful_Take_Ons'),
    ('Possession', 'Touches_Att Pen', 'Touches_Att_Pen'),
    ('Possession', 'Receiving_PrgR', 'Progressive_Passes_Received'),

    # 3. Defending
    ('Defensive Actions', 'Tackles_Tkl', 'Tackles'),
    ('Defensive Actions', 'Int', 'Interceptions'),
    ('Defensive Actions', 'Blocks_Blocks', 'Blocks'),
    ('Defensive Actions', 'Clr', 'Clearances'),
    ('Miscellaneous Stats', 'Aerial Duels_Won', 'Aerials_Won')
]

# Metrics that are ALREADY rate/ratio and should NOT be divided by 90
ALREADY_RATE_METRICS = ['Pass_Completion_Pct']

def load_and_process_leagues():
    all_files = glob.glob(os.path.join(INPUT_DIR, "*.xlsx"))
    final_df = pd.DataFrame()

    for file_path in all_files:
        league_name = os.path.basename(file_path).replace("_Stats.xlsx", "").replace("_", " ")
        print(f"Processing {league_name}...")
        
        try:
            xls = pd.ExcelFile(file_path)
            
            # 1. Base DataFrame from Player_Stats
            base_df = pd.read_excel(xls, sheet_name='Player_Stats')
            
            # Base columns
            base_cols = ['Player', 'Nation', 'Pos', 'Squad', 'Age', 'Playing Time_90s']
            
            # Rename columns found in Player_Stats
            for sheet, col, new_name in METRICS_TO_LOAD:
                if sheet == 'Player_Stats' and col in base_df.columns:
                    base_df.rename(columns={col: new_name}, inplace=True)
            
            # Keep only keys + renames
            keys = ['Player', 'Squad']
            
            # We must only keep columns that are either in base_cols or in our new_names list
            # But wait, base_df has everything. Let's just keep what we need later or rename everything first.
            merged_df = base_df.copy()

            # 2. Merge other sheets
            sheet_map = {}
            for sheet, col, new_name in METRICS_TO_LOAD:
                if sheet != 'Player_Stats':
                    if sheet not in sheet_map: sheet_map[sheet] = []
                    sheet_map[sheet].append((col, new_name))
            
            for sheet, metrics in sheet_map.items():
                if sheet in xls.sheet_names:
                    sheet_df = pd.read_excel(xls, sheet_name=sheet)
                    
                    # Columns to fetch: Keys + Metrics
                    cols_to_fetch = keys + [m[0] for m in metrics]
                    
                    # Verify cols exist
                    existing_cols = [c for c in cols_to_fetch if c in sheet_df.columns]
                    
                    # Rename dict
                    rename_dict = {m[0]: m[1] for m in metrics if m[0] in existing_cols}
                    
                    subset = sheet_df[existing_cols].rename(columns=rename_dict)
                    
                    # Clean duplicates before merge if necessary? 
                    # Usually Player+Squad is unique per sheet, but let's drop duplicates just in case
                    subset = subset.drop_duplicates(subset=[c for c in keys if c in subset.columns])
                    
                    merged_df = pd.merge(merged_df, subset, on=keys, how='left')
            
            merged_df['League'] = league_name
            final_df = pd.concat([final_df, merged_df], ignore_index=True)
            
        except Exception as e:
            print(f"Error processing {league_name}: {e}")

    # 3. Calculate Per 90 stats
    print("Calculating Per 90 stats...")
    
    # Identify which columns we actually possess in final_df
    available_metrics = [m[2] for m in METRICS_TO_LOAD if m[2] in final_df.columns]
    per90_cols = []
    
    for col in available_metrics:
        p90_name = f"{col}_Per90"
        per90_cols.append(p90_name)
        
        if col in ALREADY_RATE_METRICS:
            # Just copy the value (it's already %)
            final_df[p90_name] = final_df[col]
        else:
            # Divide by 90
            final_df[p90_name] = final_df.apply(
                lambda row: row[col] / row['Playing Time_90s'] if row['Playing Time_90s'] > 0 else 0, axis=1
            )

    # 4. Filter for Ranking (optional, but good for data quality)
    # We'll calculate percentiles for everyone, but typically you'd only compare against players with decent minutes
    
    # 5. Calculate Percentiles by Position
    print("Calculating Percentiles...")
    final_df['Pos_Primary'] = final_df['Pos'].apply(lambda x: x.split(',')[0] if isinstance(x, str) else x)
    
    for col in per90_cols:
        pct_col = f"{col}_Pct"
        # Rank within primary position
        final_df[pct_col] = final_df.groupby('Pos_Primary')[col].transform(lambda x: x.rank(pct=True, method='average') * 99)

    # Final Output Columns
    base_info = ['Player', 'Nation', 'Pos', 'Squad', 'League', 'Playing Time_90s']
    
    # We export: Info + Raw Values + Per90 + Percentiles
    # (User asked to "Add columns", so keeping Raw is good)
    final_cols = base_info + available_metrics + per90_cols + [c + "_Pct" for c in per90_cols]
    
    # Ensure they exist
    final_cols = [c for c in final_cols if c in final_df.columns]
    
    output_df = final_df[final_cols]
    
    print("Saving to Output Excel...")
    output_df.to_excel(OUTPUT_FILE, index=False)
    print("Done!")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    load_and_process_leagues()
