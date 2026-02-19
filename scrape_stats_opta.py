import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import urllib.parse
import traceback

# --- Configuration ---
LEAGUE_MAP = {
    "https://theanalyst.com/competition/bundesliga/stats": "Bundesliga",
    "https://theanalyst.com/competition/premier-league/stats": "Premier_League",
    "https://theanalyst.com/competition/la-liga/stats": "La_Liga",
    "https://theanalyst.com/competition/serie-a/stats": "Serie_A",
    "https://theanalyst.com/competition/ligue-1/stats": "Ligue_1"
}

CATEGORIES = [
    "Attacking",
    "Passing",
    "Defending",
    "Carrying",
    "Goalkeeping"
]



# --- Configuration ---
OUTPUT_DIR = "output_opta"
FORCE_UPDATE = False # Set to True to overwrite existing files (Weekly Update Mode)

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def get_team_links(driver, league_url):
    """
    Navigates to the league stats page, clicks 'TEAMS', and extracts team URLs.
    Uses robust probing logic.
    """
    print(f"  Accessing League: {league_url}")
    driver.get(league_url)
    time.sleep(10) # Give it good time

    # 1. Handle Cookie Banner
    try:
        driver.execute_script("document.getElementById('usercentrics-cmp-ui').remove()")
    except:
        pass

    # 2. Click "TEAMS" button
    clicked = False
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                txt = btn.text.strip()
                if txt and "TEAMS" in txt.upper():
                    print(f"  Found button: '{txt}'. Clicking...")
                    btn.click()
                    clicked = True
                    time.sleep(5)
                    break
            except:
                continue
        
        if not clicked:
            print("  Could not find 'TEAMS' button via iteration. Trying XPath fallback...")
            teams_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'TEAMS') or contains(text(), 'Teams')]"))
            )
            teams_btn.click()
            time.sleep(5)

    except Exception as e:
        print(f"  Error clicking TEAMS button: {e}")
        # Capture screenshot for debug
        driver.save_screenshot(f"debug_error_teams_{league_url.split('/')[-2]}.png")
        return []

    # 3. Extract Links
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    links = soup.find_all('a', href=True)
    
    team_links = set()
    for link in links:
        href = link['href']
        # Filter for actual team pages (avoiding generic links)
        if '/football/team/' in href:
            full_url = urllib.parse.urljoin(league_url, href)
            team_links.add(full_url)
            
    print(f"  Found {len(team_links)} unique teams.")
    return list(team_links)

