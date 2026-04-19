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
    help = '🚀 VIP AI Agent: Komplexní databázová korekce s hlubokou telemetrií a 100% lokalizací.'

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
            status__in=['sovereign', 'territory']
        ).order_by('name_common')

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
            
            self.log(f"\n" + "="*80)
            self.log(f"💎 [{i+1}/{total_count}] | 🤖 {model_name} | 🌍 {c.name_common} ({c.status})")
            
            # --- ZÍSKÁVÁNÍ DAT (VYLEPŠENÉ VYHLEDÁVÁNÍ) ---
            ctx = ""
            
            local_names = {"en": c.name_common, "cs": c.name_cs or c.name_common, "de": c.name_de or c.name_common}
            
            if not local_names["cs"] or local_names["cs"] == c.name_common:
                try:
                    res_cs = ddgs.text(f'"{c.name_common}" země česky', max_results=1)
                    if res_cs: local_names["cs"] = res_cs[0]['title'].split()[0]
                except: pass
                
            if not local_names["de"] or local_names["de"] == c.name_common:
                try:
                    res_de = ddgs.text(f'"{c.name_common}" Land auf Deutsch', max_results=1)
                    if res_de: local_names["de"] = res_de[0]['title'].split()[0]
                except: pass

            for lang in ("en", "cs", "de"):
                search_term = local_names[lang]
                txt = self.fetch_wikipedia_clean(search_term, lang)
                if not txt and lang != "en": 
                    txt = self.fetch_wikipedia_clean(c.name_common, lang)
                if txt: 
                    ctx += f"\n--- WIKI {lang.upper()} ---\n{txt[:4000]}\n"

            try:
                res_pop = ddgs.text(f'"{c.name_common}" current exact population estimate demographic', max_results=3)
                if res_pop: ctx += f"\n--- WEB POPULATION ---\n{' '.join([r['body'] for r in res_pop])}\n"
            except: pass

            self.log(self.style.WARNING(f"   📡 [TELEMETRIE] Staženo znaků pro AI: {len(ctx)}"))

            region_name = c.region.name if c.region else "Unknown"
            subregion_name = c.subregion or "Unknown"
            capital_name = c.capital or "Unknown"

            # --- PROMPT S FEW-SHOT PŘÍKLADEM ---
            prompt = f"""
            You are an elite Geopolitical Data Translator. Provide PERFECTLY structured JSON for: {c.name_common} (Status: {c.status}).
            
            CRITICAL TRANSLATION RULES:
            1. FULL LOCALIZATION: You MUST translate the Country Name, Capital, Region, Subregion, and System of Government into BOTH Czech (cs) and German (de). Do not leave them in English!
            2. EXACT NUMBERS: Find the absolute most exact and precise numeric population and area_km2 from the context or your knowledge. NO ROUNDED NUMBERS.
            3. DESCRIPTIONS: Write EXACTLY 5 high-quality sentences per language (EN, CS, DE). Focus on history, geography, and economy.
            4. LANGUAGES & CURRENCIES: Translate names strictly to EN, CS, DE.
            5. STRICT JSON OUTPUT ONLY.

            DATA TO TRANSLATE/FIX:
            Region: {region_name}
            Subregion: {subregion_name}
            Capital: {capital_name}
            System of Gov: {c.system_of_government or 'Find and translate'}
            Currencies: {c.currencies}
            Languages: {c.languages}

            --- FEW-SHOT EXAMPLE OF PERFECT OUTPUT FOR "Germany" ---
            {{
              "name_en": "Germany",
              "name_cs": "Německo",
              "name_de": "Deutschland",
              "population": 84432670,
              "area_km2": 357022.0,
              "system_of_government_en": "Federal Parliamentary Republic",
              "system_of_government_cs": "Federativní parlamentní republika",
              "system_of_government_de": "Föderale parlamentarische Republik",
              "region_en": "Europe",
              "region_cs": "Evropa",
              "region_de": "Europa",
              "subregion_en": "Western Europe",
              "subregion_cs": "Západní Evropa",
              "subregion_de": "Westeuropa",
              "capital_en": "Berlin",
              "capital_cs": "Berlín",
              "capital_de": "Berlin",
              "official_languages": {{ "de": {{"en": "German", "cs": "Němčina", "de": "Deutsch"}} }},
              "currencies": {{ "EUR": {{"symbol": "€", "name": {{"en": "Euro", "cs": "Euro", "de": "Euro"}}}} }},
              "description_en": "Germany is a country in Central Europe. It has a rich history marked by the Holy Roman Empire, the Reformation, and modern unification. Following World War II, it was divided but reunited in 1990. Today, it is a global economic powerhouse and a leading member of the European Union. Its landscape varies from the Alps in the south to the North Sea coast.",
              "description_cs": "Německo je stát ve střední Evropě. Má bohatou historii poznamenanou Svatou říší římskou, reformací a moderním sjednocením. Po druhé světové válce bylo rozděleno, ale v roce 1990 se znovu sjednotilo. Dnes je globální ekonomickou velmocí a předním členem Evropské unie. Jeho krajina se rozkládá od Alp na jihu až po pobřeží Severního moře.",
              "description_de": "Deutschland ist ein Staat in Mitteleuropa. Es hat eine reiche Geschichte, die vom Heiligen Römischen Reich, der Reformation und der modernen Einigung geprägt ist. Nach dem Zweiten Weltkrieg wurde es geteilt, aber 1990 wiedervereinigt. Heute ist es eine globale Wirtschaftsmacht und ein führendes Mitglied der Europäischen Union. Seine Landschaft reicht von den Alpen im Süden bis zur Nordseeküste."
            }}
            EXAMPLE 2: Dependent Territory (Åland Islands)
            {{
              "name_en": "Åland Islands", "name_cs": "Ålandy", "name_de": "Åland-Inseln",
              "population": 30359, "area_km2": 1580.0,
              "system_of_government_en": null, "system_of_government_cs": null, "system_of_government_de": null,
              "region_en": "Europe", "region_cs": "Evropa", "region_de": "Europa",
              "subregion_en": "Northern Europe", "subregion_cs": "Severní Evropa", "subregion_de": "Nordeuropa",
              "capital_en": "Mariehamn", "capital_cs": "Mariehamn", "capital_de": "Mariehamn",
              "official_languages": {{ "sv": {{"en": "Swedish", "cs": "Švédština", "de": "Schwedisch"}} }},
              "currencies": {{ "EUR": {{"symbol": "€", "name": {{"en": "Euro", "cs": "Euro", "de": "Euro"}}}} }},
              "description_en": "The Åland Islands are an autonomous, demilitarized, and Swedish-speaking region of Finland located in the Baltic Sea. They consist of a large main island and thousands of smaller skerries and islands. Their unique status was confirmed by the League of Nations in 1921, ensuring the preservation of the Swedish language and local culture. Shipping and tourism are the backbones of the local economy, with frequent ferry connections to Stockholm and Turku. The islands are famous for their maritime history and beautiful, rugged archipelago landscapes.",
              "description_cs": "Ålandy jsou autonomní, demilitarizovaná a švédsky mluvící oblast Finska nacházející se v Baltském moři. Skládají se z velkého hlavního ostrova a tisíců menších ostrůvků a útesů. Jejich jedinečný status potvrdila Společnost národů v roce 1921, čímž zajistila zachování švédského jazyka a místní kultury. Námořní doprava a cestovní ruch jsou pilíři místní ekonomiky s častým trajektovým spojením do Stockholmu a Turku. Ostrovy jsou známé svou námořní historií a krásnou, drsnou krajinou souostroví.",
              "description_de": "Die Åland-Inseln sind eine autonome, demilitarisierte und schwedischsprachige Region Finnlands, die in der Ostsee liegt. Sie bestehen aus einer großen Hauptinsel und Tausenden von kleineren Schären und Inseln. Ihr besonderer Status wurde 1921 vom Völkerbund bestätigt, um die Erhaltung der schwedischen Sprache und Kultur zu gewährleisten. Schifffahrt und Tourismus sind die Stützen der lokalen Wirtschaft mit regelmäßigen Fährverbindungen nach Stockholm und Turku. Die Inseln sind bekannt für ihre maritime Geschichte und die wunderschöne, zerklüftete Schärenlandschaft."
            }}
            --- END OF EXAMPLE ---

            Now, generate the JSON for: {c.name_common}
            """

            try:
                self.log(f"   ⏳ AI Generuje a překládá data...", inline=True)
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

                self.log(self.style.SUCCESS(f"   🤖 [TELEMETRIE] Syrová odpověď od AI (ukázka):\n   {raw_ai_text[:300].strip()}..."))

                if not res: 
                    raise ValueError("Neplatný JSON od AI")

                # --- 1. ATOMICKÝ UPDATE MODELU COUNTRY ---
                pop_val = res.get('population')
                area_val = res.get('area_km2')
                
                try: pop_val = int(float(pop_val)) if pop_val else None
                except: pop_val = None
                try: area_val = float(area_val) if area_val else None
                except: area_val = None

                if pop_val: c.population = pop_val
                if area_val: c.area_km2 = area_val
                
                sys_gov = res.get('system_of_government_en')
                if sys_gov and c.status == 'sovereign': 
                    c.system_of_government = sys_gov
                    
                langs = res.get('official_languages')
                if langs: c.languages = langs
                
                currs = res.get('currencies')
                if currs: c.currencies = currs

                # ---> ULOŽENÍ LOKALIZACÍ <---
                c.name_cs = (res.get('name_cs') or c.name_common).strip()
                c.name_de = (res.get('name_de') or c.name_common).strip()
                c.description = res.get('description_en', '').strip()
                c.description_cs = res.get('description_cs', '').strip()
                c.description_de = res.get('description_de', '').strip()

                if hasattr(c, 'capital_cs'): c.capital_cs = res.get('capital_cs', '')
                if hasattr(c, 'capital_de'): c.capital_de = res.get('capital_de', '')
                if hasattr(c, 'region_cs'): c.region_cs = res.get('region_cs', '')
                if hasattr(c, 'region_de'): c.region_de = res.get('region_de', '')
                if hasattr(c, 'subregion_cs'): c.subregion_cs = res.get('subregion_cs', '')
                if hasattr(c, 'subregion_de'): c.subregion_de = res.get('subregion_de', '')
                if hasattr(c, 'system_of_government_cs'): c.system_of_government_cs = res.get('system_of_government_cs', '')
                if hasattr(c, 'system_of_government_de'): c.system_of_government_de = res.get('system_of_government_de', '')

                c.save()

                # --- 2. VERIFIKACE VLAJEK ---
                c.additional_flags.filter(is_verified=False).update(is_verified=True)

                self.log(f"   ✅ Uloženo: Pop={pop_val} | Reg_CS='{res.get('region_cs')}' | Vláda_DE='{res.get('system_of_government_de')}'", self.style.SUCCESS)
                
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