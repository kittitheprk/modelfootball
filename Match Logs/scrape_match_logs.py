import tkinter as tk
from tkinter import ttk
import os
import time
import random
import re
from bs4 import BeautifulSoup, Comment
from tqdm import tqdm
import undetected_chromedriver as uc
import undetected_chromedriver as uc
import pandas as pd
from io import StringIO

# --- Configuration ---
BASE_OUTPUT_DIR = "Match Logs"
USER_LEAGUE_URLS = {
    "Premier_League": "https://fbref.com/en/comps/9/stats/Premier-League-Stats",
    "Serie_A": "https://fbref.com/en/comps/11/stats/Serie-A-Stats",
    "La_Liga": "https://fbref.com/en/comps/12/stats/La-Liga-Stats",
    "Ligue_1": "https://fbref.com/en/comps/13/stats/Ligue-1-Stats",
    "Bundesliga": "https://fbref.com/en/comps/20/stats/Bundesliga-Stats"
}

# Categories to scrape and their URL slug components
CATEGORIES = {
    "Scores & Fixtures": "schedule",
    "Shooting": "shooting",
    "Goalkeeping": "keeper",
    "Miscellaneous Stats": "misc"
}

# Global Popup Instance
POPUP = None

class StatusPopup:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Match Logs Scraper Status")
        self.root.geometry("450x180")
        self.root.attributes("-topmost", True) # Always on top
        
        self.style = ttk.Style()
        self.style.theme_use('default')
        
        self.lbl_header = tk.Label(self.root, text="Initializing...", font=("Arial", 10))
        self.lbl_header.pack(pady=5)
        
        self.lbl_detail = tk.Label(self.root, text="Preparing...", font=("Arial", 12, "bold"), wraplength=400)
        self.lbl_detail.pack(pady=5)
        
        self.progress = ttk.Progressbar(self.root, length=400, mode='determinate')
        self.progress.pack(pady=10)
        
        self.lbl_footer = tk.Label(self.root, text="Please do not close this window.", font=("Arial", 8), fg="gray")
        self.lbl_footer.pack(side=tk.BOTTOM, pady=5)
        
        self.root.update()

    def update_text(self, header, detail, progress_val=None, color="black"):
        try:
            self.lbl_header.config(text=header)
            self.lbl_detail.config(text=detail, fg=color)
            if progress_val is not None:
                self.progress['value'] = progress_val
            self.root.update()
        except:
            pass

    def close(self):
        try:
            self.root.destroy()
        except:
            pass

# Undetected ChromeDriver Setup (bypasses Cloudflare)
def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = uc.Chrome(options=options, version_main=144)
    return driver

def get_soup(driver, url, max_retries=3):
    """Fetches the URL and returns a BeautifulSoup object."""
    try:
        # Update popup if exists
        if POPUP:
            POPUP.update_text(f"Fetching Data...", f"{url.split('/')[-1]}", color="blue")
            
        # Random delay
        time.sleep(random.uniform(3, 5))
        
        driver.get(url)
        time.sleep(5)
        
        # Check for Cloudflare Challenge
        if "Verify you are human" in driver.page_source or "Just a moment..." in driver.title:
            print(f"\n" + "="*50)
            print(f"  [!] CLOUDFLARE DETECTED on {url}")
            print(f"  [!] Please solve the CAPTCHA in the browser window manually.")
            print(f"="*50 + "\n")
            
            if POPUP:
                POPUP.update_text("⚠️ ACTION REQUIRED ⚠️", "CLOUDFLARE DETECTED!\nPlease solve CAPTCHA in browser.", color="red")
            
            while "Verify you are human" in driver.page_source or "Just a moment..." in driver.title:
                time.sleep(5)
                # Keep popup alive
                if POPUP: POPUP.root.update()
                
                try:
                    # Check if page title normalized
                    if "FBref" in driver.title or "Stats" in driver.title:
                        print("  [+] Cloudflare passed! Resuming...")
                        if POPUP:
                            POPUP.update_text("Success", "Cloudflare Passed! Resuming...", color="green")
                        break
                except:
                    pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Un-comment hidden tables
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            if '<table' in comment:
                comment_soup = BeautifulSoup(comment, 'html.parser')
                if soup.body:
                    soup.body.append(comment_soup)
        return soup

    except Exception as e:
        print(f"  Exception fetching {url}: {e}")
        time.sleep(5)
    return None

