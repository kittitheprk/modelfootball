import pandas as pd
from bs4 import BeautifulSoup, Comment
import time
import os
import random
from io import StringIO
from tqdm import tqdm
import undetected_chromedriver as uc

# Configuration
OUTPUT_DIR = "all stats"

# Leagues and their ID mappings
LEAGUES_INFO = {
    "Premier_League": {"id": "9", "slug": "Premier-League"},
    "Serie_A": {"id": "11", "slug": "Serie-A"},
    "La_Liga": {"id": "12", "slug": "La-Liga"},
    "Ligue_1": {"id": "13", "slug": "Ligue-1"},
    "Bundesliga": {"id": "20", "slug": "Bundesliga"}
}

# Categories and their URL slug parts
CATEGORIES = {
    "Advanced Goalkeeping": "keepersadv",
    "Shooting": "shooting",
    "Passing": "passing",
    "Pass Types": "passing_types",
    "Goal and Shot Creation": "gca",
    "Defensive Actions": "defense",
    "Possession": "possession",
    "Playing Time": "playingtime",
    "Miscellaneous Stats": "misc"
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
        # tqdm.write(f"  Fetching {url}...")
        # Add random delay before request
        time.sleep(random.uniform(3, 6))
        
        driver.get(url)
        time.sleep(5) # Wait for JS
        
        # Check for Cloudflare Challenge
        retries = 0
        while "Verify you are human" in driver.page_source or "Just a moment..." in driver.title:
            if retries == 0:
                print(f"  [!] Cloudflare Challenge Detected! Please solve the CAPTCHA in the browser window.")
                tqdm.write(f"  [!] Cloudflare Challenge Detected! Please solve the CAPTCHA.")
            time.sleep(5)
            retries += 1
            if retries > 60: # Wait up to 5 minutes
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
        tqdm.write(f"  Exception: {e}")
    return None

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

def process_table(soup, category_slug):
    """Finds and processes the specific stats table."""
    
    mapping_fix = {
        "keepersadv": "keeper_adv",
        "passing_types": "passing_types",
        "gca": "gca",
        "defense": "defense",
        "playingtime": "playing_time",
        "misc": "misc"
    }
    
    search_term = mapping_fix.get(category_slug, category_slug)
    
    tables = soup.find_all('table')
    target_table = None

    for t in tables:
        tid = t.get('id', '')
        if f"stats_{search_term}" in tid:
            target_table = t
            break
            
    if not target_table:
        # tqdm.write(f"    Could not find table for {category_slug} (search term: {search_term})")
        return None

    try:
        df = pd.read_html(StringIO(str(target_table)))[0]
        df = clean_header(df)
        
        # Remove repeated headers in data rows
        if 'Player' in df.columns:
            df = df[df['Player'] != 'Player']
            
        df = df.dropna(how='all', axis=1) # Drop empty cols
        return df
    except Exception as e:
        tqdm.write(f"    Error parsing table: {e}")
        return None

def main():
    if not os.path.exists(OUTPUT_DIR):
        print(f"Error: Output directory '{OUTPUT_DIR}' does not exist. Please run previous scraper first.")
        # Create it if it doesn't exist? usually scrape_all_stats creates it.
        os.makedirs(OUTPUT_DIR, exist_ok=True)

    driver = setup_driver()

    try:
        # Total operations = Leagues * Categories
        total_ops = len(LEAGUES_INFO) * len(CATEGORIES)
        
        with tqdm(total=total_ops, desc="Overall Progress", unit="sheet") as pbar:
            for league_name, info in LEAGUES_INFO.items():
                league_id = info["id"]
                league_slug = info["slug"]
                
                file_path = os.path.join(OUTPUT_DIR, f"{league_name}_Stats.xlsx")
                tqdm.write(f"\nProcessing {league_name} -> {file_path}")
                
                if not os.path.exists(file_path):
                    tqdm.write(f"  Warning: File {file_path} not found. Skipping.")
                    pbar.update(len(CATEGORIES)) # Skip all these ops
                    continue

                try:
                     # We need to append to existing Excel file.
                     # pd.ExcelWriter in mode='a' allows appending new sheets.
                     # We must use engine='openpyxl'.
                     with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                        
                        for cat_name, cat_slug in CATEGORIES.items():
                            # tqdm.write(f"  Category: {cat_name}...")
                            pbar.set_description(f"Scraping {league_name}: {cat_name}")
                            
                            # Construct URL
                            # Format: https://fbref.com/en/comps/{id}/{slug}/{league-slug}-Stats
                            url = f"https://fbref.com/en/comps/{league_id}/{cat_slug}/{league_slug}-Stats"
                            
                            soup = get_soup(driver, url)
                            if not soup:
                                pbar.update(1)
                                continue
                                
                            df = process_table(soup, cat_slug)
                            
                            if df is not None:
                                # Sheet names must be <= 31 chars
                                safe_sheet_name = cat_name[:31] 
                                try:
                                    df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
                                    # tqdm.write(f"    Saved sheet '{safe_sheet_name}' ({len(df)} rows)")
                                except Exception as e:
                                    tqdm.write(f"    Error writing sheet {safe_sheet_name}: {e}")
                            else:
                                tqdm.write(f"    Skipping save (no data) for {cat_name}")
                            
                            pbar.update(1)
                                
                except PermissionError:
                    tqdm.write(f"  ERROR: Could not write to {file_path}. Is the file open in Excel? Please close it and retry.")
                    pbar.update(len(CATEGORIES))
                except Exception as e:
                    tqdm.write(f"  Critical Error processing {league_name}: {e}")
                    pbar.update(len(CATEGORIES))
    finally:
        driver.quit()

    print("\nDone.")

if __name__ == "__main__":
    main()
