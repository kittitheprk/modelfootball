import pandas as pd
from bs4 import BeautifulSoup, Comment
import os
import glob
from io import StringIO

# Configuration
# Mapping of League Name to expected local filename pattern (or part of it)
LEAGUES = {
    "Premier_League": "Premier League Player Stats",
    "Serie_A": "Serie A Player Stats",
    "La_Liga": "La Liga Player Stats",
    "Ligue_1": "Ligue 1 Player Stats",
    "Bundesliga": "Bundesliga Player Stats"
}

OUTPUT_DIR = "all stats"

def clean_header(df):
    """Flattens multi-level columns and cleans names."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            # col is a tuple like ('Unnamed: 0_level_0', 'Player') or ('Performance', 'Gls')
            c0 = str(col[0]).strip()
            c1 = str(col[1]).strip()
            
            if "Unnamed" in c0:
                new_cols.append(c1)
            elif "Unnamed" in c1:
                new_cols.append(c0)
            else:
                new_cols.append(f"{c0}_{c1}")
        df.columns = new_cols
    return df

def process_table(soup, table_id_part, name_filter=None):
    """Finds and processes a table based on ID substring."""
    # Find table that contains the ID part
    tables = soup.find_all('table')
    target_table = None
    for t in tables:
        if t.get('id') and table_id_part in t.get('id'):
            target_table = t
            break
            
    if not target_table:
        return None

    try:
        df = pd.read_html(StringIO(str(target_table)))[0]
        df = clean_header(df)
        
        # Clean repetitive headers
        if name_filter and name_filter in df.columns:
            df = df[df[name_filter] != name_filter]
            
        df = df.dropna(how='all', axis=1) # Drop empty cols
        return df
    except Exception as e:
        print(f"Error parsing table {table_id_part}: {e}")
        return None

def find_local_file(league_key, file_pattern):
    """Finds the most recent HTML file matching the pattern."""
    # Look in OUTPUT_DIR and current directory
    search_patterns = [
        os.path.join(OUTPUT_DIR, f"*{file_pattern}*.html"),
        os.path.join(OUTPUT_DIR, f"*{league_key}*.html"),
        f"*{file_pattern}*.html"
    ]
    
    candidates = []
    for p in search_patterns:
        candidates.extend(glob.glob(p))
    
    # Filter out debug files if possible
    valid_candidates = [c for c in candidates if "debug" not in os.path.basename(c)]
    
    if valid_candidates:
        # Return the most recent VALID file
        return max(valid_candidates, key=os.path.getmtime)
    elif candidates:
        # Fallback to debug if nothing else
        return max(candidates, key=os.path.getmtime)
        
    return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print("Starting Local HTML Processing for Stats...")
    
    for league, pattern in LEAGUES.items():
        print(f"\nProcessing {league}...")
        
        # 1. Find Local File
        local_file = find_local_file(league, pattern)
        if not local_file:
            print(f"  [!] No local HTML file found for {league} (pattern: {pattern})")
            print(f"  Please save the webpage as HTML in the '{OUTPUT_DIR}' folder.")
            continue
            
        print(f"  Reading file: {local_file}")
        
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            # Extract tables from comments (common fbref pattern)
            comments = soup.find_all(string=lambda text: isinstance(text, Comment))
            for comment in comments:
                if '<table' in comment:
                    comment_soup = BeautifulSoup(comment, 'html.parser')
                    if soup.body:
                        soup.body.append(comment_soup)

            # Create a writer for THIS league
            league_file = os.path.join(OUTPUT_DIR, f"{league}_Stats.xlsx")

            # 1. Squad Stats
            print("  Extracting Team/Squad stats...")
            df_squad = process_table(soup, "stats_squads_standard_for", name_filter="Squad")
            
            # 2. Player Stats
            print("  Extracting Player Stats...")
            tables = soup.find_all('table')
            player_table = None
            for t in tables:
                tid = t.get('id', '')
                if 'stats_standard' in tid and 'squads' not in tid:
                    player_table = t
                    break
            
            df_player = None
            if player_table:
                try:
                    df_player = pd.read_html(StringIO(str(player_table)))[0]
                    df_player = clean_header(df_player)
                    if 'Player' in df_player.columns:
                        df_player = df_player[df_player['Player'] != 'Player']
                    df_player = df_player.dropna(how='all', axis=1)
                except Exception as e:
                    print(f"    Error parsing player table: {e}")
            
            # Save if we have data
            if df_squad is not None or df_player is not None:
                try:
                    with pd.ExcelWriter(league_file, engine='openpyxl') as writer:
                        if df_squad is not None:
                            sheet_name = "Team_Stats"
                            df_squad.to_excel(writer, sheet_name=sheet_name, index=False)
                            print(f"    Saved {sheet_name} ({len(df_squad)} rows)")
                        else:
                            print("    Could not find Squad stats table.")
                            
                        if df_player is not None:
                             sheet_name = "Player_Stats"
                             df_player.to_excel(writer, sheet_name=sheet_name, index=False)
                             print(f"    Saved {sheet_name} ({len(df_player)} rows)")
                        else:
                             print("    Could not find Player stats table.")
                    print(f"  --> Saved file: {league_file}")
                except Exception as e:
                    print(f"    Error saving Excel file: {e}")
            else:
                 print(f"    WARNING: No valid data found in {local_file}.")

        except Exception as e:
            print(f"  Error processing file {local_file}: {e}")

    print(f"\n\nDone! All processed files saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
