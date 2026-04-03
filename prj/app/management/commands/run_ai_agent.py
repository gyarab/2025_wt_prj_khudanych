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
        parser.add_argument('--chunk-size', type=int, default=1)
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--reset', action='store_true')

    def log(self, message, style=None):
        styled = style(message) if style else message
        self.stdout.write(styled)
        self.stdout.flush()

    def extract_json(self, text):
        try:
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(text)
        except Exception:
            return None

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
        except Exception:
            pass
        return ""

    def fetch_multilingual_context(self, title):
        context_parts = []
        for lang in ("en", "cs", "de"):
            raw = self.fetch_wikipedia_raw(title, lang=lang)
            if raw:
                context_parts.append(f"\n--- WIKI {lang.upper()} ---\n{raw[:1800]}\n")
        return "".join(context_parts)

    def _normalize_iso3(self, value):
        if not isinstance(value, str):
            return None
        iso3 = value.strip().upper()
        return iso3 if len(iso3) == 3 and iso3.isalpha() else None

    def _is_historical_entity(self, name, web_data, ai_category):
        if ai_category == 'historical':
            return True

        text = f"{name} {web_data}".lower()
        keywords = (
            'micronation',
            'self-proclaimed state',
            'defunct',
            'former empire',
            'dissolved',
            'no longer exists',
            'extinct state',
            'unrecognized state',
        )
        return any(k in text for k in keywords)

    def _resolve_name_country(self, name):
        return Country.objects.filter(name_common__iexact=name).first() or Country.objects.filter(name_official__iexact=name).first()

    def _valid_category(self, category, fallback):
        allowed = set(FlagCollection.CATEGORY_VALUES)
        if category in allowed:
            return category
        if fallback in allowed:
            return fallback
        return 'historical'

    def _to_int(self, value):
        try:
            if value is None or value == '':
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _to_float(self, value):
        try:
            if value is None or value == '':
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def apply_geopolitical_rules(self, flag, result, web_data, sovereign_iso3):
        ai_category = self._valid_category(result.get('new_category'), flag.category)
        ai_parent_iso3 = self._normalize_iso3(result.get('parent_country_iso3'))
        matched_by_name = self._resolve_name_country(flag.name)
        bound_country = None

        # Rule A: sovereign UN state must be category=state and bind to its own ISO3.
        if matched_by_name and matched_by_name.un_member:
            ai_category = 'state'
            ai_parent_iso3 = matched_by_name.cca3
            bound_country = matched_by_name
        elif ai_parent_iso3 in sovereign_iso3:
            ai_category = 'state'
            bound_country = Country.objects.filter(cca3=ai_parent_iso3).first()

        # Rule C: micronations/defunct empires must be historical.
        if self._is_historical_entity(flag.name, web_data, ai_category):
            ai_category = 'historical'

        # Rule B: dependencies should be territories and bind to parent sovereign country.
        if ai_category == 'territory':
            if ai_parent_iso3 and ai_parent_iso3 in sovereign_iso3:
                bound_country = Country.objects.filter(cca3=ai_parent_iso3).first()
            elif flag.country and flag.country.cca3 in sovereign_iso3:
                bound_country = flag.country
        
        # Keep category inside strict set even after rule enforcement.
        ai_category = self._valid_category(ai_category, flag.category)

        # If still classified as state and we have a matching sovereign country, force self-binding.
        if ai_category == 'state' and bound_country and bound_country.un_member:
            ai_parent_iso3 = bound_country.cca3

        return ai_category, ai_parent_iso3, bound_country

    def handle(self, *args, **options):
        api_keys = [os.getenv(f"GROQ_API_KEY_{j}") for j in range(1, 10) if os.getenv(f"GROQ_API_KEY_{j}")]
        if not api_keys:
            legacy = os.getenv("GROQ_API_KEY")
            if legacy:
                api_keys = [legacy]

        if not api_keys:
            self.log("Chybí API klíče v .env!", self.style.ERROR)
            return

        if options['reset']:
            self.log("[RESET] Zahajuji hromadný reset příznaku is_verified v databázi...", self.style.WARNING)
            start_reset = time.time()
            count = FlagCollection.objects.all().update(is_verified=False)
            duration = time.time() - start_reset

            self.log(f"[RESET] Resetováno {count} záznamů za {duration:.2f} sekund.", self.style.SUCCESS)

        ddgs = DDGS()
        flags_to_process = FlagCollection.objects.filter(is_public=True, is_verified=False)
        if options['limit'] > 0:
            flags_to_process = flags_to_process[:options['limit']]

        total = flags_to_process.count()
        self.log(f"[START] Master Agent startuje pro {total} vlajek...", self.style.NOTICE)

        if total == 0:
            self.log("[DONE] Žádné záznamy ke zpracování.", self.style.SUCCESS)
            return

        current_model_idx = 0
        current_key_idx = 0
        client = Groq(api_key=api_keys[current_key_idx])
        sovereign_iso3 = set(
            Country.objects.filter(un_member=True).values_list('cca3', flat=True)
        )
        i = 0

        while i < total:
            chunk = flags_to_process[i:i + options['chunk_size']]
            data_to_send = []

            for f in chunk:
                self.log(f"[FETCH] Sběr dat (Multilingual Wiki): {f.name}")
                ctx = self.fetch_multilingual_context(f.name)

                try:
                    time.sleep(1)
                    res_stats = ddgs.text(f"{f.name} population area", max_results=2)
                    if res_stats:
                        ctx += "\n--- SEARCH ---\n" + " ".join([r.get('body', '') for r in res_stats])
                except Exception:
                    pass

                data_to_send.append({
                    "qid": str(f.wikidata_id or ''),
                    "name": f.name,
                    "current_category": f.category,
                    "country_iso3": f.country.cca3 if f.country else None,
                    "web_data": ctx[:5500],
                })

            prompt = f"""
            Act as an elite Data Architect and Polyglot Translator. Process {len(data_to_send)} entities.
            
            CONTEXT: You have raw Wikipedia data in EN, CS, and DE. 

            STEP 1: CATEGORY & BINDING (STRICT RULES)
            - Determine 'new_category'. You MUST choose exactly ONE from this list: ["state", "city", "region", "territory", "historical", "international"].
              * If it is a micronation (e.g., Robland) or a defunct empire (Romanov), use "historical".
              * If it is a sovereign country (e.g., Romania), use "state".
            - Determine 'parent_country_iso3'. If the entity is a sovereign country itself, return its own 3-letter ISO code.

            STEP 2: STATISTICS (PRECISION OVER BEAUTY)
            - Extract 'population' and 'area_km2'. 
            - PRECISION RULE: You MUST search for the most precise, non-rounded numbers in [WIKI_RAW_DATA] (e.g., look for "|population_total = 252765" instead of "about 250k").
            - DO NOT ROUND: If the source says 160.83, do NOT return 160 or 161. Return 160.83.
            - If you find two conflicting numbers, prioritize the one with more decimal places or more specific digits.
            - stats_confidence (0.0 to 1.0): 
                * 0.7-1.0: Clear specific data found.
                * 0.4-0.6: Data found but looks slightly ambiguous.
                * <0.4: Clear Context Bleed (using country area for a city).

            STEP 3: NAME TRANSLATION (EXONYMS)
            - Translate the entity's actual name into Czech ('name_cs') and German ('name_de').
            - Use established historical exonyms where applicable.

            STEP 4: MULTILINGUAL DESCRIPTIONS
            - Write exactly 2 sentences in English, Czech, and German.
            - CZECH QUALITY: Perfect gender agreement. Use formal tone.

            Return ONLY JSON:
            {{"qid": {{"new_category": "...", "parent_country_iso3": "...", "population": 123, "area_km2": 45, "stats_confidence": 0.9, "name_cs": "...", "name_de": "...", "description_en": "...", "description_cs": "...", "description_de": "..."}}}}
            
            DATA: {json.dumps(data_to_send)}
            """

            success = False
            while current_model_idx < len(self.MODELS) and not success:
                model_name = self.MODELS[current_model_idx]
                try:
                    self.log(f"[MODEL] {model_name} (Klíč: {current_key_idx + 1})")
                    response = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name, temperature=0.0, response_format={"type": "json_object"}
                    )
                    ai_results = self.extract_json(response.choices[0].message.content)
                    if not ai_results:
                        raise ValueError("AI response neobsahuje validní JSON objekt.")

                    for flag in chunk:
                        result_key = str(flag.wikidata_id or '')
                        res = ai_results.get(result_key)
                        if not res:
                            # Fallback for responses keyed by name instead of qid.
                            res = ai_results.get(flag.name)
                        if not res:
                            self.log(f"[SKIP] Chybí výsledek pro {flag.name}", self.style.WARNING)
                            continue

                        self.log(f"--- {flag.name} ---", self.style.MIGRATE_HEADING)

                        web_data = next((x.get('web_data') for x in data_to_send if x.get('name') == flag.name), '')
                        category, parent_iso3, bound_country = self.apply_geopolitical_rules(
                            flag, res, web_data, sovereign_iso3
                        )

                        flag.category = category
                        if bound_country:
                            flag.country = bound_country
                            self.log(
                                f"  [Binding] Připojeno k {bound_country.name_common} ({bound_country.cca3})",
                                self.style.SUCCESS,
                            )
                        elif parent_iso3:
                            self.log(
                                f"  [Binding] AI navrhla {parent_iso3}, ale stát nebyl nalezen v tabulce Country.",
                                self.style.WARNING,
                            )
                        else:
                            self.log("  [Binding] Parent ISO-3 neurčeno.", self.style.WARNING)

                        confidence = self._to_float(res.get('stats_confidence'))
                        if confidence is not None and confidence >= 0.4:
                            flag.population = self._to_int(res.get('population'))
                            flag.area_km2 = self._to_float(res.get('area_km2'))
                        else:
                            flag.population = None
                            flag.area_km2 = None
                            self.log(
                                f"  [Veto] Statistiky smazány (Jistota: {confidence if confidence is not None else 0.0})",
                                self.style.WARNING,
                            )

                        name_cs = (res.get('name_cs') or '').strip()
                        name_de = (res.get('name_de') or '').strip()
                        flag.name_cs = name_cs or flag.name
                        flag.name_de = name_de or flag.name

                        flag.description = {
                            'en': (res.get('description_en') or '').strip(),
                            'cs': (res.get('description_cs') or '').strip(),
                            'de': (res.get('description_de') or '').strip(),
                            'parent_country_iso3': parent_iso3 or (flag.country.cca3 if flag.country else None),
                        }
                        flag.is_verified = True
                        flag.save()

                    success = True
                except Exception as e:
                    err = str(e)
                    self.log(f"[ERROR] {model_name}: {err}", self.style.WARNING)
                    if "429" in err and current_key_idx < len(api_keys) - 1:
                        current_key_idx += 1
                        client = Groq(api_key=api_keys[current_key_idx])
                        self.log(f"[RETRY] Přepínám na API klíč {current_key_idx + 1}", self.style.WARNING)
                        continue
                    if "429" in err and current_key_idx >= len(api_keys) - 1:
                        current_key_idx = 0
                        current_model_idx += 1
                        if current_model_idx < len(self.MODELS):
                            client = Groq(api_key=api_keys[current_key_idx])
                            self.log(f"[FALLBACK] Přepínám model na {self.MODELS[current_model_idx]}", self.style.WARNING)
                        break

                    current_key_idx = 0
                    current_model_idx += 1
                    if current_model_idx < len(self.MODELS):
                        client = Groq(api_key=api_keys[current_key_idx])
                        self.log(f"[FALLBACK] Přepínám model na {self.MODELS[current_model_idx]}", self.style.WARNING)
                    break

            if current_model_idx >= len(self.MODELS):
                self.log("[STOP] Všechny modely vyčerpány. Zpracování ukončeno.", self.style.ERROR)
                break

            i += options['chunk_size']
            time.sleep(2)

        self.log("[DONE] Běh run_ai_agent dokončen.", self.style.SUCCESS)