def scrape_team_stats(driver, team_url):
    """
    Visits a team's page, navigates to stats, and scrapes all categories.
    Implements state reset to avoid 'Super Table' issue.
    """
    # Ensure we are on the stats page
    if not team_url.endswith("/stats"):
        stats_url = f"{team_url}/stats"
    else:
        stats_url = team_url
        
    print(f"    Scraping Team: {stats_url}")
    
    # 0. State Reset (Critical Factor)
    try:
        driver.delete_all_cookies()
        driver.get("about:blank")
        time.sleep(1)
    except:
        pass
        
    # 1. Navigate
    driver.get(stats_url)
    time.sleep(8) # Increased from 5 to 8 for stability
    
    # Check if page exists/loaded
    if "404" in driver.title:
        print("      Page not found (404).")
        return None

    cat_dfs = {}

    for cat in CATEGORIES:
        # Retry loop for Super Table issue
        for attempt in range(2):
            # 1. Switch Category
            if cat != "Attacking": # Attacking is default
                try:
                     # Strategy 3: Click React Select Container
                     dropdown_container = WebDriverWait(driver, 5).until(
                         EC.presence_of_element_located((By.CLASS_NAME, "react-select__single-value"))
                     )
                     current_text = dropdown_container.text.strip()
                     
                     if current_text != cat:
                         dropdown_container.click()
                         time.sleep(1)
                         option = driver.find_element(By.XPATH, f"//div[contains(@class, 'react-select__option') and text()='{cat}']")
                         option.click()
                         time.sleep(3) 
                except Exception as e:
                    print(f"      Switching to {cat} failed: {e}")

            # 2. Extract Data
            try:
                # Use pandas to read HTML directly (handles colspan/rowspan better)
                # We need to wrap table html in StringIO or pass string
                from io import StringIO
                
                # Check for table presence first manually to avoid waiting
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                table_element = soup.find('table')
                
                if table_element:
                    html_io = StringIO(str(table_element))
                    dfs = pd.read_html(html_io)
                    
                    if dfs:
                        df = dfs[0]
                        
                        # Check "Super Table" by column count
                        if len(df.columns) > 25:
                             print(f"      [WARN] Detected Super Table ({len(df.columns)} columns). Retrying...")
                             driver.refresh()
                             time.sleep(5)
                             continue
                        
                        # Clean columns (handle MultiIndex if any, though likely flat)
                        # If headers are empty, pandas names them "Unnamed: X".
                        # We might needed to standardize names? 
                        # User wants mapped columns. 
                        # Let's keep raw for now, data is safer.
                        
                        # Clean columns (Flatten MultiIndex correctly)
                        new_cols = []
                        for col in df.columns:
                            # If MultiIndex, col is a tuple
                            if isinstance(col, tuple):
                                clean_parts = [str(p).strip() for p in col if "Unnamed" not in str(p) and str(p).strip() != ""]
                                if not clean_parts:
                                    new_cols.append("Unknown")
                                elif len(clean_parts) == 1:
                                    new_cols.append(clean_parts[0])
                                else:
                                    new_cols.append("_".join(clean_parts))
                            else:
                                new_cols.append(str(col).strip())
                        
                        df.columns = new_cols
                        
                        cat_dfs[cat] = df
                        break # Success
            except Exception as e:
                print(f"      Table extraction failed for {cat}: {e}")
        
    return cat_dfs

def clean_team_name(url):
    # url example: .../football/team/scm-156/bayern-munchen
    # parts: ['football', 'team', 'scm-156', 'bayern-munchen']
    try:
        parts = url.rstrip('/').split('/')
        name_slug = parts[-1]
        name = name_slug.replace('-', ' ').title()
        return name
    except:
        return "Unknown_Team"

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    driver = setup_driver()
    
    try:
        for league_url, league_name in LEAGUE_MAP.items():
            print(f"--- Starting {league_name} ---")
            
            # Setup League Directory
            league_dir = os.path.join(OUTPUT_DIR, league_name)
            if not os.path.exists(league_dir):
                os.makedirs(league_dir)
            
            # 1. Get All Teams
            team_links = get_team_links(driver, league_url)
            
            if not team_links:
                print(f"No teams found for {league_name}. Skipping.")
                continue
            
            # Use list to iterate
            team_links = list(team_links)
            
            # 2. Process Each Team
            for team_url in team_links:
                team_name = clean_team_name(team_url)
                file_path = os.path.join(league_dir, f"{team_name}.xlsx")
                
                # Check if already done (Resume capability)
                # Check if already done (Resume capability)
                if not FORCE_UPDATE and os.path.exists(file_path):
                    print(f"    Skipping {team_name} (Already exists)")
                    continue
                
                print(f"Processing {team_name}...")
                
                # Scrape
                try:
                    stats_data = scrape_team_stats(driver, team_url)
                    
                    if stats_data:
                        print(f"    Got data for categories: {list(stats_data.keys())}")
                        
                        # Save to Excel
                        # Use openpyxl explicitly
                        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                            for cat, df in stats_data.items():
                                df.to_excel(writer, sheet_name=cat, index=False)
                                
                        # Check file size immediately
                        if os.path.exists(file_path):
                            size = os.path.getsize(file_path)
                            if size < 100:
                                print(f"    [ERROR] File created but size is {size} bytes: {file_path}")
                                # Try deleting it so we know it failed
                                os.remove(file_path)
                            else:
                                print(f"    Saved {team_name}.xlsx ({size} bytes)")
                    else:
                        print(f"    No data for {team_name}")
                        
                except Exception as e:
                    print(f"    Error processing {team_name}: {e}")
                    traceback.print_exc()

            print(f"Finished {league_name}.\n")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
