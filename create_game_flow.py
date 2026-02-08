import pandas as pd
import os
import glob

# Mappings for user request
# 1. calc_PPDA = accurateOwnHalfPassesAgainst / (tackles + interceptions + fouls)
# 2. calc_OPPDA = accurateOwnHalfPasses / (tacklesAgainst + interceptionsAgainst)
# 3. calc_FieldTilt_Pct = accurateOppositionHalfPasses / (accurateOppositionHalfPasses + accurateOppositionHalfPassesAgainst)
# 4. calc_HighError_Rate = errorsLeadingToShot + errorsLeadingToGoal
# 5. calc_Directness = totalLongBalls / totalPasses
# 6. calc_BigChance_Diff = bigChances - bigChancesAgainst

SOURCE_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\sofascore_team_data"
DEST_DIR = r"c:\Users\errig\OneDrive - มหาวิทยาลัยสยาม (1)\Desktop\model football\game flow"

def calculate_metrics(df):
    df = df.copy()
    
    # helper to avoid ZeroDivisionError
    def safe_div(a, b):
        return a / b.replace(0, 1) # simple safety, though usually these sums > 0

    # 1. calc_PPDA
    # Formula: accurateOwnHalfPassesAgainst / (tackles + interceptions + fouls)
    defensive_actions = df['tackles'] + df['interceptions'] + df['fouls']
    df['calc_PPDA'] = df['accurateOwnHalfPassesAgainst'] / defensive_actions.replace(0, pd.NA)

    # 2. calc_OPPDA
    # Formula: accurateOwnHalfPasses / (tacklesAgainst + interceptionsAgainst)
    defensive_actions_against = df['tacklesAgainst'] + df['interceptionsAgainst']
    df['calc_OPPDA'] = df['accurateOwnHalfPasses'] / defensive_actions_against.replace(0, pd.NA)

    # 3. calc_FieldTilt_Pct
    # Formula: accurateOppositionHalfPasses / (accurateOppositionHalfPasses + accurateOppositionHalfPassesAgainst)
    total_opp_half_passes = df['accurateOppositionHalfPasses'] + df['accurateOppositionHalfPassesAgainst']
    df['calc_FieldTilt_Pct'] = df['accurateOppositionHalfPasses'] / total_opp_half_passes.replace(0, pd.NA)

    # 4. calc_HighError_Rate
    # Formula: errorsLeadingToShot + errorsLeadingToGoal
    df['calc_HighError_Rate'] = df['errorsLeadingToShot'] + df['errorsLeadingToGoal']

    # 5. calc_Directness
    # Formula: totalLongBalls / totalPasses
    df['calc_Directness'] = df['totalLongBalls'] / df['totalPasses'].replace(0, pd.NA)

    # 6. calc_BigChance_Diff
    # Formula: bigChances - bigChancesAgainst
    df['calc_BigChance_Diff'] = df['bigChances'] - df['bigChancesAgainst']

    return df

def main():
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        # Avoid printing path with Thai characters on Windows console default encoding
        print(f"Created directory: game flow")

    files = glob.glob(os.path.join(SOURCE_DIR, "*.xlsx"))
    print(f"Found {len(files)} files.")

    for file_path in files:
        filename = os.path.basename(file_path)
        # Clean filename to get League Name
        # e.g. "Premier_League_Team_Stats.xlsx" -> "Premier_League"
        league_name = filename.replace("_Team_Stats.xlsx", "").replace(".xlsx", "")
        
        print(f"Processing League: {league_name}")
        
        try:
            df = pd.read_excel(file_path)
            
            # Ensure columns exist
            required_cols = [
                'Team_Name',
                'accurateOwnHalfPassesAgainst', 'tackles', 'interceptions', 'fouls',
                'accurateOwnHalfPasses', 'tacklesAgainst', 'interceptionsAgainst',
                'accurateOppositionHalfPasses', 'accurateOppositionHalfPassesAgainst',
                'errorsLeadingToShot', 'errorsLeadingToGoal',
                'totalLongBalls', 'totalPasses',
                'bigChances', 'bigChancesAgainst'
            ]
            
            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                print(f"  SKIPPING {filename}: Missing columns: {missing}")
                continue

            df_calculated = calculate_metrics(df)
            
            # Select columns to save
            output_cols = ['Team_Name', 'calc_PPDA', 'calc_OPPDA', 'calc_FieldTilt_Pct', 
                           'calc_HighError_Rate', 'calc_Directness', 'calc_BigChance_Diff']
            
            final_df = df_calculated[output_cols]
            
            # Save as a single-row DataFrame
            save_path = os.path.join(DEST_DIR, f"{league_name}_GameFlow.xlsx")
            final_df.to_excel(save_path, index=False)
                
            print(f"  Saved consolidated file for {league_name}")

        except Exception as e:
            print(f"  Error processing {filename}: {e}")

if __name__ == "__main__":
    main()
