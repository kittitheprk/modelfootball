import pandas as pd
import glob
import os

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "model_ready_data.csv")

def clean_fbref_data():
    """Compiles and cleans FBref player data."""
    all_files = glob.glob(os.path.join(DATA_DIR, "*_players.csv"))
    print(f"Found {len(all_files)} FBref player files.")
    
    if not all_files:
        return pd.DataFrame()
        
    df_list = []
    for f in all_files:
        try:
            df = pd.read_csv(f)
            # 1. Remove "Matches" link columns
            cols_to_drop = [c for c in df.columns if "Matches" in c and "Played" not in c]
            df = df.drop(columns=cols_to_drop, errors='ignore')
            
            # 2. Filter out header repetition rows (where "Player" appears in Player column)
            if 'Unnamed: 0_level_0_Player' in df.columns:
                 df = df[df['Unnamed: 0_level_0_Player'] != 'Player']
            elif 'Player' in df.columns:
                 df = df[df['Player'] != 'Player']

            df_list.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not df_list:
        return pd.DataFrame()

    full_df = pd.concat(df_list, ignore_index=True)
    
    # 3. Rename Columns
    # We strip the prefix "Unnamed: ..._" and specific category prefixes for cleaner usage
    new_cols = {}
    for col in full_df.columns:
        if "Unnamed" in col:
            new_cols[col] = col.split('_')[-1]
        elif "_" in col and "Team_" not in col and "Season" not in col and "Competition" not in col:
            # e.g. Performance_Gls -> Gls
            # Check if suffix collision exists? (e.g. Per 90_Gls vs Performance_Gls)
            # Ideally we keep some context or standardized names.
            # Let's keep it simple: Category_StatName
            # But standard usage usually just wants 'Goals', 'Assists', 'xG'
            
            parts = col.split('_')
            stat_name = "_".join(parts[1:])
            
            # Manual Mapping for common important stats
            if stat_name == "Gls": new_cols[col] = "Goals"
            elif stat_name == "Ast": new_cols[col] = "Assists"
            elif stat_name == "PK": new_cols[col] = "Penalties"
            elif stat_name == "PKatt": new_cols[col] = "Penalties_Att"
            elif stat_name == "CrdY": new_cols[col] = "Yellow_Cards"
            elif stat_name == "CrdR": new_cols[col] = "Red_Cards"
            else:
                new_cols[col] = stat_name # Default to suffix
        else:
            new_cols[col] = col
            
    full_df = full_df.rename(columns=new_cols)
    
    # Handle Duplicate Columns if any resulted from renaming (e.g. Expect_xG vs Per90_xG -> xG)
    # Actually, Per 90 Minutes_xG -> xG would conflict with Expected_xG -> xG
    # Let's refine renaming to avoid conflicts
    # Re-reading standard FBref cols...
    # Expected_xG -> xG
    # Per 90 Minutes_xG -> xG (Conflict!)
    
    # Better strategy: Only rename specific known columns, or keep prefix for "Per 90"
    
    return full_df

def robust_clean(df):
    """Refined cleaning strategy."""
    
    # Map for clean names
    rename_map = {
        'Unnamed: 0_level_0_Player': 'Player',
        'Unnamed: 1_level_0_Nation': 'Nation',
        'Unnamed: 2_level_0_Pos': 'Pos',
        'Unnamed: 3_level_0_Age': 'Age',
        'Unnamed: 4_level_0_MP': 'Matches_Played',
        'Playing Time_Starts': 'Starts',
        'Playing Time_Min': 'Minutes',
        'Playing Time_90s': '90s',
        
        # Performance
        'Performance_Gls': 'Goals',
        'Performance_Ast': 'Assists',
        'Performance_G+A': 'G_plus_A',
        'Performance_PK': 'PK_Made',
        'Performance_PKatt': 'PK_Att',
        'Performance_CrdY': 'Yellow_Cards',
        'Performance_CrdR': 'Red_Cards',
        
        # Expected
        'Expected_xG': 'xG',
        'Expected_npxG': 'npxG',
        'Expected_xAG': 'xAG',
        
        # Progression
        'Progression_PrgC': 'Prog_Carries',
        'Progression_PrgP': 'Prog_Passes',
        'Progression_PrgR': 'Prog_Receives',
    }
    
    # Rename known cols
    df = df.rename(columns=rename_map)
    
    # For others, if they contain "Per 90", append _Per90
    new_cols = {}
    for col in df.columns:
        if "Per 90 Minutes" in col:
            # e.g. Per 90 Minutes_Gls
            suffix = col.split('_')[-1]
            new_cols[col] = f"{suffix}_Per90"
            
    df = df.rename(columns=new_cols)
    
    # Fill NAs
    # Numeric columns: fill with 0
    # String columns: fill with "" or "Unknown"
    
    # Identify numeric cols
    for col in df.columns:
        # Try converting to numeric
        try:
             df[col] = pd.to_numeric(df[col])
             df[col] = df[col].fillna(0)
        except:
             # Keep as object, fill na
             df[col] = df[col].fillna("")
             
    return df

if __name__ == "__main__":
    print("Starting Data Cleaning...")
    
    # We mainly focus on FBref for the model as it has the stats
    raw_df = clean_fbref_data()
    
    if not raw_df.empty:
        clean_df = robust_clean(raw_df)
        
        # Drop rows with empty Player name
        clean_df = clean_df[clean_df['Player'] != ""]
        
        print(f"Data shape: {clean_df.shape}")
        print("Columns:", clean_df.columns.tolist()[:10], "...")
        
        clean_df.to_csv(OUTPUT_FILE, index=False)
        print(f"Successfully saved to {OUTPUT_FILE}")
    else:
        print("No data found to clean.")
