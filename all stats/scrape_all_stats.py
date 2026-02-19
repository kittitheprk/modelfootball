import pandas as pd
from bs4 import BeautifulSoup, Comment
import time
import os
import random
from io import StringIO
import undetected_chromedriver as uc

# Configuration
OUTPUT_DIR = "all stats"

LEAGUES = {
    "Premier_League": {"id": "9", "slug": "Premier-League"},
    "Serie_A": {"id": "11", "slug": "Serie-A"},
    "La_Liga": {"id": "12", "slug": "La-Liga"},
    "Ligue_1": {"id": "13", "slug": "Ligue-1"},
    "Bundesliga": {"id": "20", "slug": "Bundesliga"}
}

# Undetected ChromeDriver Setup (bypasses Cloudflare)
def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = uc.Chrome(options=options, version_main=144)
    return driver

def get_soup(driver, url):
    """Fetches the URL and returns a BeautifulSoup object, parsing comments for hidden tables."""
    try:
        time.sleep(random.uniform(3, 6))
        driver.get(url)
        time.sleep(5)

        # Check for Cloudflare Challenge
        retries = 0
        while "Verify you are human" in driver.page_source or "Just a moment..." in driver.title:
            if retries == 0:
                print(f"  [!] Cloudflare Challenge Detected! Please solve the CAPTCHA in the browser window.")
            time.sleep(5)
            retries += 1
            if retries > 60:
                break

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Extract tables from comments (common fbref pattern)
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if '<table' in comment:
                comment_soup = BeautifulSoup(comment, 'html.parser')
                if soup.body:
                    soup.body.append(comment_soup)
        return soup

    except Exception as e:
        print(f"  Exception fetching {url}: {e}")
    return None

def clean_header(df):
    """Flattens multi-level columns and cleans names."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
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
        
        if name_filter and name_filter in df.columns:
            df = df[df[name_filter] != name_filter]
            
        df = df.dropna(how='all', axis=1)
        return df
    except Exception as e:
        print(f"Error parsing table {table_id_part}: {e}")
        return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    print(f"Starting FBref Stats Scrape for {len(LEAGUES)} leagues...")
    
    driver = setup_driver()
    try:
        for league_name, info in LEAGUES.items():
            league_id = info["id"]
            league_slug = info["slug"]
            
            url = f"https://fbref.com/en/comps/{league_id}/stats/{league_slug}-Stats"
            print(f"\nProcessing {league_name}...")
            print(f"  URL: {url}")
            
            soup = get_soup(driver, url)
            if not soup:
                print(f"  [!] Failed to fetch page for {league_name}. Skipping.")
                continue

            league_file = os.path.join(OUTPUT_DIR, f"{league_name}_Stats.xlsx")

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
                 print(f"    WARNING: No valid data found for {league_name}.")

    finally:
        driver.quit()

    print(f"\n\nDone! All processed files saved in: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
