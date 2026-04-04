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
    help = 'Master AI Agent: Production Ready. Isolated Search, Few-Shot Prompt, Auto-Repair JSON & Snippet Debugging.'

    MODELS = [
        {"name": "gemini-3.1-flash-lite-preview", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "chunk_size": 4},
        {"name": "gpt-oss-120b", "provider": "sambanova", "base_url": "https://api.sambanova.ai/v1", "chunk_size": 3},
        {"name": "openai/gpt-oss-120b", "provider": "groq", "base_url": None, "chunk_size": 3},
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Omezí počet vlajek ke zpracování')
        parser.add_argument('--reset', action='store_true', help='Resetuje is_verified a vrátí JUNK vlajky do oběhu')

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
            self.log("🧹 [RESET] Vracím všechny vlajky do oběhu a mažu 'is_verified' status...", self.style.WARNING)
            FlagCollection.objects.all().update(is_verified=False, is_public=True)

        ddgs = DDGS()
        flags_qs = FlagCollection.objects.filter(is_verified=False).order_by('name')
        if options['limit'] > 0: flags_qs = flags_qs[:options['limit']]
        
        flags_to_process = list(flags_qs)
        total_count = len(flags_to_process)
        self.log(f"🚀 [START] Produkční Agent inicializován pro {total_count} vlajek.", self.style.NOTICE)

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
            provider, model_name, original_chunk_size = m_cfg["provider"], m_cfg["name"], m_cfg["chunk_size"]
            if not keys[provider]: 
                current_model_idx += 1
                continue

            k_idx = current_key_indices[provider]
            c_key = keys[provider][k_idx]
            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key) if m_cfg["base_url"] else Groq(api_key=c_key)

            attempts = 0
            max_attempts = 3
            success = False
            current_chunk_size = original_chunk_size

            while attempts < max_attempts and not success:
                chunk = flags_to_process[i:i + current_chunk_size]
                if not chunk: break

                self.log(f"\n📦 [BATCH {i+1}-{min(i+current_chunk_size, total_count)}/{total_count}] | Model: {model_name} | Pokus: {attempts+1}/{max_attempts}")
                data_to_send = []

                for idx, f in enumerate(chunk):
                    real_idx = i + idx + 1
                    self.log(f"   🔍 [{real_idx}] {f.name[:30]:<30}", inline=True)
                    
                    ctx = ""
                    wiki_stats = []
                    
                    for lang in ("en", "cs", "de"):
                        title = f.name if lang == "en" else self.get_wikipedia_title_from_qid(f.wikidata_id, lang)
                        if title:
                            txt = self.fetch_wikipedia_clean(title, lang)
                            if txt:
                                wiki_stats.append(f"{lang.upper()}:{len(txt)}")
                                ctx += f"\n--- WIKI {lang.upper()} ({title}) ---\n{txt[:1200]}\n"

                    self.log(f" 📖 Wiki [{' | '.join(wiki_stats) if wiki_stats else 'None'}]", inline=True)

                    missing_pop = (f.population is None)
                    missing_area = (f.area_km2 is None)
                    low_data = len(ctx) < 600
                    web_stats = []

                    if missing_pop or missing_area or low_data:
                        hint = f.country.name_common if f.country else ""
                        safe_name = f'"{f.name}"' if not f.name.startswith("'") else f.name
                        queries = []
                        
                        if missing_pop: queries.append(f"{safe_name} {hint} population site:wikipedia.org".strip())
                        if missing_area: queries.append(f"{safe_name} {hint} area square kilometers site:wikipedia.org".strip())
                        if not missing_pop and not missing_area: queries.append(f"{safe_name} {hint} geography details site:wikipedia.org".strip())

                        self.log("") # Odřádkování pro čistý výpis snippetů
                        for q in queries:
                            try:
                                res_web = ddgs.text(q, max_results=2)
                                if res_web:
                                    found_text = " ".join([r.get('body', '') for r in res_web])
                                    q_type = "pop" if "population" in q else ("area" if "area" in q else "details")
                                    web_stats.append(f"{q_type}:{len(found_text)}")
                                    ctx += f"\n--- WEB SEARCH ({q}) ---\n{found_text}\n"
                                    
                                    # PŘIDANÝ DEBUGGING SNIPPETU
                                    clean_snippet = found_text[:200].replace('\n', ' ')
                                    self.log(f"      📄 AI vidí ({q_type}): {clean_snippet}...", self.style.HTTP_INFO)
                            except: pass
                            time.sleep(1)
                        self.log("      ", inline=True) # Zarovnání pro další výpisy

                    self.log(f"🌐 Web [{' | '.join(web_stats) if web_stats else 'None'}]")

                    data_to_send.append({
                        "qid": str(f.wikidata_id or ''), "name": f.name, 
                        "db_pop": f.population, "db_area": f.area_km2, "web_data": ctx[:4500],
                    })

                prompt = f"""
                Act as an elite Geopolitical Data Architect. Process {len(data_to_send)} entities.
                
                STRICT JUNK FILTER (CRITICAL):
                Distinguish between a physical TERRITORY and a MOVEMENT/REGIME/IDEOLOGY.
                - VALID: Nations, Cities, Towns, Villages, Settlements, Provinces, Historical States, Territories.
                - JUNK: Political parties, revolutionary movements, specific dictatorial periods/regimes, sports teams.
                
                FEW-SHOT EXAMPLES:
                1. Input: "26th of July Movement" -> Output: "new_category": "junk"
                2. Input: "4th of August Regime" -> Output: "new_category": "junk"
                3. Input: "Abinsky urban settlement" -> Output: "new_category": "city"
                4. Input: "Aachen" -> Output: "new_category": "city", "name_cs": "Cáchy"
                5. Input: "Abbasid Caliphate" -> Output: "new_category": "historical"
                
                DATA EXTRACTION RULES:
                - STATISTICS: Extract EXACT numbers from web_data. NEVER round! If missing, use null.
                - NAMES: Translate known exonyms strictly.
                - DESCRIPTIONS: Exactly 3 sentences per language (EN, CS, DE) focusing on history/geography. Max 250 chars/lang.
                - FORBIDDEN: Do NOT mention numeric statistics (population/area) in the description text.
                
                RETURN ONLY A VALID JSON DICTIONARY mapping QID (or name) to results:
                {{ "QID": {{ "new_category": "state|city|region|territory|historical|international|junk", "parent_country_iso3": "ISO3", "population": 123, "area_km2": 45.5, "name_cs": "...", "name_de": "...", "description_en": "...", "description_cs": "...", "description_de": "..." }} }}
                """

                try:
                    self.log(f"   🤖 [AI] Volám AI...", style=self.style.HTTP_INFO)
                    resp = client.chat.completions.create(
                        messages=[{"role": "user", "content": f"{prompt}\n\nDATA: {json.dumps(data_to_send)}"}],
                        model=model_name, temperature=0.0, response_format={"type": "json_object"}
                    )
                    
                    content = resp.choices[0].message.content
                    ai_results = self.extract_json(content)

                    if not ai_results:
                        raise ValueError(f"Nečitelný JSON od AI.")

                    for flag in chunk:
                        res = ai_results.get(str(flag.wikidata_id or '')) or ai_results.get(flag.name)
                        if not res: continue

                        if str(res.get('new_category')).lower() == 'junk':
                            flag.is_public = False; flag.is_verified = True; flag.save()
                            self.log(f"      🗑️  {flag.name[:25]:<25} -> JUNK (skryto)", self.style.WARNING)
                            continue

                        cat = res.get('new_category')
                        if cat not in dict(FlagCollection.CATEGORY_CHOICES): cat = flag.category
                        
                        ai_iso = self._normalize_iso3(res.get('parent_country_iso3'))
                        bound_country = Country.objects.filter(cca3=ai_iso).first() if ai_iso in sovereign_iso3 else None
                        
                        flag.category = cat
                        if bound_country: flag.country = bound_country
                        
                        try:
                            if res.get('population'): flag.population = int(float(res.get('population')))
                            if res.get('area_km2'): flag.area_km2 = float(res.get('area_km2'))
                        except: pass

                        flag.name_cs = (res.get('name_cs') or flag.name).strip()
                        flag.name_de = (res.get('name_de') or flag.name).strip()
                        flag.description = {'en': res.get('description_en',''), 'cs': res.get('description_cs',''), 'de': res.get('description_de','')}
                        flag.is_verified = True
                        flag.save()
                        
                        pop_str = f"{flag.population}" if flag.population else "None"
                        area_str = f"{flag.area_km2}" if flag.area_km2 else "None"
                        self.log(f"      ✅ {flag.name[:25]:<25} -> {flag.name_cs[:15]} (Pop: {pop_str}, Area: {area_str})")

                    success = True
                    i += len(chunk)
                    time.sleep(1)

                except Exception as e:
                    err = str(e).lower()
                    attempts += 1
                    
                    if "429" in err or "rate limit" in err:
                        self.log(f"   ⏳ [RATE LIMIT] Limit. Čekám 15s...", self.style.WARNING)
                        time.sleep(15)
                        if k_idx < len(keys[provider]) - 1:
                            k_idx += 1
                            current_key_indices[provider] = k_idx
                            self.log("      🔄 Přepínám na další klíč.")
                            attempts -= 1 
                    else:
                        self.log(f"   ⚠️ [POKUS {attempts} SELHAL] {err[:150]}", self.style.ERROR)
                        if attempts < max_attempts:
                            current_chunk_size = max(1, current_chunk_size - 1)
                            self.log(f"      🔄 Snižuji dávku na {current_chunk_size} a zkouším znovu...", self.style.NOTICE)

            if not success:
                self.log(f"   ❌ [CRITICAL] {model_name} selhal 3x po sobě. Fallback na další model.", self.style.ERROR)
                current_model_idx += 1

        self.log(f"\n🏁 [HOTOVO] Celá fronta zpracována.", self.style.SUCCESS)