def extract_column_mapping(table_soup):
    """Extracts a mapping of short column names to their full aria-label names."""
    mapping = {}
    thead = table_soup.find('thead')
    if thead:
        trs = thead.find_all('tr')
        if len(trs) > 0:
            last_tr = trs[-1] # Usually the bottom most header row has the actual names
            for th in last_tr.find_all(['th', 'td']):
                short_name = th.text.strip()
                full_name = th.get('aria-label', '').strip()
                if full_name and full_name != short_name:
                    mapping[short_name] = full_name
                else:
                    mapping[short_name] = short_name
    return mapping

def clean_header(df, col_mapping=None):
    """Flattens multi-level columns and renames to full columns if mapping provided."""
    if col_mapping is None:
        col_mapping = {}

    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            # col is tuple ('Unnamed: 0_level_0', 'Date') or ('Performance', 'Gls')
            c0 = str(col[0]).strip()
            c1 = str(col[1]).strip()
            
            c1_mapped = col_mapping.get(c1, c1)
            c0_mapped = col_mapping.get(c0, c0)
            
            if "Unnamed" in c0:
                new_cols.append(c1_mapped)
            elif "Unnamed" in c1:
                new_cols.append(c0_mapped)
            else:
                new_cols.append(f"{c0}_{c1_mapped}")
        df.columns = new_cols
    else:
        df.columns = [col_mapping.get(str(c).strip(), str(c).strip()) for c in df.columns]
        
    # Handle duplicates by appending _1, _2
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        cols[cols[cols == dup].index.values.tolist()] = [dup + '_' + str(i) if i != 0 else dup for i in range(sum(cols == dup))]
    df.columns = cols
    
    return df

def get_team_urls(driver, league_url):
    """Scrapes the league page to get a dict of {TeamName: RelativeURL}."""
    if POPUP:
        POPUP.update_text("Scanning League", "Finding Teams...", color="black")
        
    soup = get_soup(driver, league_url)
    if not soup:
        return {}
    
    teams = {}
    seen_hrefs = set()
    
    # Helper to add team
    def add_team(name, link):
        if not link or not isinstance(name, str):
            return
        
        clean_name = name.strip()
        if link in seen_hrefs:
            return
        if clean_name.lower().startswith("vs ") or "match report" in clean_name.lower():
            return
            
        teams[clean_name] = link
        seen_hrefs.add(link)

    for link in soup.select("table tbody tr th a"):
        href = link.get('href')
        if href and '/squads/' in href:
            add_team(link.text, href)
            
    if not teams:
        for td in soup.select("td[data-stat='team'] a"):
            href = td.get('href')
            if href and '/squads/' in href:
                add_team(td.text, href)
                
    return teams

def process_team(driver, league_name, team_name, team_rel_url):
    """
    Scrapes all match log categories for a single team.
    Saves directly to Excel.
    """
    # Popup update handled in loop mostly, but can add detail here
    
    team_full_url = f"https://fbref.com{team_rel_url}"
    soup = get_soup(driver, team_full_url)
    if not soup:
        return
    
    clean_league_name = league_name.replace("_", " ")
    match_log_link = None
    potential_links = []

    target_text = f"Match Logs ({clean_league_name})"
    for a in soup.find_all('a', href=True):
        if target_text in a.text:
            match_log_link = a['href']
            break
        if "Match Logs" in a.text:
            potential_links.append((a.text, a['href']))
            
    if not match_log_link and potential_links:
        tqdm.write(f"  Warning: Specific link '{target_text}' not found for {team_name}. using first generic match.")
        match_log_link = potential_links[0][1]

    if not match_log_link:
        for a in soup.find_all('a', href=True):
            if "/matchlogs/" in a['href'] and "schedule" in a['href']:
                match_log_link = a['href']
                break

    if not match_log_link:
        tqdm.write(f"  Error: No Match Log link found for {team_name}. Skipping.")
        return

    match = re.search(r"/squads/([^/]+)/([^/]+)/matchlogs/([^/]+)/schedule/(.*)", match_log_link)
    
    if match:
        team_id, season, comp_id, url_slug_end = match.groups()
    else:
        # Try finding non-schedule match log
        parts = match_log_link.split('/')
        if len(parts) >= 9 and 'matchlogs' in parts:
           idx = parts.index('matchlogs')
           team_id = parts[idx-2]
           season = parts[idx-1]
           comp_id = parts[idx+1]
           base_slug = parts[-1] 
        else:
           return

    base_slug = match_log_link.split('/')[-1]
    base_slug = base_slug.replace("Scores-and-Fixtures", "Match-Logs")
    
    out_dir = os.path.join(BASE_OUTPUT_DIR, league_name)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{team_name}.xlsx")
    
    try:
        with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
            data_saved = False
            for cat_name, cat_slug in CATEGORIES.items():
                if match:
                    cat_url = f"https://fbref.com/en/squads/{team_id}/{season}/matchlogs/{comp_id}/{cat_slug}/{base_slug}"
                else:
                    cat_url = f"https://fbref.com{match_log_link.replace('/schedule/', f'/{cat_slug}/')}"
                    cat_url = cat_url.replace("Scores-and-Fixtures", "Match-Logs")

                cat_soup = get_soup(driver, cat_url)
                if not cat_soup:
                    continue
                
                table = cat_soup.find('table', id="matchlogs_for")
                if not table:
                    for t in cat_soup.find_all('table'):
                        if 'matchlogs' in t.get('id', ''):
                            table = t
                            break
                
                if table:
                    try:
                        col_mapping = extract_column_mapping(table)
                        df = pd.read_html(StringIO(str(table)))[0]
                        df = clean_header(df, col_mapping)
                        if 'Date' in df.columns:
                            df = df[df['Date'] != 'Date']
                        
                        sheet_name = cat_name[:31] 
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        data_saved = True
                    except Exception as e:
                        tqdm.write(f"      Error parsing table for {cat_name}: {e}")
                else:
                    pass # Silently skip missing tables
            
            if not data_saved:
                tqdm.write(f"  Warning: No data saved for {team_name}")
                
    except Exception as e:
        tqdm.write(f"  Error writing file for {team_name}: {e}")

