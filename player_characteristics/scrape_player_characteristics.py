import os
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import sys

# --- Configuration ---
OUTPUT_DIR = "player_characteristics"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

LEAGUE_URLS = {
    "Ligue_1": "https://www.whoscored.com/regions/74/tournaments/22/france-ligue-1",
    "Premier_League": "https://www.whoscored.com/regions/252/tournaments/2/england-premier-league",
    "La_Liga": "https://www.whoscored.com/regions/206/tournaments/4/spain-laliga",
    "Serie_A": "https://www.whoscored.com/regions/108/tournaments/5/italy-serie-a",
    "Bundesliga": "https://www.whoscored.com/regions/81/tournaments/3/germany-bundesliga"
}

# --- Selenium Setup ---
def setup_driver():
    options = Options()
    # options.add_argument("--headless") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Use webdriver_manager to automatically install/locate driver
    service = Service(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=options)
    return driver

# --- Helper Functions ---
def random_sleep(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def log(msg):
    print(msg)
    sys.stdout.flush()


def extract_characteristics(soup):
    """
    Extracts strengths, weaknesses, and style of play from the player page soup.
    """
    characteristics = {
        "Strengths": [],
        "Weaknesses": [],
        "Style of Play": []
    }
    
    try:
        # Strengths
        for item in soup.select(".strengths .character"):
            name_div = item.find("div")
            rating_span = item.select_one(".sws-level-wrapper span")
            if name_div:
                text = name_div.get_text(strip=True)
                if rating_span:
                    text += f" ({rating_span.get_text(strip=True)})"
                characteristics["Strengths"].append(text)

        # Weaknesses
        for item in soup.select(".weaknesses .character"):
            name_div = item.find("div")
            rating_span = item.select_one(".sws-level-wrapper span")
            if name_div:
                text = name_div.get_text(strip=True)
                if rating_span:
                    text += f" ({rating_span.get_text(strip=True)})"
                characteristics["Weaknesses"].append(text)
                         
        # Style of Play
        for item in soup.select(".style .character"):
             # Style usually is a list item or div inside
             # The structure is often <li> or <div> inside .style .character
             # Based on inspection: .style .character contains the text directly or in a child div
             text = item.get_text(strip=True)
             if text:
                  characteristics["Style of Play"].append(text)

    except Exception as e:
        log(f"Error parsing characteristics: {e}")
        
    return characteristics

def scrape_league(driver, league_name, league_url):
    log(f"Scraping League: {league_name}")
    driver.get(league_url)
    random_sleep(3, 5)
    
    # 1. Get all teams
    # We need to find the table with team links.
    # Usually in the 'Standings' tab which is default.
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Selector for team links. Usually 'a.team-link' or similar inside the standings table.
    # Let's try a general selector for links containing 'teams' in href
    team_links = []
    
    # Specific to WhoScored standings table
    # <a href="/teams/44/germany-borussia-dortmund" class="team-link">Borussia Dortmund</a>
    
    seen_urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/teams/" in href and "show" in href: # e.g., /teams/44/show/Borussia-Dortmund
            full_url = "https://www.whoscored.com" + href
            if full_url not in seen_urls:
                team_name = a.get_text(strip=True)
                if team_name: # Ensure it has text
                    # Identify valid team link (sometimes there are duplicates or image links)
                    team_links.append((team_name, full_url))
                    seen_urls.add(full_url)
    
    log(f"Found {len(team_links)} teams.")
    
    # Prepare Excel Writer
    output_file = os.path.join(OUTPUT_DIR, f"{league_name}_Characteristics.xlsx")
    
    # Create a dummy dataframe to initialize writer if we want to append, 
    # but here we are creating fresh for the league.
    # We will use a dictionary to store dfs and save at end, or save incrementally?
    # Saving incrementally is safer.
    
    for team_name, team_url in team_links:
        log(f"  Scraping Team: {team_name}")
        try:
            scrape_team(driver, team_name, team_url, output_file)
        except Exception as e:
            print(f"  Error scraping team {team_name}: {e}")
        
        random_sleep(2, 4)

def scrape_team(driver, team_name, team_url, output_file):
    driver.get(team_url)
    random_sleep(3, 5)
    
    # 2. Get Players
    # Need to go to "Squad" tab usually? Or is the squad listed on summary?
    # WhoScored usually has a squad list on the summary page (top players) 
    # but strictly we might want the full squad.
    # The URL often defaults to 'Summary'. 'Squad' tab might be needed better coverage.
    # Let's try to extract from the visible summary table first (usually 'Player Statistics').
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    player_links = []
    
    # Look for player links: /players/123/show/Player-Name
    seen_players = set()
    
    # Determine if we need to click "Squad" or "Statistics" tab?
    # For now, let's grab whatever players are linked on the main team page.
    # This usually includes the starting XI + subs from recent games or 'Top Performers'.
    # For a full list, we might need to navigate.
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/players/" in href and "show" in href:
            full_url = "https://www.whoscored.com" + href
            if full_url not in seen_players:
                player_name = a.get_text(strip=True)
                if player_name:
                    player_links.append((player_name, full_url))
                    seen_players.add(full_url)
    
    print(f"    Found {len(player_links)} players potential links (deduping needed potentially).")
    
    team_data = []
    
    # Slice for testing?
    # player_links = player_links[:3] 
    
    for player_name, player_url in player_links:
        print(f"    Scraping Player: {player_name}")
        try:
            driver.get(player_url)
            random_sleep(2, 3) # Short sleep
            
            p_soup = BeautifulSoup(driver.page_source, "html.parser")
            chars = extract_characteristics(p_soup)
            
            # Format as string
            s_str = ", ".join(chars["Strengths"])
            w_str = ", ".join(chars["Weaknesses"])
            sty_str = ", ".join(chars["Style of Play"])
            
            team_data.append({
                "Player": player_name,
                "URL": player_url,
                "Strengths": s_str,
                "Weaknesses": w_str,
                "Style of Play": sty_str
            })
            
        except Exception as e:
            print(f"    Failed to scrape player {player_name}: {e}")
    
    # Save to Sheet
    if team_data:
        df = pd.DataFrame(team_data)
        
        # Safe sheet name (max 31 chars)
        sheet_name = team_name[:31].replace(":", "").replace("/", "")
        
        # Write to Excel
        # Check if file exists to append or create
        if os.path.exists(output_file):
            with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        else:
             with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
        print(f"    Saved {len(df)} players to sheet '{sheet_name}'")
    else:
        print("    No player data found.")

# --- Main Execution ---
def main():
    driver = setup_driver()
    try:
        for name, url in LEAGUE_URLS.items():
            scrape_league(driver, name, url)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
