import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://fbref.com/en/squads/b8fd03ef/2023-2024/matchlogs/c9/schedule/Manchester-City-Match-Logs-Premier-League"
headers = {'User-Agent': 'Mozilla/5.0'}
resp = requests.get(url, headers=headers)
soup = BeautifulSoup(resp.content, 'html.parser')

table = soup.find('table', id=lambda x: x and 'matchlogs' in x)
if table:
    print("Found table:", table.get('id'))
    thead = table.find('thead')
    if thead:
        trs = thead.find_all('tr')
        if len(trs) > 0:
            last_tr = trs[-1] # Usually the bottom most header row has the actual names
            for th in last_tr.find_all('th'):
                text = th.text.strip()
                aria = th.get('aria-label', '')
                tip = th.get('data-tip', '')
                print(f"Col: {text} | aria-label: {aria} | data-tip: {tip}")
else:
    print("No table found")
