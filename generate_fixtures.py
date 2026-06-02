import json
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_JSON_PATH = BASE_DIR / "fixtures" / "countries_raw.json"
OUTPUT_FIXTURE_PATH = BASE_DIR / "fixtures" / "countries.json" # Zápis přímo do kořenové složky fixtures

def convert():
    if not RAW_JSON_PATH.exists():
        print(f"Chyba: {RAW_JSON_PATH} neexistuje.")
        return

    with open(RAW_JSON_PATH, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    django_fixture = []

    for entry in raw_data:
        cca3 = entry.get("cca3")
        cca2 = entry.get("cca2")
        if not cca3 or not cca2:
            continue

        name_data = entry.get("name", {})
        capitals = entry.get("capital", [])
        
        flag_svg = f"https://flagcdn.com/{cca2.lower()}.svg"
        flag_png = f"https://flagcdn.com/w320/{cca2.lower()}.png"

        fixture_item = {
            "model": "app.country",
            "pk": cca3,
            "fields": {
                "cca2": cca2,
                "name_common": name_data.get("common", "Unknown"),
                "name_official": name_data.get("official", "Unknown"),
                "capital": capitals[0] if capitals else "",
                "region": entry.get("region", ""),
                "subregion": entry.get("subregion", ""),
                "population": entry.get("population", 0),
                "area_km2": entry.get("area"),
                "flag_svg": flag_svg,
                "flag_png": flag_png,
                "is_independent": entry.get("independent") is True,
                "upvotes": random.randint(10, 500),
                "downvotes": random.randint(0, 100)
            }
        }
        django_fixture.append(fixture_item)

    with open(OUTPUT_FIXTURE_PATH, "w", encoding="utf-8") as f:
        json.dump(django_fixture, f, ensure_ascii=False, indent=4)

    print(f"Fixture vygenerována do kořenového: {OUTPUT_FIXTURE_PATH}")

if __name__ == "__main__":
    convert()