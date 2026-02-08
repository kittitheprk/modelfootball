import pandas as pd
from bs4 import BeautifulSoup, Comment
import time
import os
import random
import re
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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
    "Shooting": "shooting",
    "Goalkeeping": "keeper",
    "Passing": "passing",
    "Pass Types": "passing_types",
    "Goal and Shot Creation": "gca",
    "Defensive Actions": "defense",
    "Possession": "possession",
    "Miscellaneous Stats": "misc"
}

# Selenium Setup
def setup_driver():
    options = Options()
    # options.add_argument("--headless") # Run in headless mode (optional, good for automation)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    # Hide selenium detection
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })
    return driver

def get_soup(driver, url, max_retries=3):
    """Fetches the URL and returns a BeautifulSoup object."""
    # With selenium, retries are handled by loading page. If page loads error, we can check title?
    # FBref often redirects to 'Just a moment...' 
    # The driver.get returns when onload fires.
    
    try:
        # Random delay
        time.sleep(random.uniform(3, 5))
        
        driver.get(url)
        time.sleep(5)
        
        # Check for Cloudflare Challenge
        retries = 0
        while "Verify you are human" in driver.page_source or "Just a moment..." in driver.title:
            if retries == 0:
                 print(f"  [!] Cloudflare Challenge Detected! Please solve the CAPTCHA.")
            time.sleep(5)
            retries += 1
            if retries > 60: # Wait up to 5 minutes
                 break

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

def clean_header(df):
    """Flattens multi-level columns."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns:
            # col is tuple ('Unnamed: 0_level_0', 'Date') or ('Performance', 'Gls')
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

def get_team_urls(driver, league_url):
    """Scrapes the league page to get a dict of {TeamName: RelativeURL}."""
    soup = get_soup(driver, league_url)
    if not soup:
        return {}
    
    teams = {}
    for link in soup.select("table tbody tr th a"):
        href = link.get('href')
        if href and '/squads/' in href:
            team_name = link.text.strip()
            teams[team_name] = href 
            
    if not teams:
        for td in soup.select("td[data-stat='team'] a"):
            href = td.get('href')
            if href and '/squads/' in href:
                team_name = td.text.strip()
                teams[team_name] = href 
    return teams

def process_team(driver, league_name, team_name, team_rel_url):
    """
    Scrapes all match log categories for a single team.
    Saves directly to Excel.
    """
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
                        df = pd.read_html(str(table))[0]
                        df = clean_header(df)
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
    if not os.path.exists(BASE_OUTPUT_DIR):
        os.makedirs(BASE_OUTPUT_DIR)
        
    print(f"Starting Match Logs Scrape for {len(USER_LEAGUE_URLS)} leagues...")
    
    driver = setup_driver()
    try:
        for league_name, league_url in USER_LEAGUE_URLS.items():
            print(f"\nProcessing League: {league_name}")
            
            teams = get_team_urls(driver, league_url)
            print(f"  Found {len(teams)} teams.")
            
            for team_name, team_rel_url in tqdm(teams.items(), desc=f"Teams in {league_name}", unit="team"):
                process_team(driver, league_name, team_name, team_rel_url)
    finally:
        driver.quit()
    
    print("\nAll scraping completed.")

if __name__ == "__main__":
    main()
