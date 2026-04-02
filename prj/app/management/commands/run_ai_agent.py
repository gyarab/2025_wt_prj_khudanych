import json
import time
import os
import re
from ddgs import DDGS
from groq import Groq
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from app.models import FlagCollection, Country

load_dotenv()

class Command(BaseCommand):
    help = 'Balanced AI Agent: Exact numbers only, calibrated confidence.'

    def add_arguments(self, parser):
        parser.add_argument('--chunk-size', type=int, default=2, help='Malé dávky pro lepší soustředění AI')
        parser.add_argument('--limit', type=int, default=0, help='Limit zpracovaných vlajek')
        parser.add_argument('--reset', action='store_true', help='Reset is_verified status')

    def extract_json(self, text):
        try:
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(text)
        except Exception:
            return None

    def handle(self, *args, **options):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            self.stdout.write(self.style.ERROR("Chybí GROQ_API_KEY!"))
            return

        if options['reset']:
            self.stdout.write(self.style.WARNING("🔄 Resetuji stav vlajek na is_verified=False..."))
            FlagCollection.objects.all().update(is_verified=False)

        client = Groq(api_key=api_key)
        ddgs = DDGS()
        
        flags_to_process = FlagCollection.objects.filter(is_public=True, is_verified=False)
        if options['limit'] > 0:
            flags_to_process = flags_to_process[:options['limit']]
            
        total = flags_to_process.count()
        self.stdout.write(self.style.NOTICE(f"🚀 Llama 4 Scout startuje pro {total} vlajek..."))

        for i in range(0, total, options['chunk_size']):
            chunk = flags_to_process[i:i + options['chunk_size']]
            data_to_send = []
            
            for f in chunk:
                self.stdout.write(f"  🔍 Hledám kontext pro: {f.name}...")
                
                query_info = f"{f.name} flag {f.category} history overview"
                query_stats = f"{f.name} {f.category} exact population area city size"
                
                combined_context = ""
                try:
                    res_info = ddgs.text(query_info, max_results=4)
                    time.sleep(1)
                    res_stats = ddgs.text(query_stats, max_results=3)
                    
                    if res_info:
                        combined_context += "[INFO]: " + " ".join([r.get('body', '') for r in res_info])
                    if res_stats:
                        combined_context += " [STATS]: " + " ".join([r.get('body', '') for r in res_stats])
                except Exception as e:
                    combined_context = f"Search failed or rate limited: {e}"

                data_to_send.append({
                    "qid": str(f.wikidata_id),
                    "name": f.name,
                    "current_category": f.category,
                    "web_data": combined_context[:3000]
                })

            prompt = f"""
            Act as an uncompromising Data Architect. Process {len(data_to_send)} entities.

            STEP 1: CATEGORY & BINDING
            - Determine 'new_category' (state, city, region, territory, historical, international).
            - Identify the modern sovereign country this belongs to. Provide its 3-letter ISO code in 'parent_country_iso3' (e.g., 'DEU' for Aachen, 'RUS' for Abdulino). If unknown, return null.

            STEP 2: STATISTICS & CALIBRATED CONFIDENCE (CRITICAL)
            - Extract EXACT 'population' and 'area_km2'. DO NOT ROUND NUMBERS! If the source says 1420153, return 1420153, not 1400000.
            - WARNING: Do NOT assign a huge parent country's area to a small city.
            - Provide 'stats_confidence' (0.0 to 1.0) using this STRICT scale:
              * 0.8 to 1.0: You are very confident the stats belong specifically to this city/region/state.
              * 0.5 to 0.7: You found stats, but the web text is slightly ambiguous.
              * 0.0 to 0.4: You suspect Context Bleed (e.g., parent country's area assigned to city), OR the entity is a fake micronation. If so, return null for the numbers.

            STEP 3: MULTILINGUAL DESCRIPTIONS & FALLBACK
            - Write exactly 2 sentences in English, Czech, and German.
            - INTERNAL CZECH QA: Perfect declensions. No robotic phrasing. Use exonyms (Aachen -> Cáchy).
            - FALLBACK: If 'web_data' is empty or lacks details, rely on your internal knowledge base to write 2 interesting, universally accepted historical or geographical facts about the entity.

            Return ONLY JSON mapping QID to results.
            FORMAT:
            {{"qid": {{"new_category": "...", "parent_country_iso3": "USA", "population": 123456, "area_km2": 45.67, "stats_confidence": 0.9, "description_en": "...", "description_cs": "...", "description_de": "..."}}}}
            
            DATA: {json.dumps(data_to_send)}
            """

            try:
                response = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )
                
                ai_results = self.extract_json(response.choices[0].message.content)
                if not ai_results: 
                    self.stdout.write(self.style.ERROR("  [Chyba]: AI nevrátila platný JSON."))
                    continue

                for flag in chunk:
                    res = ai_results.get(str(flag.wikidata_id))
                    if res:
                        self.stdout.write(self.style.MIGRATE_HEADING(f"\n--- Zpracovávám: {flag.name} ---"))
                        
                        allowed_cats = ['state', 'city', 'region', 'territory', 'historical', 'international']
                        new_cat = res.get('new_category', flag.category)
                        if new_cat not in allowed_cats: new_cat = 'historical'
                        
                        if new_cat != flag.category:
                            self.stdout.write(self.style.WARNING(f"  [Kategorie]: {flag.category} -> {new_cat}"))
                        flag.category = new_cat

                        stats_conf = res.get('stats_confidence', 0.0)
                        
                        if stats_conf < 0.75:
                            flag.population = None
                            flag.area_km2 = None
                            self.stdout.write(self.style.WARNING(f"  [Python Veto]: Statistiky smazány (Jistota AI: {stats_conf})."))
                        else:
                            if 'population' in res: flag.population = res.get('population')
                            if 'area_km2' in res: flag.area_km2 = res.get('area_km2')

                        iso3 = res.get('parent_country_iso3')
                        if iso3:
                            parent = Country.objects.filter(cca3=iso3.upper()).first()
                            if parent:
                                flag.country = parent
                                self.stdout.write(self.style.SUCCESS(f"  [Binding]: Úspěšně připojeno k {parent.name_common} ({iso3})"))

                        desc = {}
                        desc['en'] = res.get('description_en', 'Data unavailable.')
                        desc['cs'] = res.get('description_cs', 'Data nejsou k dispozici.')
                        desc['de'] = res.get('description_de', 'Daten nicht verfügbar.')
                        flag.description = desc
                        
                        flag.is_verified = True
                        flag.save()
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Ošetřeno a uloženo."))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Batch failed: {e}"))
                time.sleep(5)
            
            time.sleep(3)