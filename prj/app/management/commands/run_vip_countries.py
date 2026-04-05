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
from app.models import FlagCollection, Country

load_dotenv()

class Command(BaseCommand):
    help = 'VIP AI Agent: Exclusively processes Countries and Dependencies with enriched data, smart telemetry, and timeouts.'

    MODELS = [
        {"name": "gemini-3.1-flash-lite-preview", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "chunk_size": 1},
        {"name": "gpt-oss-120b", "provider": "sambanova", "base_url": "https://api.sambanova.ai/v1", "chunk_size": 1},
        {"name": "openai/gpt-oss-120b", "provider": "groq", "base_url": None, "chunk_size": 1},
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Omezí počet vlajek ke zpracování')
        parser.add_argument('--reset', action='store_true', help='Resetuje is_verified a vrátí vlajky do oběhu')

    def log(self, message, style=None, inline=False):
        styled = style(message) if style else message
        if inline:
            self.stdout.write(styled, ending="")
        else:
            self.stdout.write(styled + "\n")
        self.stdout.flush()

    def extract_json(self, text):
        """Ultra-robustní parser: Oprava uvozovek u popisků a backtracking u extra závorek."""
        try:
            text = re.sub(r'```[a-zA-Z]*\n?|\n?```', '', text).strip()
            
            # Oprava chybějících uvozovek u textových polí (Gemini Glitch)
            text = re.sub(r'":\s?([^"{\[\s0-9\-][^,}\]]+)(?=[,}\]])', r'": "\1"', text)
            
            start_match = re.search(r'(\[|\{)', text)
            if not start_match: return None
            start_idx = start_match.start()
            
            for end_idx in range(len(text), start_idx, -1):
                if text[end_idx-1] in ('}', ']'):
                    try:
                        parsed = json.loads(text[start_idx:end_idx])
                        if isinstance(parsed, list):
                            converted = {}
                            for item in parsed:
                                k = str(item.get('qid') or item.get('name'))
                                converted[k] = item
                            return converted
                        return parsed
                    except json.JSONDecodeError:
                        continue
            return None
        except Exception:
            return None

    def fetch_wikipedia_clean(self, title, lang="en"):
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {"action": "query", "format": "json", "titles": title, "prop": "extracts", "explaintext": 1, "redirects": 1}
        headers = {'User-Agent': 'JustEnoughFlagsBot/2.0'}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=5)
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                if page_id != "-1": return page_info.get("extract", "")
        except: pass
        return ""

    def get_wikipedia_title_from_qid(self, qid, lang="en"):
        if not qid: return None
        url = "https://www.wikidata.org/w/api.php"
        params = {"action": "wbgetentities", "format": "json", "ids": qid, "props": "sitelinks", "sitefilter": f"{lang}wiki"}
        try:
            r = requests.get(url, params=params, timeout=4)
            return r.json()["entities"][qid]["sitelinks"][f"{lang}wiki"]["title"]
        except: return None

    def _normalize_iso3(self, value):
        if not isinstance(value, str): return None
        iso3 = value.strip().upper()
        return iso3 if len(iso3) == 3 and iso3.isalpha() else None

    def handle(self, *args, **options):
        keys = {
            "google": [os.getenv(f"GOOGLE_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GOOGLE_API_KEY_{j}")],
            "sambanova": [os.getenv(f"SAMBANOVA_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"SAMBANOVA_API_KEY_{j}")],
            "groq": [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]
        }

        if options['reset']:
            self.log("🧹 [RESET] Vracím vlajky (country & dependency) do oběhu...", self.style.WARNING)
            FlagCollection.objects.filter(category__in=['country', 'dependency']).update(is_verified=False)

        ddgs = DDGS()
        # VIP FILTER: Only countries and dependencies
        flags_qs = FlagCollection.objects.filter(
            category__in=['country', 'dependency'], 
            is_verified=False
        ).order_by('name')
        
        if options['limit'] > 0: 
            flags_qs = flags_qs[:options['limit']]
        
        flags_to_process = list(flags_qs)
        total_count = len(flags_to_process)
        self.log(f"🚀 [VIP START] Zpracovávám {total_count} států a závislých území. (Timeout 45s)", self.style.NOTICE)

        sovereign_iso3 = set(Country.objects.filter(un_member=True).values_list('cca3', flat=True))
        current_key_indices = {"google": 0, "sambanova": 0, "groq": 0}
        current_model_idx = 0
        
        i = 0
        while i < total_count:
            if current_model_idx >= len(self.MODELS):
                self.log("\n💤 [PAUZA] Všechny modely vyčerpány (Rate Limit). Čekám 60 sekund...", self.style.ERROR)
                time.sleep(60)
                current_model_idx = 0 
                continue

            m_cfg = self.MODELS[current_model_idx]
            provider, model_name, chunk_size = m_cfg["provider"], m_cfg["name"], m_cfg["chunk_size"]
            
            if not keys[provider]: 
                current_model_idx += 1
                continue

            k_idx = current_key_indices[provider]
            c_key = keys[provider][k_idx]
            
            # PŘIDÁN TVRDÝ TIMEOUT 45 SEKUND, aby se to nezaseklo na "Aarianian Union" na 2 minuty
            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=45.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=45.0)

            attempts = 0
            max_attempts = 3
            success = False

            while attempts < max_attempts and not success:
                # VIP MODE: Always chunk_size = 1 (one entity at a time)
                chunk = flags_to_process[i:i + 1]
                if not chunk: break

                self.log(f"\n📦 [VIP BATCH {i+1}/{total_count}] | Model: {model_name} | Pokus: {attempts+1}/{max_attempts}")
                data_to_send = []

                for idx, f in enumerate(chunk):
                    real_idx = i + idx + 1
                    self.log(f"   🔍 [{real_idx}] {f.name[:40]:<40}", inline=True)
                    
                    ctx = ""
                    wiki_stats = []
                    
                    # Fetch comprehensive Wikipedia data
                    for lang in ("en", "cs", "de"):
                        title = f.name if lang == "en" else self.get_wikipedia_title_from_qid(f.wikidata_id, lang)
                        if title:
                            txt = self.fetch_wikipedia_clean(title, lang)
                            if txt:
                                wiki_stats.append(f"{lang.upper()}:{len(txt)}")
                                # VIP: More comprehensive context (up to 2500 chars per language)
                                ctx += f"\n--- WIKI {lang.upper()} ({title}) ---\n{txt[:2500]}\n"

                    self.log(f" 📖 Wiki [{' | '.join(wiki_stats) if wiki_stats else 'None'}]", inline=True)

                    missing_pop = (f.population is None)
                    missing_area = (f.area_km2 is None)
                    web_stats = []

                    # Always perform web search for VIP entities
                    hint = f.country.name_common if f.country else ""
                    safe_name = f'"{f.name}"' if not f.name.startswith("'") else f.name
                    queries = []
                    
                    if missing_pop: 
                        queries.append(f"{safe_name} {hint} population site:wikipedia.org".strip())
                    if missing_area: 
                        queries.append(f"{safe_name} {hint} area square kilometers site:wikipedia.org".strip())
                    
                    # Additional enrichment queries
                    queries.append(f"{safe_name} {hint} geography details site:wikipedia.org".strip())
                    queries.append(f"{safe_name} {hint} history political status site:wikipedia.org".strip())

                    self.log("") 
                    for q in queries:
                        try:
                            res_web = ddgs.text(q, max_results=3)  # VIP: More results
                            if res_web:
                                found_text = " ".join([r.get('body', '') for r in res_web])
                                q_type = "pop" if "population" in q else ("area" if "area" in q else "geo" if "geography" in q else "hist")
                                web_stats.append(f"{q_type}:{len(found_text)}")
                                ctx += f"\n--- WEB SEARCH ({q}) ---\n{found_text}\n"
                                
                                clean_snippet = found_text[:150].replace('\n', ' ')
                                self.log(f"      📄 AI vidí ({q_type}): {clean_snippet}...", self.style.HTTP_INFO)
                            time.sleep(1.5)  # RYCHLEJŠÍ: 1.5s místo 3s
                        except: 
                            pass
                        
                    self.log(f"      🌐 Web [{' | '.join(web_stats) if web_stats else 'None'}]")

                    data_to_send.append({
                        "qid": str(f.wikidata_id or ''), 
                        "name": f.name, 
                        "db_pop": f.population, 
                        "db_area": f.area_km2, 
                        "web_data": ctx[:8000],  # VIP: More context
                    })

                # VIP PROMPT: Comprehensive 10-sentence descriptions + Category correction
                prompt = f"""
                Act as an elite Geopolitical Data Architect.
                ENTITY: {flag.name}
                STRICT CATEGORY RULES (CRITICAL):
                - 'country': ONLY 193 UN members + 2 observers.
                - 'dependency': Real, recognized overseas territories (e.g., Greenland, Aruba, Bermuda).
                - 'region': States of a federation, provinces (e.g., Jalisco, Texas, Johor).
                - 'historical': Former states that no longer exist.
                - 'junk': Micronations (like Aarianian Union, Aerican Empire), unrecognized internet projects, fictional states, or political movements. THIS IS CRITICAL.

                - ISO3: Provide the 3-letter ISO code of the parent sovereign country.
                - STATISTICS: Extract EXACT numeric population and area in square kilometers. NEVER round.
                - NAMES: Strictly translate known exonyms to CS and DE.
                - DESCRIPTIONS: Exactly 10 sentences per language (EN, CS, DE). Focus on deep history, geography, and culture. No numbers in text!

                RETURN JSON DICT FORMAT:
                {{ "QID": {{ "new_category": "country|dependency|region|city|historical|junk", "parent_country_iso3": "ISO3", "population": 123, "area_km2": 45.5, "name_cs": "...", "name_de": "...", "description_en": "...", "description_cs": "...", "description_de": "..." }} }}

                DATA: {json.dumps(data_to_send)}
                """

                try:
                    self.log(f"   🤖 [AI] Volám AI pro VIP entitu... ", style=self.style.HTTP_INFO, inline=True)
                    
                    # TELEMETRIE: Začínáme měřit čas odpovědi AI
                    start_time = time.time()
                    
                    resp = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name, 
                        temperature=0.0, 
                        response_format={"type": "json_object"}
                    )
                    
                    # Zastavení stopek
                    elapsed = time.time() - start_time
                    self.log(f"⏱️ Odpověď za {elapsed:.1f}s", inline=False)
                    
                    content = resp.choices[0].message.content
                    ai_results = self.extract_json(content)

                    if not ai_results:
                        raise ValueError(f"Nečitelný JSON od AI.")

                    for flag in chunk:
                        res = ai_results.get(str(flag.wikidata_id or '')) or ai_results.get(flag.name)
                        if not res: 
                            self.log(f"      ⚠️  Žádná data pro {flag.name}", self.style.WARNING)
                            continue

                        # 1. OPRAVA KATEGORIE
                        new_cat = res.get('new_category')
                        if new_cat and new_cat in dict(FlagCollection.CATEGORY_CHOICES):
                            flag.category = new_cat
                            if new_cat not in ['country', 'dependency']:
                                self.log(f"      🔄 Změna kategorie na: {new_cat}", self.style.NOTICE)

                        # 2. OPRAVA SYNCHRONIZACE (Fallback na existující flag.country)
                        ai_iso = self._normalize_iso3(res.get('parent_country_iso3'))
                        bound_country = Country.objects.filter(cca3=ai_iso).first() if ai_iso in sovereign_iso3 else flag.country
                        
                        if bound_country: 
                            flag.country = bound_country
                        
                        # TASK 4: Dual Database Synchronization
                        try:
                            if res.get('population'): 
                                flag.population = int(float(res.get('population')))
                            if res.get('area_km2'): 
                                flag.area_km2 = float(res.get('area_km2'))
                        except: 
                            pass

                        # Sync to Country model if bound AND if it's actually a country
                        if bound_country and flag.category == 'country' and (flag.population or flag.area_km2):
                            country_updated = False
                            if flag.population and flag.population > 0:
                                bound_country.population = flag.population
                                country_updated = True
                            if flag.area_km2 and flag.area_km2 > 0:
                                bound_country.area_km2 = flag.area_km2
                                country_updated = True
                            if country_updated:
                                bound_country.save()
                                self.log(f"      🔄 Country model synchronized: {bound_country.cca3}", self.style.SUCCESS)

                        flag.name_cs = (res.get('name_cs') or flag.name).strip()
                        flag.name_de = (res.get('name_de') or flag.name).strip()
                        flag.description = {
                            'en': res.get('description_en', ''), 
                            'cs': res.get('description_cs', ''), 
                            'de': res.get('description_de', '')
                        }
                        flag.is_verified = True
                        flag.save()
                        
                        pop_str = f"{flag.population:,}" if flag.population else "None"
                        area_str = f"{flag.area_km2:,.2f}" if flag.area_km2 else "None"
                        desc_len_en = len(res.get('description_en', ''))
                        self.log(f"      ✅ {flag.name[:30]:<30} -> Pop: {pop_str}, Kat: {flag.category}, Desc: {desc_len_en} chars")

                    success = True
                    i += len(chunk)
                    time.sleep(2)  # RYCHLEJŠÍ: 2s místo 5s po úspěchu

                except Exception as e:
                    err = str(e).lower()
                    attempts += 1
                    
                    elapsed_fail = time.time() - start_time if 'start_time' in locals() else 0
                    if elapsed_fail > 0:
                        self.log(f" ❌ Selhalo po {elapsed_fail:.1f}s", inline=False)
                    
                    if "429" in err or "rate limit" in err or "timeout" in err or "read operation timed out" in err:
                        self.log(f"   ⏳ [RATE LIMIT / TIMEOUT] Čekám 30s...", self.style.WARNING)
                        time.sleep(30)
                        if k_idx < len(keys[provider]) - 1:
                            k_idx += 1
                            current_key_indices[provider] = k_idx
                            self.log(f"      🔄 Přepínám na další klíč ({k_idx+1}).")
                            c_key = keys[provider][k_idx]
                            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=45.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=45.0)
                            attempts -= 1  # Timeout nebereme jako tvrdou chybu
                    else:
                        self.log(f"   ⚠️ [POKUS {attempts} SELHAL] {err[:150]}", self.style.ERROR)

            if not success:
                self.log(f"   ❌ [CRITICAL] {model_name} selhal 3x po sobě u {flag.name}. Fallback na další model.", self.style.ERROR)
                current_model_idx += 1

        self.log(f"\n🏁 [VIP HOTOVO] Celá fronta VIP entit zpracována.", self.style.SUCCESS)