import json
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"
OUTPUT_FILE = FIXTURE_DIR / "countries_raw.json"
# print(FIXTURE_DIR)

def fetch_countries():
    print("Fetching country data...")
    try:
        FIXTURE_DIR.mkdir(exist_ok=True)
        
        req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"Data saved to {OUTPUT_FILE}")
    
    except Exception as e:
        print(f"An error occurred: {e}")
if __name__ == "__main__":
    fetch_countries()