import json
import time
import os
import re
import requests
from ddgs import DDGS
from groq import Groq
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from app.models import FlagCollection, Country

load_dotenv()

class Command(BaseCommand):
    help = 'Master AI Agent: Verbose Binding, Multi-language Wiki, and Key Rotation.'

    MODELS = [
        "openai/gpt-oss-120b",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "openai/gpt-oss-20b",
        "llama-3.3-70b-versatile",
        "qwen/qwen3-32b",
        "llama-3.1-8b-instant"
    ]

    def add_arguments(self, parser):
        parser.add_argument('--chunk-size', type=int, default=2)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--reset', action='store_true')

    def extract_json(self, text):
        try:
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match: return json.loads(match.group(1))
            return json.loads(text)
        except: return None

    def fetch_wikipedia_raw(self, title, lang="en"):
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query", "format": "json", "titles": title,
            "prop": "revisions", "rvprop": "content", "rvslots": "main", "redirects": 1
        }
        headers = {'User-Agent': 'JustEnoughFlagsBot/1.0 (Student Project)'}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=5)
            r.raise_for_status() 
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                if page_id != "-1":
                    return page_info["revisions"][0]["slots"]["main"]["*"]
        except: pass
        return ""

    def handle(self, *args, **options):
        # NATAŽENÍ KLÍČŮ
        api_keys = [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]
        if not api_keys:
            legacy = os.getenv("GROQ_API_KEY")
            if legacy: api_keys = [legacy]

        if not api_keys:
            self.stdout.write(self.style.ERROR("Chybí API klíče v .env!"))
            return

        # VERBOSE RESET
        if options['reset']:
            self.stdout.write(self.style.WARNING("🔄 Zahajuji hromadný reset příznaku is_verified v databázi..."))
            self.stdout.flush() # Vynutí okamžitý zápis do logu/terminálu
            
            start_reset = time.time()
            count = FlagCollection.objects.all().update(is_verified=False)
            duration = time.time() - start_reset
            
            self.stdout.write(self.style.SUCCESS(f"✅ Resetováno {count} záznamů za {duration:.2f} sekund."))
            self.stdout.flush()
        ddgs = DDGS()
        flags_to_process = FlagCollection.objects.filter(is_public=True, is_verified=False)
        if options['limit'] > 0: flags_to_process = flags_to_process[:options['limit']]
            
        total = flags_to_process.count()
        self.stdout.write(self.style.NOTICE(f"🚀 Master Agent startuje pro {total} vlajek..."))

        current_model_idx = 0
        current_key_idx = 0
        client = Groq(api_key=api_keys[current_key_idx])
        i = 0
        
        while i < total:
            chunk = flags_to_process[i:i + options['chunk_size']]
            data_to_send = []
            
            for f in chunk:
                self.stdout.write(f"  🔍 Sběr dat (Multilingual Wiki): {f.name}...")
                ctx = ""
                for lang in ["en", "cs", "de"]:
                    raw = self.fetch_wikipedia_raw(f.name, lang=lang)
                    if raw: ctx += f"\n--- WIKI {lang.upper()} ---\n{raw[:1500]}\n"
                
                try:
                    time.sleep(1)
                    res_stats = ddgs.text(f"{f.name} population area", max_results=2)
                    if res_stats: ctx += "\n--- SEARCH ---\n" + " ".join([r.get('body', '') for r in res_stats])
                except: pass

                data_to_send.append({
                    "qid": str(f.wikidata_id), "name": f.name, "current_category": f.category, "web_data": ctx[:5000]
                })

            prompt = f"""
            Act as an elite Data Architect. Process {len(data_to_send)} entities.
            
            STEP 1: CATEGORY & BINDING (MANDATORY)
            - Determine 'new_category' (state, city, region, territory, historical, international).
            - Identify the MODERN SOVEREIGN COUNTRY this belongs to. 
            - IMPORTANT: Even for historical entities, suggest the modern country on whose territory it mostly lay (e.g., 'UZB' for Khwarazm, 'RUS' for Armenian SSR).
            - Return 3-letter ISO code in 'parent_country_iso3'.

            STEP 2: STATISTICS
            - Extract 'population' and 'area_km2'.
            - Provide 'stats_confidence' (0.0 to 1.0).

            STEP 3: MULTILINGUAL DESCRIPTIONS
            - Write exactly 2 sentences in EN, CS, DE.
            - CZECH: Perfect grammar and gender agreement. No robotic phrasing.

            Return ONLY JSON:
            {{"qid": {{"new_category": "...", "parent_country_iso3": "USA", "population": 123, "area_km2": 45, "stats_confidence": 0.9, "description_en": "...", "description_cs": "...", "description_de": "..."}}}}
            
            DATA: {json.dumps(data_to_send)}
            """

            success = False
            while current_model_idx < len(self.MODELS) and not success:
                model_name = self.MODELS[current_model_idx]
                try:
                    self.stdout.write(f"  🤖 Model: {model_name} (Klíč: {current_key_idx+1})")
                    response = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name, temperature=0.0, response_format={"type": "json_object"}
                    )
                    ai_results = self.extract_json(response.choices[0].message.content)
                    if not ai_results: break 

                    for flag in chunk:
                        res = ai_results.get(str(flag.wikidata_id))
                        if res:
                            self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- {flag.name} ---"))
                            flag.category = res.get('new_category', flag.category)
                            
                            # 1. BINDING DEBUG (Uvidíš, co AI navrhuje)
                            iso3 = res.get('parent_country_iso3')
                            if iso3:
                                parent = Country.objects.filter(cca3=iso3.upper()).first()
                                if parent:
                                    flag.country = parent
                                    self.stdout.write(self.style.SUCCESS(f"  [Binding]: Připojeno k {parent.name_common} ({iso3})"))
                                else:
                                    self.stdout.write(self.style.WARNING(f"  [Binding]: AI navrhla {iso3}, ale tento kód není v tabulce Country!"))
                            else:
                                self.stdout.write(self.style.WARNING(f"  [Binding]: AI vrátila null - kód státu nebyl určen."))

                            # 2. STATS
                            conf = res.get('stats_confidence', 0.0)
                            if conf >= 0.5:
                                flag.population = res.get('population')
                                flag.area_km2 = res.get('area_km2')
                            else:
                                flag.population = flag.area_km2 = None
                                self.stdout.write(self.style.WARNING(f"  [Veto]: Statistiky smazány (Jistota: {conf})"))

                            flag.description = {'en': res.get('description_en',''), 'cs': res.get('description_cs',''), 'de': res.get('description_de','')}
                            flag.is_verified = True
                            flag.save()
                    success = True 
                except Exception as e:
                    if "429" in str(e) and current_key_idx < len(api_keys) - 1:
                        current_key_idx += 1
                        client = Groq(api_key=api_keys[current_key_idx])
                        continue
                    else:
                        current_model_idx += 1
                        current_key_idx = 0
                        if current_model_idx < len(self.MODELS): client = Groq(api_key=api_keys[current_key_idx])
                        break 
            
            if current_model_idx >= len(self.MODELS): break
            i += options['chunk_size']
            time.sleep(2)