def main():
    global POPUP
    
    if not os.path.exists(BASE_OUTPUT_DIR):
        os.makedirs(BASE_OUTPUT_DIR)
        
    print(f"Starting Match Logs Scrape for {len(USER_LEAGUE_URLS)} leagues...")
    
    # Initialize Popup
    try:
        POPUP = StatusPopup()
        POPUP.update_text("Starting Scraper", "Initializing drivers...", 0)
    except Exception as e:
        print(f"Could not initialize popup: {e}")
    
    total_leagues = len(USER_LEAGUE_URLS.items())
    current_league_idx = 0
    
    # Approx total teams (5 leagues * 20 teams = 100) for progress bar
    total_estimated_teams = 100 
    teams_processed_count = 0
    
    try:
        for league_name, league_url in USER_LEAGUE_URLS.items():
            current_league_idx += 1
            print(f"\nProcessing League: {league_name}")
            
            if POPUP:
                POPUP.update_text(f"League {current_league_idx}/{total_leagues}: {league_name}", "Finding teams...")
            
            # Setup driver for finding teams
            driver = setup_driver()
            try:
                teams = get_team_urls(driver, league_url)
            except Exception as e:
                print(f"Error getting teams for {league_name}: {e}")
                driver.quit()
                continue
                
            driver.quit() # Close it to restart fresh for processing
            
            print(f"  Found {len(teams)} unique teams.")
            
            # Convert dict items to a list to iterate with index
            team_items = list(teams.items())
            
            # Process teams in batches to restart driver
            batch_size = 5
            for i in range(0, len(team_items), batch_size):
                batch = team_items[i : i + batch_size]
                
                # Restart driver for this batch
                driver = setup_driver()
                try:
                    for team_name, team_rel_url in batch:
                        # Filter out garbage "vs Team" or "Match Report" if they slipped through
                        if team_name.lower().startswith("vs ") or "match report" in team_name.lower():
                            continue
                            
                        # Update Popup
                        teams_processed_count += 1
                        progress_pct = (teams_processed_count / total_estimated_teams) * 100
                        if progress_pct > 100: progress_pct = 99
                        
                        tqdm.write(f"Processing {team_name}...")
                        if POPUP:
                            POPUP.update_text(f"League: {league_name} ({current_league_idx}/{total_leagues})", 
                                              f"Scraping: {team_name}", 
                                              progress_pct)

                        try:
                            process_team(driver, league_name, team_name, team_rel_url)
                        except Exception as e:
                            tqdm.write(f"  Error processing {team_name}: {e}")
                            
                finally:
                    driver.quit()
                    time.sleep(2) # Cooldown
        
        if POPUP:
            POPUP.update_text("Completed", "All scraping finished!", 100, "green")
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\nScraping interrupted by user.")
    finally:
        if POPUP:
            POPUP.close()
            
    print("\nAll scraping completed.")

if __name__ == "__main__":
    main()
