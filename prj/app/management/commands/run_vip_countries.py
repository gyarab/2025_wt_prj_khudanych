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
    help = '🚀 VIP AI Agent: Country-centric iteration pro maximální úsporu tokenů a prevenci duplicit.'

    MODELS = [
        {"name": "gemma-3-27b-it", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
        {"name": "gemini-3.1-flash-lite-preview", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"},
        {"name": "gpt-oss-120b", "provider": "sambanova", "base_url": "https://api.sambanova.ai/v1"},
        {"name": "openai/gpt-oss-120b", "provider": "groq", "base_url": None},
    ]

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Limit zpracovaných zemí')
        parser.add_argument('--reset', action='store_true', help='Reset is_verified vlajek')

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
        params = {"action": "query", "format": "json", "titles": title, "prop": "extracts", "explaintext": 1, "redirects": 1}
        try:
            r = requests.get(url, params=params, timeout=5)
            pages = r.json().get("query", {}).get("pages", {})
            for p_id, p_info in pages.items():
                if p_id != "-1": return p_info.get("extract", "")
        except: pass
        return ""

    def handle(self, *args, **options):
        # Načtení klíčů
        keys = {
            "google": [os.getenv(f"GOOGLE_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GOOGLE_API_KEY_{j}")],
            "sambanova": [os.getenv(f"SAMBANOVA_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"SAMBANOVA_API_KEY_{j}")],
            "groq": [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]
        }

        if options['reset']:
            self.log("🧹 [RESET] Vracím vlajky do oběhu (is_verified=False)...", self.style.WARNING)
            FlagCollection.objects.filter(category__in=['country', 'dependency']).update(is_verified=False)

        ddgs = DDGS()

        # 🧠 PARADIGM SHIFT: Hledáme v tabulce Country, ne ve vlajkách!
        # Vezmeme pouze ty země, které mají napojenou alespoň jednu vlajku, co ještě není ověřená
        countries_qs = Country.objects.filter(
            additional_flags__isnull=False,
            additional_flags__is_verified=False,
            additional_flags__category__in=['country', 'dependency']
        ).distinct().order_by('name_common')

        if options['limit'] > 0: 
            countries_qs = countries_qs[:options['limit']]

        countries_list = list(countries_qs)
        total_count = len(countries_list)
        
        self.log(f"🚀 [VIP START] Zpracovávám {total_count} unikátních států a závislých území.", self.style.NOTICE)

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
            
            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=45.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=45.0)

            c = countries_list[i]
            
            # Najdeme tu "hlavní" vlajku, do které pak uložíme texty (preferujeme is_public=True)
            main_flag = c.additional_flags.filter(is_public=True, category__in=['country', 'dependency']).first()
            if not main_flag:
                main_flag = c.additional_flags.filter(category__in=['country', 'dependency']).first()
                
            if not main_flag:
                self.log(f"   ⚠️ Přeskakuji {c.name_common}, nenašel jsem u ní vhodnou vlajku.")
                i += 1
                continue

            self.log(f"\n💎 [{i+1}/{total_count}] | 🤖 AI: {model_name} | 🌍 Stát: {c.name_common}")
            
            # --- ZÍSKÁVÁNÍ DAT ---
            ctx = ""
            wiki_stats = []
            for lang in ("en", "cs"):
                txt = self.fetch_wikipedia_clean(c.name_common, lang)
                if txt: 
                    wiki_stats.append(f"{lang.upper()}:{len(txt)}")
                    ctx += f"\n--- WIKI {lang.upper()} ---\n{txt[:2500]}\n"

            self.log(f"   📖 Wiki: [{' | '.join(wiki_stats) if wiki_stats else 'Žádné'}]")

            web_stats = []
            try:
                res = ddgs.text(f'"{c.name_common}" population area history geography', max_results=2)
                if res: 
                    found_text = " ".join([r['body'] for r in res])
                    web_stats.append(f"DDGS:{len(found_text)}")
                    ctx += f"\n--- WEB ---\n{found_text}\n"
            except: pass
            
            if web_stats:
                self.log(f"   🌐 Web search: [{' | '.join(web_stats)}]")

            # --- AI PROMPT (FEW-SHOT) ---
            prompt = f"""
            Act as an elite Geopolitical Historian. Provide structured data for: {c.name_common}.
            
            RULES:
            1. Extract exact numeric population and area_km2. Use null if unknown.
            2. Write EXACTLY 5 sentences per language (EN, CS, DE). Focus on deep history and culture. NO population/area numbers in the text!
            3. Translate names perfectly to Czech and German.
            4. STRICT JSON OUTPUT ONLY. Do NOT wrap in markdown unless it's a JSON block.

            EXAMPLE OUTPUT FORMAT:
            {{
              "name_cs": "Bavorské království",
              "name_de": "Königreich Bayern",
              "population": 1234567,
              "area_km2": 456.78,
              "description_en": "Sentence 1. Sentence 2. Sentence 3. Sentence 4. Sentence 5.",
              "description_cs": "Věta 1. Věta 2. Věta 3. Věta 4. Věta 5.",
              "description_de": "Satz 1. Satz 2. Satz 3. Satz 4. Satz 5."
            }}
            """

            try:
                self.log(f"   ⏳ Generuji (5 vět, pop/area)...", inline=True)
                start_time = time.time()
                
                api_args = {
                    "messages": [{"role": "user", "content": prompt + f"\n\nDATA TO ANALYZE:\n{ctx[:4500]}"}],
                    "model": model_name, 
                    "temperature": 0.0
                }
                
                # Gemini podporuje JSON mód, open-source modely (Gemma, Sambanova) potřebují few-shot
                if "gemma" not in model_name.lower():
                    api_args["response_format"] = {"type": "json_object"}

                resp = client.chat.completions.create(**api_args)
                res = self.extract_json(resp.choices[0].message.content)
                
                elapsed = time.time() - start_time
                self.log(f" [Odpověď za {elapsed:.1f}s]", inline=False)

                if not res: 
                    raise ValueError("Invalid JSON from AI")

                # --- 1. ATOMICKÝ UPDATE MODELU COUNTRY (ZEMĚ) ---
                pop_val = res.get('population')
                area_val = res.get('area_km2')
                
                try: pop_val = int(float(pop_val)) if pop_val else None
                except: pop_val = None
                
                try: area_val = float(area_val) if area_val else None
                except: area_val = None

                update_fields = {}
                if pop_val: update_fields['population'] = pop_val
                if area_val: 
                    update_fields['area_km2'] = area_val
                    if hasattr(Country, 'area'): update_fields['area'] = area_val

                if update_fields:
                    # Toto přepíše data SQL příkazem přímo v databázi (nejbezpečnější metoda)
                    Country.objects.filter(id=c.id).update(**update_fields)
                    self.log(f"   ⚡ Data atomicky uložena do tabulky Country: {update_fields}", self.style.SUCCESS)

                # --- 2. ULOŽENÍ TEXTŮ DO MODELU FLAGCOLLECTION (VLAJKY) ---
                main_flag.name_cs = (res.get('name_cs') or main_flag.name).strip()
                main_flag.name_de = (res.get('name_de') or main_flag.name).strip()
                main_flag.description = {
                    'en': res.get('description_en', ''), 
                    'cs': res.get('description_cs', ''), 
                    'de': res.get('description_de', '')
                }
                main_flag.is_verified = True
                main_flag.save()
                
                # Pokud k této zemi patří i další historické vlajky, odškrtneme je, aby je skript už nebral jako nedodělané
                c.additional_flags.filter(is_verified=False).update(is_verified=True)

                self.log(f"   ✅ Uloženo: CS={main_flag.name_cs[:20]}... | Pop: {pop_val} | Area: {area_val}")
                
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
                    self.log(f"   ⚠️ Chyba parsování/API: {err[:150]}", self.style.ERROR)
                    i += 1 

        self.log("\n🎉 Celá fronta států úspěšně obsloužena!", self.style.SUCCESS)
