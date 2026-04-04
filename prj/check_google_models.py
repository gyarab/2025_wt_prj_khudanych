import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Načteme tvůj první klíč
api_key = os.getenv("GOOGLE_API_KEY_1")

if not api_key:
    print("❌ Klíč GOOGLE_API_KEY_1 nebyl nalezen v .env")
    exit()

print("🔍 Ptám se Googlu na přesná jména modelů...\n")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    for model in data.get('models', []):
        # Vyfiltrujeme jen ty, co umí generovat text (generateContent)
        if 'generateContent' in model.get('supportedGenerationMethods', []):
            # Odstraníme prefix 'models/', abys to mohl rovnou zkopírovat do run_ai_agent.py
            clean_name = model['name'].replace('models/', '')
            print(f"✅ {clean_name}")
else:
    print(f"❌ Chyba API: {response.status_code} - {response.text}")