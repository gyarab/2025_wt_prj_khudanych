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
from django.db.models import Q

load_dotenv()

class Command(BaseCommand):
    help = 'VIP AI Agent: Generates 5-sentence encyclopedic descriptions + stats for PUBLIC Countries and Dependencies.'

    MODELS = [
        {"name": "gemma-3-27b-it", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "chunk_size": 1},
        {"name": "gemini-3.1-flash-lite-preview", "provider": "google", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "chunk_size": 1},
        {"name": "gpt-oss-120b", "provider": "sambanova", "base_url": "https://api.sambanova.ai/v1", "chunk_size": 1},
        {"name": "openai/gpt-oss-120b", "provider": "groq", "base_url": None, "chunk_size": 1},
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Limit records')
        parser.add_argument('--reset', action='store_true', help='Reset is_verified for VIP categories')

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

    def get_wikipedia_title_from_qid(self, qid, lang="en"):
        if not qid: return None
        url = "https://www.wikidata.org/w/api.php"
        params = {"action": "wbgetentities", "format": "json", "ids": qid, "props": "sitelinks", "sitefilter": f"{lang}wiki"}
        try:
            r = requests.get(url, params=params, timeout=4)
            return r.json()["entities"][qid]["sitelinks"][f"{lang}wiki"]["title"]
        except: return None

    def handle(self, *args, **options):
        google_keys = [os.getenv(f"GOOGLE_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GOOGLE_API_KEY_{j}")]
        keys = {"google": google_keys, 
                "sambanova": [os.getenv(f"SAMBANOVA_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"SAMBANOVA_API_KEY_{j}")],
                "groq": [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]}

        if options['reset']:
            self.log("🧹 [RESET] Vracím VEŘEJNÉ VIP vlajky do oběhu...", self.style.WARNING)
            FlagCollection.objects.filter(category__in=['country', 'dependency'], is_public=True).update(is_verified=False)

        ddgs = DDGS()
        
        flags_qs = FlagCollection.objects.filter(
            category__in=['country', 'dependency'], 
            is_public=True, 
            is_verified=False
        ).order_by('name')
        
        if options['limit'] > 0: flags_qs = flags_qs[:options['limit']]
        
        flags_to_process = list(flags_qs)
        total_count = len(flags_to_process)
        self.log(f"🚀 [VIP START] Zpracovávám {total_count} prioritních veřejných subjektů.", self.style.NOTICE)

        current_key_indices = {"google": 0, "sambanova": 0, "groq": 0}
        current_model_idx = 0
        i = 0

        while i < total_count:
            if current_model_idx >= len(self.MODELS):
                time.sleep(60); current_model_idx = 0; continue

            m_cfg = self.MODELS[current_model_idx]
            provider, model_name = m_cfg["provider"], m_cfg["name"]
            if not keys[provider]: current_model_idx += 1; continue

            k_idx = current_key_indices[provider]
            c_key = keys[provider][k_idx]
            client = OpenAI(base_url=m_cfg["base_url"], api_key=c_key, timeout=60.0) if m_cfg["base_url"] else Groq(api_key=c_key, timeout=60.0)

            f = flags_to_process[i]
            self.log(f"\n💎 [{i+1}/{total_count}] | 🤖 AI: {model_name} | 🏳️ Entita: {f.name}")
            
            ctx = ""
            wiki_stats = []
            for lang in ("en", "cs", "de"):
                title = f.name if lang == "en" else self.get_wikipedia_title_from_qid(f.wikidata_id, lang)
                if title:
                    txt = self.fetch_wikipedia_clean(title, lang)
                    if txt: 
                        wiki_stats.append(f"{lang.upper()}:{len(txt)}")
                        ctx += f"\n--- WIKI {lang.upper()} ({title}) ---\n{txt[:2000]}\n" # Zkráceno na 2000 pro úsporu TPM

            self.log(f"   📖 Wiki nalezeno: [{' | '.join(wiki_stats) if wiki_stats else 'Žádné'}]")

            web_stats = []
            hint = f.country.name_common if f.country else ""
            queries = [f'"{f.name}" {hint} geography population area']
            for q in queries:
                try:
                    res = ddgs.text(q, max_results=3)
                    if res: 
                        found_text = " ".join([r['body'] for r in res])
                        web_stats.append(f"DDGS:{len(found_text)}")
                        ctx += f"\n--- WEB ({q}) ---\n" + found_text + "\n"
                except: pass
                time.sleep(1)
            
            if web_stats:
                self.log(f"   🌐 Web search: [{' | '.join(web_stats)}]")

            # FEW-SHOT PROMPT (Klíč k úspěchu pro Gemmu bez JSON módu)
            prompt = f"""
            Act as an elite Geopolitical Historian. Provide structured data for: {f.name}.
            
            RULES:
            1. Extract exact numeric population and area_km2. Use null if unknown.
            2. Write EXACTLY 5 sentences per language (EN, CS, DE). Focus on deep history and culture. NO population/area numbers in the text!
            3. Translate names perfectly (adjective form for CS history, e.g., "Bavorské království").
            4. STRICT JSON OUTPUT ONLY. Do NOT wrap in markdown unless it's a JSON block.

            EXAMPLE OUTPUT (Do not copy this data, use it as a structure template):
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
                self.log(f"   ⏳ Generuji (max 5 vět, hledám pop/area)...", inline=True)
                start_time = time.time()
                
                # ZDE JE TA MAGIE OPRAVY PRO GEMMU
                api_args = {
                    "messages": [{"role": "user", "content": prompt + f"\n\nDATA TO ANALYZE:\n{ctx[:4500]}"}], # Drasticky zkrácený kontext
                    "model": model_name, 
                    "temperature": 0.0
                }
                
                if "gemma" not in model_name.lower():
                    api_args["response_format"] = {"type": "json_object"}

                resp = client.chat.completions.create(**api_args)
                res = self.extract_json(resp.choices[0].message.content)
                
                elapsed = time.time() - start_time
                self.log(f" [Odpověď za {elapsed:.1f}s]", inline=False)

                if not res: raise ValueError("Invalid JSON from AI")

                # Ukládání textů
                f.name_cs = (res.get('name_cs') or f.name).strip()
                f.name_de = (res.get('name_de') or f.name).strip()
                f.description = {'en': res.get('description_en', ''), 'cs': res.get('description_cs', ''), 'de': res.get('description_de', '')}
                
                # Opatrné zpracování Population & Area
                pop_val = res.get('population')
                area_val = res.get('area_km2')
                
                try: pop_val = int(float(pop_val)) if pop_val else None
                except: pop_val = None
                
                try: area_val = float(area_val) if area_val else None
                except: area_val = None

                # Pokud má vlajka nulu/None, přepíšeme ji
                if pop_val and not f.population: f.population = pop_val
                if area_val and not f.area_km2: f.area_km2 = area_val

                # TVRDÝ SYNC DO HLAVNÍ TABULKY COUNTRY (Přepíše vše!)
                # TVRDÝ SYNC S OPRAVOU VAZBY
                if f.country:
                    # 1. POKUS O ZÁCHRANU: Najdeme tu "pravou" zemi podle jména, pokud je ta současná špatná
                    # (Hledáme v modelu Country, kde jsou ta hezká data s měnou a ISO)
                    real_country = Country.objects.filter(
                        Q(name_common__iexact=f.name) | Q(name_official__iexact=f.name)
                    ).first()

                    # Pokud jsme našli tu pravou, přemapujeme vlajku na ni
                    target_country = real_country if real_country else f.country
                    
                    if real_country and f.country != real_country:
                        self.log(f"   🔗 PŘEMAPOVÁVÁM: Vlajka {f.name} nyní ukazuje na správný Country model.")
                        f.country = real_country
                    
                    country_updated = False
                    if pop_val:
                        target_country.population = pop_val
                        country_updated = True
                    if area_val:
                        target_country.area_km2 = area_val
                        # Pokud tvůj model používá pole 'area' místo 'area_km2', zapíšeme i tam
                        if hasattr(target_country, 'area'):
                            target_country.area = area_val
                        country_updated = True
                    
                    if country_updated:
                        target_country.save()
                        self.log(f"   🔄 Data TVRDĚ uložena do Country modelu: {target_country.name_common}")

                f.is_verified = True
                f.save()
                
                # Zobrazení do terminálu
                p_str = f"{f.population:,}" if f.population else "Neznámá"
                a_str = f"{f.area_km2:,.2f}" if f.area_km2 else "Neznámá"
                self.log(f"   ✅ Uloženo: CS={f.name_cs[:20]}... | Pop: {p_str} | Area: {a_str}")
                i += 1
                time.sleep(1.5) # Ochrana TPM

            except Exception as e:
                err = str(e).lower()
                if "rate" in err or "limit" in err or "429" in err or "503" in err:
                    self.log("   ⏳ Rate limit... přepínám klíč (30s pauza).", self.style.WARNING)
                    time.sleep(30)
                    k_idx = (k_idx + 1) % len(keys[provider])
                    current_key_indices[provider] = k_idx
                    if k_idx == 0: current_model_idx += 1
                else:
                    self.log(f"   ⚠️ Chyba parsování/API: {err[:150]}", self.style.ERROR)
                    i += 1 

        self.log("\n🎉 Všechny veřejné VIP subjekty mají své popisy a statistiky!", self.style.SUCCESS)