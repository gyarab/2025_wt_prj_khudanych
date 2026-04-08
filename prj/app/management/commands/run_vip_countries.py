import json
import time
import os
import re
import requests
from ddgs import DDGS
from groq import Groq
from openai import OpenAI
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from app.models import FlagCollection, Country

load_dotenv()

class Command(BaseCommand):
    help = '🚀 VIP AI Agent: Komplexní databázová korekce s hlubokou telemetrií.'

    MODELS = [
        {"name": "gemma-3-27b-it", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
        {"name": "gemini-3.1-flash-lite-preview", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
        {"name": "gpt-oss-120b", "provider": "sambanova", "base_url": "https://api.sambanova.ai/v1"},
        {"name": "openai/gpt-oss-120b", "provider": "groq", "base_url": None},
    ]

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Limit zpracovaných zemí')
        parser.add_argument('--reset', action='store_true', help='Reset is_verified pouze pro suverénní státy a teritoria')

    def log(self, message, style=None, inline=False):
        styled = style(message) if style else message
        if inline:
            self.stdout.write(styled, ending="")
        else:
            self.stdout.write(styled + "\n")
        self.stdout.flush()

    def extract_json(self, text):
        try:
            text = re.sub(r'```[a-zA-Z]*\n?|\n?```', '', text).strip()
            start_match = re.search(r'(\[|\{)', text)
            if not start_match: return None
            start_idx = start_match.start()
            for end_idx in range(len(text), start_idx, -1):
                if text[end_idx-1] in ('}', ']'):
                    try:
                        return json.loads(text[start_idx:end_idx])
                    except: continue
            return None
        except: return None

    def fetch_wikipedia_clean(self, title, lang="en"):
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query", 
            "format": "json", 
            "titles": title, 
            "prop": "extracts", 
            "explaintext": 1, 
            "exchars": 7000, 
            "redirects": 1
        }
        # Tímto se představíme Wikipedii, aby nás neblokovala
        headers = {
            'User-Agent': 'JustEnoughFlags/1.0 (Educational Project; Python/Django)'
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=5)
            pages = r.json().get("query", {}).get("pages", {})
            for p_id, p_info in pages.items():
                if p_id != "-1": return p_info.get("extract", "")
        except: pass
        return ""

    def handle(self, *args, **options):
        keys = {
            "google": [os.getenv(f"GOOGLE_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GOOGLE_API_KEY_{j}")],
            "sambanova": [os.getenv(f"SAMBANOVA_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"SAMBANOVA_API_KEY_{j}")],
            "groq": [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]
        }

        if options['reset']:
            self.log("🧹 [BEZPEČNÝ RESET] Vracím vlajky do oběhu (Pouze pro 'sovereign' a 'territory')...", self.style.WARNING)
            FlagCollection.objects.filter(country__status__in=['sovereign', 'territory']).update(is_verified=False)

        ddgs = DDGS()

        countries_qs = Country.objects.filter(
            status__in=['sovereign', 'territory'],
            additional_flags__isnull=False,
            additional_flags__is_verified=False
        ).distinct().order_by('name_common')

        if options['limit'] > 0: 
            countries_qs = countries_qs[:options['limit']]

        countries_list = list(countries_qs)
        total_count = len(countries_list)
        
        self.log(f"🚀 [VIP AI AGENT] Zpracovávám {total_count} států a závislých území.", self.style.NOTICE)

        current_key_indices = {"google": 0, "sambanova": 0, "groq": 0}
        current_model_idx = 0
        i = 0

        while i < total_count:
            if current_model_idx >= len(self.MODELS):
                self.log("💤 Všechny modely vyčerpány. Pauza 60s...", self.style.WARNING)
                time.sleep(60)
                current_model_idx = 0
                continue

            m_cfg = self.MODELS[current_model_idx]
            provider, model_name = m_cfg["provider"], m_cfg["name"]
            
            if not keys.get(provider): 
                current_model_idx += 1
                continue

            k_idx = current_key_indices[provider]
            c_key = keys[provider][k_idx]
            
            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=50.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=50.0)

            c = countries_list[i]
            
            main_flag = c.additional_flags.filter(category__in=['country', 'dependency']).first()
            if not main_flag:
                i += 1
                continue

            self.log(f"\n" + "="*80)
            self.log(f"💎 [{i+1}/{total_count}] | 🤖 {model_name} | 🌍 {c.name_common} ({c.status})")
            
            # --- ZÍSKÁVÁNÍ DAT ---
            ctx = ""
            for lang in ("en", "cs", "de"):
                txt = self.fetch_wikipedia_clean(c.name_common, lang)
                if txt: ctx += f"\n--- WIKI {lang.upper()} ---\n{txt[:5000]}\n"

            try:
                # Upravený vyhledávací dotaz pro DuckDuckGo
                res = ddgs.text(f'"{c.name_common}" current exact population estimate', max_results=5)
                if res: ctx += f"\n--- WEB ---\n{' '.join([r['body'] for r in res])}\n"
            except: pass

            # --- TELEMETRIE KONTEXTU ---
            self.log(self.style.WARNING(f"   📡 [TELEMETRIE] Staženo znaků pro AI: {len(ctx)}"))
            self.log(self.style.WARNING(f"   📡 [TELEMETRIE] Ukázka z nalezených dat: {ctx[:150].strip()}..."))

            region_name = c.region.name if c.region else "Unknown"

            # --- PROMPT ---
            prompt = f"""
            Act as an elite Geopolitical Historian and Data Specialist. Provide PERFECTLY structured JSON data for: {c.name_common} (Status: {c.status}).
            
            CRITICAL RULES:
            1. EXACT NUMBERS: Find the absolute most exact and precise numeric population and area_km2. 
               - If the CONTEXT contains an exact figure (like 40,218,234), use it without rounding.
               - If the CONTEXT only has rounded numbers (like 45 million), IGNORE IT and rely on your own vast internal knowledge base (e.g. World Bank, UN, or CIA World Factbook data) to provide a precise, unrounded figure.
               - DO NOT USE rounded numbers like 40000000 or 45000000.
            2. DESCRIPTIONS: Write EXACTLY 5 sentences per language (EN, CS, DE). Focus on history. NO population/area numbers in the text!
            3. NAMES: Translate country name and capital city perfectly to Czech and German.
            4. SYSTEM OF GOVERNMENT: Provide the exact form of government STRICTLY translated into EN, CS, and DE (e.g., if EN is "Islamic Republic", CS must be "Islámská republika" and DE "Islamische Republik"). If status='territory', use null.
            5. REGION TRANSLATION: Translate the region "{region_name}" to Czech and German (e.g. "Asia" -> "Asie", "Asien").
            6. LANGUAGES (CRITICAL): Review the existing languages. REMOVE any languages that are NOT officially recognized at the national level. Translate language names to EN, CS, DE.
            7. CURRENCIES: Translate currency names to EN, CS, DE. Keep exact codes and symbols.
            8. STRICT JSON OUTPUT ONLY.

            EXISTING DATABASE DATA TO FIX/TRANSLATE:
            Existing Currencies: {c.currencies}
            Existing Languages: {c.languages}

            EXPECTED JSON STRUCTURE:
            {{
              "name_cs": "...",
              "name_de": "...",
              "population": 12345678,
              "area_km2": 123.45,
              "system_of_government_en": "...",
              "system_of_government_cs": "...",
              "system_of_government_de": "...",
              "region_cs": "...",
              "region_de": "...",
              "capital_cs": "...",
              "capital_de": "...",
              "official_languages": {{ "code": {{"en": "...", "cs": "...", "de": "..."}} }},
              "currencies": {{ "CODE": {{"symbol": "...", "name": {{"en": "...", "cs": "...", "de": "..."}}}} }},
              "description_en": "...",
              "description_cs": "...",
              "description_de": "..."
            }}
            """

            try:
                self.log(f"   ⏳ AI Generuje data...", inline=True)
                start_time = time.time()
                
                api_args = {
                    "messages": [{"role": "user", "content": prompt + f"\n\nCONTEXT TO ANALYZE:\n{ctx[:25000]}"}],
                    "model": model_name, 
                    "temperature": 0.0
                }
                
                if "gemma" not in model_name.lower():
                    api_args["response_format"] = {"type": "json_object"}

                resp = client.chat.completions.create(**api_args)
                raw_ai_text = resp.choices[0].message.content
                res = self.extract_json(raw_ai_text)
                
                elapsed = time.time() - start_time
                self.log(f" [Za {elapsed:.1f}s]", inline=False)

                # --- TELEMETRIE AI ODPOVĚDI ---
                self.log(self.style.SUCCESS(f"   🤖 [TELEMETRIE] Syrová odpověď od AI (ukázka):\n   {raw_ai_text[:300].strip()}..."))

                if not res: 
                    raise ValueError("Neplatný JSON od AI")

                # --- 1. ATOMICKÝ UPDATE MODELU COUNTRY (ZEMĚ) ---
                pop_val = res.get('population')
                area_val = res.get('area_km2')
                
                try: pop_val = int(float(pop_val)) if pop_val else None
                except: pop_val = None
                try: area_val = float(area_val) if area_val else None
                except: area_val = None

                update_fields = {}
                if pop_val: update_fields['population'] = pop_val
                if area_val: update_fields['area_km2'] = area_val
                
                sys_gov = res.get('system_of_government_en')
                if sys_gov and c.status == 'sovereign': 
                    update_fields['system_of_government'] = sys_gov
                    
                langs = res.get('official_languages')
                if langs: update_fields['languages'] = langs
                
                currs = res.get('currencies')
                if currs: update_fields['currencies'] = currs

                if update_fields:
                    Country.objects.filter(id=c.id).update(**update_fields)

                # --- 2. ULOŽENÍ TEXTŮ A PŘEKLADŮ DO FLAGCOLLECTION ---
                main_flag.name_cs = (res.get('name_cs') or main_flag.name).strip()
                main_flag.name_de = (res.get('name_de') or main_flag.name).strip()
                
                main_flag.description = {
                    'en': res.get('description_en', ''), 
                    'cs': res.get('description_cs', ''), 
                    'de': res.get('description_de', ''),
                    'capital_cs': res.get('capital_cs', ''),
                    'capital_de': res.get('capital_de', ''),
                    'system_of_government_cs': res.get('system_of_government_cs', ''),
                    'system_of_government_de': res.get('system_of_government_de', ''),
                    'region_cs': res.get('region_cs', ''),
                    'region_de': res.get('region_de', '')
                }
                main_flag.is_verified = True
                main_flag.save()
                
                c.additional_flags.filter(is_verified=False).update(is_verified=True)

                self.log(f"   ✅ Uloženo: Pop={pop_val} | Vláda_CS='{res.get('system_of_government_cs')}' | Reg_CS='{res.get('region_cs')}'", self.style.SUCCESS)
                
                i += 1
                time.sleep(1.5)

            except Exception as e:
                err = str(e).lower()
                if "rate" in err or "limit" in err or "429" in err or "503" in err:
                    self.log("   ⏳ Rate limit... přepínám klíč (20s pauza).", self.style.WARNING)
                    time.sleep(20)
                    k_idx = (k_idx + 1) % len(keys[provider])
                    current_key_indices[provider] = k_idx
                    if k_idx == 0: current_model_idx += 1
                else:
                    self.log(f"   ⚠️ Chyba parsování/API: {err[:200]}", self.style.ERROR)
                    i += 1 

        self.log("\n🎉 Ultimátní databázová korekce dokončena!", self.style.SUCCESS)