
import pandas as pd
import os

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

base_path = r"c:/Users/errig/OneDrive - มหาวิทยาลัยสยาม (1)/Desktop/model football"
all_stats_path = os.path.join(base_path, "all stats", "Bundesliga_Stats.xlsx")
sofascore_path = os.path.join(base_path, "sofascore_team_data", "Bundesliga_Team_Stats.xlsx")

def get_sofascore_stats(team_keyword):
    try:
        df = pd.read_excel(sofascore_path)
        # Filter loosely by name
        team_stats = df[df['Team_Name'].astype(str).str.contains(team_keyword, case=False, na=False)].iloc[0]
        return team_stats
    except Exception as e:
        print(f"Error getting sofascore stats for {team_keyword}: {e}")
        return None

def get_fbref_aggregate(squad_name, sheet_name, columns):
    try:
        df = pd.read_excel(all_stats_path, sheet_name=sheet_name)
        # Filter by Squad
        squad_df = df[df['Squad'] == squad_name]
        # Sum the columns
        total = squad_df[columns].sum()
        return total
    except Exception as e:
        print(f"Error getting fbref stats for {squad_name} in {sheet_name}: {e}")
        return None

def main():
    print("Gathering data for Bayern Munich vs Wolfsburg...")

    # Team Names
    sofa_bayern = "Bayern"
    sofa_wolfsburg = "Wolfsburg"
    fbref_bayern = "Bayern Munich"
    fbref_wolfsburg = "Wolfsburg"

    # 1. Sofascore Data
    print("\n--- Sofascore Team Stats (Average/Total per match usually available as totals or averages) ---")
    s_bayern = get_sofascore_stats(sofa_bayern)
    s_wolf = get_sofascore_stats(sofa_wolfsburg)
    
    if s_bayern is not None and s_wolf is not None:
        metrics = [
            'goalsScored', 'goalsConceded', 'averageBallPossession', 'shots', 'shotsOnTarget', 
            'bigChances', 'fastBreaks', 'totalCrosses', 'totalLongBalls', 'accuratePassesPercentage',
            'tackles', 'interceptions', 'fouls', 'yellowCards', 'duelsWonPercentage', 'aerialDuelsWonPercentage'
        ]
        
        comparison = pd.DataFrame({
            'Metric': metrics,
            'Bayern': [s_bayern.get(m, 'N/A') for m in metrics],
            'Wolfsburg': [s_wolf.get(m, 'N/A') for m in metrics]
        })
        print(comparison.to_string(index=False))

    # 2. Fbref Detailed Style Data (Aggregated from Players)
    print("\n--- Fbref Detailed Style Stats (Aggregated Player Totals) ---")
    
    # Passing Style
    pass_cols = ['Short_Att', 'Short_Cmp', 'Long_Att', 'Passes_Att (GK)'] # Note: Passes_Att (GK) might be in GK sheet, standard passing has Long_Att
    # Let's check the Passing sheet columns again from previous step if needed.
    # Passing Sheet: 'Short_Att', 'Long_Att', 'Total_Att'
    
    # We'll grab specific columns from specific sheets
    
    # Sheet: Passing
    # Short vs Long
    p_bayern = get_fbref_aggregate(fbref_bayern, 'Passing', ['Short_Att', 'Medium_Att', 'Long_Att', 'Total_Att'])
    p_wolf = get_fbref_aggregate(fbref_wolfsburg, 'Passing', ['Short_Att', 'Medium_Att', 'Long_Att', 'Total_Att'])
    
    # Sheet: Pass Types
    # Through Balls, Crosses
    pt_bayern = get_fbref_aggregate(fbref_bayern, 'Pass Types', ['Pass Types_TB', 'Pass Types_Crs', 'Pass Types_Sw']) # Sw = Switches
    pt_wolf = get_fbref_aggregate(fbref_wolfsburg, 'Pass Types', ['Pass Types_TB', 'Pass Types_Crs', 'Pass Types_Sw'])
    
    # Sheet: Possession
    # Dribbles (Take-Ons)
    poss_bayern = get_fbref_aggregate(fbref_bayern, 'Possession', ['Take-Ons_Att', 'Take-Ons_Succ'])
    poss_wolf = get_fbref_aggregate(fbref_wolfsburg, 'Possession', ['Take-Ons_Att', 'Take-Ons_Succ'])

    # Construct Fbref Comparison
    rows = []
    if p_bayern is not None and p_wolf is not None:
        rows.append({'Metric': 'Short Passes Att', 'Bayern': p_bayern['Short_Att'], 'Wolfsburg': p_wolf['Short_Att']})
        rows.append({'Metric': 'Long Passes Att', 'Bayern': p_bayern['Long_Att'], 'Wolfsburg': p_wolf['Long_Att']})
        # Calc percentages
        b_short_pct = (p_bayern['Short_Att'] / p_bayern['Total_Att']) * 100 if p_bayern['Total_Att'] else 0
        w_short_pct = (p_wolf['Short_Att'] / p_wolf['Total_Att']) * 100 if p_wolf['Total_Att'] else 0
        rows.append({'Metric': 'Short Pass %', 'Bayern': f"{b_short_pct:.1f}%", 'Wolfsburg': f"{w_short_pct:.1f}%"})

    if pt_bayern is not None and pt_wolf is not None:
        rows.append({'Metric': 'Through Balls', 'Bayern': pt_bayern['Pass Types_TB'], 'Wolfsburg': pt_wolf['Pass Types_TB']})
        rows.append({'Metric': 'Crosses (Pass Types)', 'Bayern': pt_bayern['Pass Types_Crs'], 'Wolfsburg': pt_wolf['Pass Types_Crs']})
        rows.append({'Metric': 'Switches', 'Bayern': pt_bayern['Pass Types_Sw'], 'Wolfsburg': pt_wolf['Pass Types_Sw']})

    if poss_bayern is not None and poss_wolf is not None:
        rows.append({'Metric': 'Dribbles Att', 'Bayern': poss_bayern['Take-Ons_Att'], 'Wolfsburg': poss_wolf['Take-Ons_Att']})
    
    fbref_comp = pd.DataFrame(rows)
    print(fbref_comp.to_string(index=False))

if __name__ == "__main__":
    main()
