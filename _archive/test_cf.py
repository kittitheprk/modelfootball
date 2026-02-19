import cloudscraper

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True})
url = "https://fbref.com/en/comps/9/stats/Premier-League-Stats"

print(f"Testing access to {url}...")
try:
    response = scraper.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.text)}")
    if "Verify you are human" in response.text:
        print("Blocked by Cloudflare Turnstile.")
    else:
        print("Success! Content seems valid.")
except Exception as e:
    print(f"Exception: {e}")
