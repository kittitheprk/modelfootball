import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Same setup as before
def setup_driver():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Keep headless for speed, output is text
    options.add_argument("--headless") 
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

CATEGORIES = [
    "Attacking",
    "Passing",
    "Defending", 
    "Carrying",
    "Goalkeeping"
]

def verify_bayern_columns(driver):
    url = "https://theanalyst.com/football/team/scm-1902/hoffenheim/stats"
    print(f"--- Verifying Data from: {url} ---")
    print("Context: We are on the 'Bayern Munich' page, so ALL players found here belong to Bayern Munich.\n")
    
    driver.get(url)
    time.sleep(8) # Wait for initial load
    
    # Handle Cookie Banner (Just in case)
    try:
        driver.execute_script("document.getElementById('usercentrics-cmp-ui').remove()")
    except:
        pass

    for cat in CATEGORIES:
        print(f"Checking Category: [{cat}]")
        
        # 1. Try to switch category
        try:
            print(f"  Attempting to switch to {cat}...")
            # Debug: Print all potential dropdown-like elements
            print("  [DEBUG] Searching for dropdown candidates...")
            candidates = driver.find_elements(By.XPATH, "//div[contains(@class, 'single-value')] | //div[contains(@class, 'control')] | //div[contains(@id, 'react-select')]")
            for c in candidates:
                print(f"  Candidate: '{c.text}' (Class: {c.get_attribute('class')})")

            # Strategy 3: Click the React Select container
            # The class 'react-select__single-value' is the text IN the box, but we need to click the box or the control.
            # Usually the parent of 'single-value' or a sibling 'control'.
            print("  Strategy 3: Clicking React Select Control...")
            try:
                # Try finding the container that holds the current value
                current_val = driver.find_element(By.CLASS_NAME, "react-select__single-value")
                # Click the PARENT or the element itself might work
                current_val.click()
                time.sleep(1)
                
                # Now the menu should be open. Find the option 'Passing', 'Defending' etc.
                # React Select options usually have id starting with 'react-select' or class 'react-select__option'
                print(f"  Menu opened. Looking for option '{cat}'...")
                # Try specific text match in the menu
                option = driver.find_element(By.XPATH, f"//div[contains(@class, 'react-select__option') and text()='{cat}']")
                option.click()
                time.sleep(5)
                
            except Exception as inner_e:
                print(f"  Strategy 3 Failed: {inner_e}")
        except Exception as e:
            print(f"  Error switching to {cat}: {e}")

        # 2. Extract Table Data
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table')
        
        if table:
            # Headers
            headers = [th.text.strip() for th in table.find_all('th')]
            
            # First Row
            rows = table.find_all('tr')
            if len(rows) > 1:
                # Row 0 is header, Row 1 is data
                first_row_cols = [td.text.strip() for td in rows[1].find_all('td')]
                
                # Align them for display
                print(f"  {'COLUMN':<20} | {'VALUE (First Player)'}")
                print(f"  {'-'*20} | {'-'*20}")
                
                # Handle mismatch length if any (though looking for match)
                max_len = max(len(headers), len(first_row_cols))
                for i in range(max_len):
                    h = headers[i] if i < len(headers) else "MISSING"
                    v = first_row_cols[i] if i < len(first_row_cols) else "MISSING"
                    print(f"  {h:<20} | {v}")
            else:
                print("  No data rows found.")
        else:
            print("  No table found.")
        print("\n" + "="*50 + "\n")

def main():
    driver = setup_driver()
    try:
        verify_bayern_columns(driver)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
