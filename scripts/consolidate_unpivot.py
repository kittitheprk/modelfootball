import pandas as pd
import os
import glob

# Paths
sofascore_dir = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\sofascore_team_data"
gameflow_dir = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\game flow"
output_dir = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\charts"
output_file = os.path.join(output_dir, "unpivoted_data.xlsx")

print("Starting consolidation...")

# --- Process Sofascore Team Data ---
print("Processing Sofascore Team Data...")
all_sofa_data = []
sofa_files = glob.glob(os.path.join(sofascore_dir, "*.xlsx"))

for filepath in sofa_files:
    try:
        print(f"Reading {os.path.basename(filepath)}...")
        df = pd.read_excel(filepath)
        
        # Ensure 'League' column exists. If not, infer from filename
        if 'League' not in df.columns:
            filename = os.path.basename(filepath)
            league_name = filename.replace("_Team_Stats.xlsx", "").replace("_", " ")
            df['League'] = league_name
            
        all_sofa_data.append(df)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

sofascore_unpivoted = pd.DataFrame()
if all_sofa_data:
    combined_sofa = pd.concat(all_sofa_data, ignore_index=True)
    
    # Identify ID columns for melting
    # We always want Team_Name and League. Team_ID if it exists.
    id_vars = [col for col in ['Team_Name', 'League', 'Team_ID'] if col in combined_sofa.columns]
    
    # Melt the rest
    # value_vars will be everything else
    sofascore_unpivoted = combined_sofa.melt(id_vars=id_vars, var_name='Metric', value_name='Value')
    print(f"Sofascore unpivoted shape: {sofascore_unpivoted.shape}")

# --- Process Game Flow Data ---
print("Processing Game Flow Data...")
all_gameflow = []
gameflow_files = glob.glob(os.path.join(gameflow_dir, "*.xlsx"))

for filepath in gameflow_files:
    try:
        print(f"Reading {os.path.basename(filepath)}...")
        df = pd.read_excel(filepath)
        
        # Create League column from filename
        filename = os.path.basename(filepath)
        # Example: Bundesliga_GameFlow.xlsx -> Bundesliga
        league_name = filename.replace("_GameFlow.xlsx", "").replace("_", " ")
        df['League'] = league_name
        
        all_gameflow.append(df)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

gameflow_unpivoted = pd.DataFrame()
if all_gameflow:
    combined_gameflow = pd.concat(all_gameflow, ignore_index=True)
    
    # Identify ID columns
    id_vars = [col for col in ['Team_Name', 'League'] if col in combined_gameflow.columns]
    
    # Melt
    gameflow_unpivoted = combined_gameflow.melt(id_vars=id_vars, var_name='Metric', value_name='Value')
    print(f"Game Flow unpivoted shape: {gameflow_unpivoted.shape}")

# --- Save to Excel ---
print("Saving to output file...")
try:
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        if not sofascore_unpivoted.empty:
            sofascore_unpivoted.to_excel(writer, sheet_name='sofascore_team_data', index=False)
        else:
            print("Warning: Sofascore data is empty.")
            
        if not gameflow_unpivoted.empty:
            gameflow_unpivoted.to_excel(writer, sheet_name='game flow', index=False)
        else:
            print("Warning: Game Flow data is empty.")
            
    print("Done!")
except Exception as e:
    print(f"Error saving file: {e}")
