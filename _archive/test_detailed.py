import cloudscraper
import pandas as pd
from bs4 import BeautifulSoup, Comment
import time
import random

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
url = "https://fbref.com/en/comps/9/shooting/Premier-League-Stats"

print(f"Testing detailed stats access to {url}...")
try:
    response = scraper.get(url)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
    else:
        print("Failed.")
except Exception as e:
    print(f"Error: {e}")
