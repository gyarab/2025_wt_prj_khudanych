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
    help = 'Master AI Agent: Expanded Context, Perfect Czech Grammar, Auto-Retries, ID matching & Token Fallback.'

    MODELS = [
        {"name": "gemma-3-27b-it", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "chunk_size": 1},
        {"name": "gemma-4-31b-it", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "chunk_size": 1},
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
        # NOVÝ ARGUMENT: Spustí skript od konce abecedy
        parser.add_argument('--reverse', action='store_true', help='Pojede vlajky od konce (Z do A)')

    def log(self, message, style=None, inline=False):
        styled = style(message) if style else message
        if inline:
            self.stdout.write(styled, ending="")
        else:
            self.stdout.write(styled + "\n")
        self.stdout.flush()

    def extract_json(self, text):
        """Jednodušší a robustnější parser, který neničí Listy."""
        try:
            text = re.sub(r'```[a-zA-Z]*\n?|\n?```', '', text).strip()
            text = re.sub(r'":\s?([^"{\[\s0-9\-][^,}\]]+)(?=[,}\]])', r'": "\1"', text)
            start_match = re.search(r'(\[|\{)', text)
            if not start_match: return None
            for end_idx in range(len(text), start_match.start(), -1):
                if text[end_idx-1] in ('}', ']'):
                    try:
                        return json.loads(text[start_match.start():end_idx])
                    except: continue
            return None
        except: return None

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
        # 1. Nejdříve načteme Google klíče samostatně
        google_keys = [os.getenv(f"GOOGLE_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GOOGLE_API_KEY_{j}")]
        
        # 2. Logika pro paralelní běh (prohození klíčů)
        if options['reverse'] and len(google_keys) >= 2:
            # Prohodíme první a druhý klíč. Reverse skript začne s klíčem č. 2.
            google_keys[0], google_keys[1] = google_keys[1], google_keys[0]
            self.log("🔀 [KEY SWAP] Reverzní mód aktivní: Skript začíná s GOOGLE_API_KEY_2.", self.style.WARNING)

        # 3. Složení finálního slovníku klíčů
        keys = {
            "google": google_keys,
            "sambanova": [os.getenv(f"SAMBANOVA_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"SAMBANOVA_API_KEY_{j}")],
            "groq": [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]
        }

        if options['reset']:
            self.log("🧹 [RESET] Vracím všechny vlajky do oběhu a mažu 'is_verified' status...", self.style.WARNING)
            FlagCollection.objects.all().update(is_verified=False, is_public=True)

        ddgs = DDGS()
        
        # LOGIKA PRO REVERZNÍ BĚH (Klešťový obchvat)
        if options['reverse']:
            flags_qs = FlagCollection.objects.filter(is_verified=False).order_by('-name')
            self.log("◀️ [REVERZNÍ MÓD] Jedu od Z do A...", self.style.WARNING)
        else:
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
            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=45.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=45.0)

            attempts = 0
            max_attempts = max(3, len(keys[provider]) + 1)
            success = False
            current_chunk_size = original_chunk_size
            
            # Nastavíme výchozí limit kontextu pro tuto dávku
            current_context_limit = 7500

            while attempts < max_attempts and not success:
                chunk = flags_to_process[i:i + current_chunk_size]
                if not chunk: break

                self.log(f"\n📦 [BATCH {i+1}-{min(i+len(chunk), total_count)}/{total_count}] | Model: {model_name} | Pokus: {attempts+1}/{max_attempts}")
                data_to_send = []
                flags_for_ai = [] 

                for idx, f in enumerate(chunk):
                    real_idx = i + idx + 1
                    
                    # RYCHLÁ KONTROLA DATABÁZE (Ochrana proti duplicitě při setkání agentů)
                    f.refresh_from_db()
                    desc_cs = f.description.get('cs', '') if isinstance(f.description, dict) else ''
                    if (len(desc_cs) > 20 and f.population and f.area_km2) or f.is_verified:
                        f.is_verified = True
                        f.save()
                        self.log(f"   ⏭️ [{real_idx}] {f.name[:30]:<30} (Již zpracováno kolegou)", self.style.SUCCESS)
                        continue
                    
                    self.log(f"   🔍 [{real_idx}] {f.name[:30]:<30}", inline=True)
                    flags_for_ai.append((real_idx, f))
                    
                    ctx = ""
                    wiki_stats = []
                    
                    for lang in ("en", "cs", "de"):
                        title = f.name if lang == "en" else self.get_wikipedia_title_from_qid(f.wikidata_id, lang)
                        if title:
                            txt = self.fetch_wikipedia_clean(title, lang)
                            if txt:
                                wiki_stats.append(f"{lang.upper()}:{len(txt)}")
                                ctx += f"\n--- WIKI {lang.upper()} ({title}) ---\n{txt[:2500]}\n"

                    self.log(f" 📖 Wiki [{' | '.join(wiki_stats) if wiki_stats else 'None'}]", inline=True)

                    missing_pop = (f.population is None)
                    missing_area = (f.area_km2 is None)
                    low_data = len(ctx) < 1500 
                    web_stats = []

                    if missing_pop or missing_area or low_data:
                        hint = f.country.name_common if f.country else ""
                        safe_name = f'"{f.name}"' if not f.name.startswith("'") else f.name
                        queries = []
                        
                        if missing_pop: queries.append(f"{safe_name} {hint} population site:wikipedia.org".strip())
                        if missing_area: queries.append(f"{safe_name} {hint} area square kilometers site:wikipedia.org".strip())
                        if not missing_pop and not missing_area: queries.append(f"{safe_name} {hint} geography details site:wikipedia.org".strip())

                        self.log("") 
                        for q in queries:
                            try:
                                res_web = ddgs.text(q, max_results=3)
                                if res_web:
                                    found_text = " ".join([r.get('body', '') for r in res_web])
                                    q_type = "pop" if "population" in q else ("area" if "area" in q else "details")
                                    web_stats.append(f"{q_type}:{len(found_text)}")
                                    ctx += f"\n--- WEB SEARCH ({q}) ---\n{found_text}\n"
                                    
                                    clean_snippet = found_text[:200].replace('\n', ' ')
                                    self.log(f"      📄 AI vidí ({q_type}): {clean_snippet}...", self.style.HTTP_INFO)
                            except: pass
                            time.sleep(1)
                        self.log("      ", inline=True) 

                    self.log(f"🌐 Web [{' | '.join(web_stats) if web_stats else 'None'}]")

                    data_to_send.append({
                        "internal_id": str(real_idx), 
                        "name": f.name, 
                        "db_pop": f.population, 
                        "db_area": f.area_km2, 
                        # Použije se dynamický limit kontextu (při Token chybě se zmenší)
                        "web_data": ctx[:current_context_limit],
                    })

                if not data_to_send:
                    success = True
                    i += len(chunk)
                    continue

                prompt = f"""
            PHASE 1: FAST BULK SORTER - Geopolitical categorization for {len(data_to_send)} entities.
            Your PRIMARY MISSION is PERFECT categorization. Be BRUTALLY strict.
            
            CATEGORY RULES:
            1. "country": 193 UN members + 2 observers ONLY.
            2. "dependency": Real non-sovereign territories (Greenland, Bermuda).
            3. "region": States of federation, provinces, districts (Texas, Bavaria).
            4. "city": Cities, towns, municipalities.
            5. "historical": Former states (Soviet Union).
            6. "international": UN, EU, NATO.
            7. "junk": Micronations (Aarianian Union), internet projects, parties, movements, individuals.
            
            DATA EXTRACTION:
            - Extract exact numbers for population/area from the web_data. NEVER round. Use null if missing.
            - NAMES (CS/DE): You MUST prioritize the titles found in WIKI CS (for name_cs) and WIKI DE (for name_de). 
            - If WIKI CS title is "Království Algarves", use exactly that. 
            - If no Czech Wikipedia title is available, follow the adjective rule: "Württemberské království" (preferred) over "Království Württembersko".
            - DESCRIPTIONS: Write exactly 3 highly informative sentences per language (EN, CS, DE). Avoid generic filler phrases. Use specific historical facts, locations, capitals, and ruling dynasties found in the text. Max 300 chars per language. Do NOT mention population or area statistics in the text.
            
            OUTPUT FORMAT (JSON LIST OF OBJECTS - STRICTLY USE THIS FORMAT):
            [
              {{ 
                "internal_id": "MUST MATCH EXACTLY THE internal_id FROM DATA", 
                "new_category": "country|dependency|city|region|historical|international|junk", 
                "parent_country_iso3": "ABC", 
                "population": 12345, 
                "area_km2": 67.89, 
                "name_cs": "...", 
                "name_de": "...", 
                "description_en": "...", 
                "description_cs": "...", 
                "description_de": "..." 
              }}
            ]
            """

                try:
                    self.log(f"   🤖 [AI] Volám AI...", style=self.style.HTTP_INFO)
                    
                    api_args = {
                        "messages": [{"role": "user", "content": f"{prompt}\n\nDATA: {json.dumps(data_to_send)}"}],
                        "model": model_name,
                        "temperature": 0.0,
                    }

                    if "gemma" not in model_name.lower():
                        api_args["response_format"] = {"type": "json_object"}

                    resp = client.chat.completions.create(**api_args)
                    
                    content = resp.choices[0].message.content
                    ai_results = self.extract_json(content)

                    if not ai_results:
                        raise ValueError("AI nevrátila validní JSON.")

                    ai_list = []
                    if isinstance(ai_results, dict):
                        for val in ai_results.values():
                            if isinstance(val, list): ai_list.extend(val)
                            elif isinstance(val, dict): ai_list.append(val)
                        if not ai_list: ai_list = list(ai_results.values())
                    elif isinstance(ai_results, list):
                        ai_list = ai_results

                    res_by_id = {str(item.get("internal_id")): item for item in ai_list if isinstance(item, dict) and item.get("internal_id")}

                    missing_ids = []
                    for real_idx, flag in flags_for_ai:
                        if str(real_idx) not in res_by_id:
                            missing_ids.append(flag.name)
                    
                    if missing_ids:
                        raise ValueError(f"AI ztratila ID pro tyto položky: {', '.join(missing_ids)}")

                    for real_idx, flag in flags_for_ai:
                        res = res_by_id[str(real_idx)]

                        if str(res.get('new_category')).lower() == 'junk':
                            flag.category = 'junk' if 'junk' in dict(FlagCollection.CATEGORY_CHOICES) else flag.category
                            flag.is_public = False
                            flag.is_verified = True
                            flag.save()
                            self.log(f"      🗑️  {flag.name[:25]:<25} -> JUNK (hidden)", self.style.WARNING)
                            continue

                        new_cat = res.get('new_category')
                        valid_categories = [choice[0] for choice in FlagCollection.CATEGORY_CHOICES]
                        if new_cat in valid_categories:
                            flag.category = new_cat
                        
                        ai_iso = self._normalize_iso3(res.get('parent_country_iso3'))
                        bound_country = Country.objects.filter(cca3=ai_iso).first() if ai_iso in sovereign_iso3 else None
                        
                        if bound_country: 
                            flag.country = bound_country
                        
                        try:
                            if res.get('population'): flag.population = int(float(res.get('population')))
                            if res.get('area_km2'): flag.area_km2 = float(res.get('area_km2'))
                        except: pass

                        if bound_country and flag.category == 'country':
                            country_updated = False
                            if res.get('population') and flag.population and flag.population > 0:
                                if bound_country.population == 0 or bound_country.population is None:
                                    bound_country.population = flag.population; country_updated = True
                            if res.get('area_km2') and flag.area_km2 and flag.area_km2 > 0:
                                if bound_country.area_km2 == 0 or bound_country.area_km2 is None:
                                    bound_country.area_km2 = flag.area_km2; country_updated = True
                            if country_updated: bound_country.save()

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
                        self.log(f"      ✅ {flag.name[:25]:<25} -> [{flag.category}] {flag.name_cs[:15]} (Pop: {pop_str}, Area: {area_str})")

                    success = True
                    i += len(chunk)
                    time.sleep(1)

                except Exception as e:
                    err = str(e).lower()
                    attempts += 1
                    
                    # 1. FALLBACK PRO TOKENY: Pokud API zakřičí, že je kontext moc velký
                    if "token" in err or "too large" in err or "context length" in err or "maximum context" in err:
                        self.log(f"   ✂️ [TOKEN LIMIT] Text je příliš dlouhý. Zkracuji data a zkouším znovu...", self.style.WARNING)
                        current_context_limit = 3500
                        time.sleep(2)
                        
                    # 2. BĚŽNÉ CHYBY: Rate limity a přetížení
                    elif "429" in err or "rate limit" in err or "timeout" in err or "503" in err:
                        self.log(f"   ⏳ [LIMIT / 503] Čekám 15s...", self.style.WARNING)
                        time.sleep(15)
                        
                        if len(keys[provider]) > 1:
                            k_idx = (k_idx + 1) % len(keys[provider])
                            current_key_indices[provider] = k_idx
                            self.log(f"      🔄 Přepínám na klíč č. {k_idx+1}.")
                            
                            c_key = keys[provider][k_idx]
                            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=45.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=45.0)
                            
                    # 3. OSTATNÍ CHYBY: Rozbitý JSON atd.
                    else:
                        self.log(f"   ⚠️ [POKUS {attempts} SELHAL] {err[:150]}", self.style.ERROR)
                        if attempts < max_attempts:
                            current_chunk_size = max(1, current_chunk_size - 1)
                            self.log(f"      🔄 Snižuji dávku na {current_chunk_size} a zkouším znovu...", self.style.NOTICE)

            if not success:
                self.log(f"   ❌ [CRITICAL] Přeskakuji tuto dávku, selhala {max_attempts}x po sobě.", self.style.ERROR)
                i += len(chunk)
                current_chunk_size = original_chunk_size
                current_model_idx += 1

        self.log(f"\n🏁 [HOTOVO] Celá fronta zpracována.", self.style.SUCCESS)