import time
import requests
import re
from urllib.parse import urlparse, quote, unquote
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from SPARQLWrapper import SPARQLWrapper, JSON
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = 'Professional Geographic Flag Sync: Subqueries, Garbage Filters & Banner Blocker'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JustEnoughFlags/3.0 (sergio@example.com)'
        })

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, default='Q213', help='Wikidata QID')
        parser.add_argument('--limit', type=int, default=100, help='Limit results')
        parser.add_argument('--download', action='store_true', help='Download images')
        parser.add_argument('--verbose', action='store_true', help='Show detailed logs')

    def get_category(self, type_labels, entity_name):
        # Necháme Python jen rozlišit, jestli je to město nebo region (pro barvičky na webu)
        tl = type_labels.lower()
        if any(w in tl for w in ['region', 'province', 'district', 'state', 'okres', 'kraj']):
            return 'state'
        return 'city' # Všechno ostatní zachycené SPARQLem bude prostě město/obec

    def handle(self, *args, **options):
        country_qid = options['country']
        
        # Mapování na Country objekt
        QID_TO_CCA2 = {'Q213': 'CZ', 'Q183': 'DE', 'Q142': 'FR', 'Q145': 'GB', 'Q159': 'RU', 'Q30': 'US'}
        country_obj = Country.objects.filter(cca2=QID_TO_CCA2.get(country_qid)).first()

        sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        sparql.agent = self.session.headers['User-Agent']
        
        # OPTIMALIZOVANÝ DOTAZ (Limit Pushdown + Subquery)
        query = f"""
            SELECT ?item 
                   (SAMPLE(?itemLabelEn_) AS ?itemLabelEn) 
                   (SAMPLE(?itemLabelCs_) AS ?itemLabelCs) 
                   (SAMPLE(?flag_) AS ?flag) 
                   (GROUP_CONCAT(DISTINCT ?typeLabel; separator=", ") AS ?typeLabels) 
            WHERE {{
                # 1. Rychlý výběr 500 věcí s vlajkou (Zabrání Timeoutu 504)
                {{
                    SELECT ?item ?flag_ WHERE {{
                        ?item wdt:P17 wd:{country_qid} ;
                              wdt:P41 ?flag_ .
                        FILTER NOT EXISTS {{ ?item wdt:P576 ?dissolved }}
                    }} LIMIT {options['limit']}
                }}
                
                # 2. ZJIŠTĚNÍ TYPU A KONTROLA RODOKMENU (Tohle vyřadí Trivago, Albánce i firmy!)
                ?item wdt:P31 ?type .
                ?type wdt:P279* ?geo_type .
                VALUES ?geo_type {{ wd:Q15284 wd:Q486972 }} 
                
                # 3. Získání popisků
                OPTIONAL {{ ?item wdt:P1705 ?nativeLabel_ . }}
                SERVICE wikibase:label {{ 
                    bd:serviceParam wikibase:language "en,cs". 
                    ?item rdfs:label ?itemLabelEn_ . 
                    ?type rdfs:label ?typeLabel . 
                }}
                OPTIONAL {{ ?item rdfs:label ?itemLabelCs_ . FILTER(LANG(?itemLabelCs_) = "cs") }}
            }} GROUP BY ?item
        """
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert().get("results", {}).get("bindings", [])

        for result in results:
            wid = result["item"]["value"].split('/')[-1]
            flag_url = result.get("flag", {}).get("value", "")
            label_en = result.get("itemLabelEn", {}).get("value", "")
            label_cs = result.get("itemLabelCs", {}).get("value", "")
            type_labels = result.get("typeLabels", {}).get("value", "")

            # Logika pro jméno a kategorii
            name_display = label_cs if label_cs else label_en
            category = self.get_category(type_labels, name_display)

            if category == 'GARBAGE':
                if options['verbose']: self.stdout.write(self.style.WARNING(f"  Skipped Garbage: {name_display}"))
                continue

            # Banner blocker
            if any(kw in flag_url.lower() for kw in ['banner', 'vertical', 'hochformat']):
                continue

            # Uložení (včetně anglického jména pro SLUG v modelu)
            obj, created = FlagCollection.objects.update_or_create(
                wikidata_id=wid,
                defaults={
                    'name': name_display[:200],
                    'category': category,
                    'flag_image': flag_url,
                    'country': country_obj,
                    'description': {"wikidata_type": type_labels, "label_en": label_en}
                }
            )
            
            # Download (pomocí tvé download_flag funkce nebo thumb URL)
            if options['download'] and (created or not obj.image_file):
                # ... (zde doplň svůj download_flag kód)
                self.stdout.write(self.style.SUCCESS(f"  Synced: {name_display}"))