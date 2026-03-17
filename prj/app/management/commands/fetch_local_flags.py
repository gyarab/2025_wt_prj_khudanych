import time
import requests
from urllib.parse import urlparse, quote, unquote
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from SPARQLWrapper import SPARQLWrapper, JSON
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = 'Geographic-only Flag Downloader: Filters out sports teams and non-territorial entities'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'JustEnoughFlags/1.0 (https://jef.svs.gyarab.cz/; contact: admin@svs.gyarab.cz) python-requests/2.31'
        })
        self.stats = {'created': 0, 'updated': 0, 'downloaded': 0, 'failed': 0, 'skipped': 0}

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, default='Q213', help='Wikidata QID')
        parser.add_argument('--limit', type=int, default=10000, help='Limit results')
        parser.add_argument('--download', action='store_true', help='Download images')
        parser.add_argument('--force', action='store_true', help='Force re-download')
        parser.add_argument('--verbose', action='store_true', help='Detailed logs')
        parser.add_argument('--delay', type=float, default=0.03, help='Delay between requests (default: 0.03s)')

    def get_thumb_url(self, flag_url, width=1000):
        filename = unquote(flag_url.split('/')[-1]).split('?')[0].replace(' ', '_')
        encoded_name = quote(filename)
        return f"https://commons.wikimedia.org/w/thumb.php?f={encoded_name}&w={width}"

    def get_category(self, type_labels, entity_name):
        tl = type_labels.lower()
        en = entity_name.lower()
        if any(w in tl for w in ['municipality', 'city', 'town', 'village', 'obec', 'město', 'district of prague']):
            return 'city'
        if any(w in tl for w in ['region', 'province', 'kraj', 'district', 'okres', 'voivodeship', 'oblast']):
            return 'state'
        if any(w in tl for w in ['territory', 'dependent']):
            return 'territory'
        if any(w in en for w in ['city', 'town', 'municipal']):
            return 'city'
        return 'region'

    def is_garbage_entity(self, label, type_labels):
        """Filter out sports teams, Olympic delegations, and other non-geographic noise."""
        l = label.lower()
        tl = type_labels.lower()
        
        # Keywords for sports teams and delegations
        garbage_keywords = [
            'national team', 'reprezentace', 'reprezentační', 'olympijsk', 'paralympijsk', 
            'hockey', 'football', 'handball', 'volleyball', 'basketball', 'club', 'klub',
            'championship', 'mistrovství', 'at the olympics', 'na olympijských'
        ]
        
        # Check both the label and the Wikidata type labels
        if any(kw in l for kw in garbage_keywords) or any(kw in tl for kw in garbage_keywords):
            return True
            
        # Exclude specific organization/event types if they don't look geographic
        if any(kw in tl for kw in ['organization', 'event', 'delegation', 'association']):
            # Geographic entities usually have these keywords
            geographic_keywords = ['municipality', 'city', 'town', 'village', 'obec', 'město', 'region', 'district']
            if not any(kw in tl for kw in geographic_keywords):
                return True
                
        return False

    def handle(self, *args, **options):
        verbose = options['verbose']
        delay = options['delay']
        
        self.stdout.write(self.style.SUCCESS(f"🚀 Starting Filtered High-Speed Sync (Excluding Sports/Noise)"))

        cca2_map = {'Q213': 'CZ', 'Q183': 'DE', 'Q142': 'FR', 'Q145': 'GB', 'Q159': 'RU', 'Q30': 'US'}
        country_obj = Country.objects.filter(cca2=cca2_map.get(options['country'])).first()

        sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        sparql.agent = self.session.headers['User-Agent']
        
        # Enhanced SPARQL with initial exclusions for sports/teams
        query = f"""
            SELECT ?item (SAMPLE(?itemLabel_) AS ?itemLabel) (SAMPLE(?itemLabelCs_) AS ?itemLabelCs) 
                   (SAMPLE(?flag_) AS ?flag) (GROUP_CONCAT(DISTINCT ?typeLabel; separator=", ") AS ?typeLabels) 
            WHERE {{
                ?item wdt:P17 wd:{options['country']} . 
                ?item wdt:P41 ?flag_ . 
                ?item wdt:P31 ?type .
                
                # Exclude obvious non-geographic types (National Sports Team, Olympic Delegation, etc.)
                FILTER NOT EXISTS {{ ?item wdt:P31/wdt:P279* wd:Q21008035 }} # National sports team
                FILTER NOT EXISTS {{ ?item wdt:P31/wdt:P279* wd:Q1063162 }}  # Country at the Olympics
                FILTER NOT EXISTS {{ ?item wdt:P31/wdt:P279* wd:Q15991290 }} # National team
                
                SERVICE wikibase:label {{ 
                    bd:serviceParam wikibase:language "en,cs". 
                    ?item rdfs:label ?itemLabel_ . 
                    ?type rdfs:label ?typeLabel . 
                }}
                OPTIONAL {{ ?item rdfs:label ?itemLabelCs_ . FILTER(LANG(?itemLabelCs_) = "cs") }}
            }} GROUP BY ?item LIMIT {options['limit']}
        """
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        
        try:
            items = sparql.query().convert().get("results", {}).get("bindings", [])
            self.stdout.write(f"Fetched {len(items)} items. Filtering and processing...")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"SPARQL Error: {e}"))
            return

        start_time = time.time()
        for i, item in enumerate(items):
            wid = item["item"]["value"].split('/')[-1]
            flag_url = item.get("flag", {}).get("value", "")
            label_en = item.get("itemLabel", {}).get("value", "Unknown")
            label_cs = item.get("itemLabelCs", {}).get("value", "")
            type_labels = item.get("typeLabels", {}).get("value", "Subdivision")
            name = label_cs if label_cs else label_en

            # Apply "Garbage Filter" (Sports teams, Olympics, etc.)
            if self.is_garbage_entity(name, type_labels):
                if verbose: self.stdout.write(self.style.WARNING(f"  [Skipped] Garbage entity: {name} ({wid})"))
                self.stats['skipped'] += 1
                continue

            # 1. Atomic DB Update
            obj, created = FlagCollection.objects.update_or_create(
                wikidata_id=wid,
                defaults={
                    'name': name[:200],
                    'category': self.get_category(type_labels, name),
                    'description': {"wikidata_type": type_labels, "label_en": label_en, "label_cs": label_cs},
                    'flag_image': flag_url,
                    'country': country_obj
                }
            )
            
            if created: self.stats['created'] += 1
            else: self.stats['updated'] += 1

            # 2. Download Logic
            if options['download']:
                file_exists = obj.image_file and obj.image_file.storage.exists(obj.image_file.name)
                if options['force'] or not file_exists:
                    if verbose: self.stdout.write(f"  [{i+1}/{len(items)}] Downloading {wid} ({name})...")
                    
                    url = self.get_thumb_url(flag_url)
                    try:
                        response = self.session.get(url, timeout=15)
                        if response.status_code == 200:
                            path = unquote(urlparse(flag_url).path).lower()
                            ext = path.split('.')[-1] if '.' in path else 'png'
                            if ext not in ['svg', 'png', 'jpg', 'jpeg', 'gif']: ext = 'png'
                            obj.image_file.save(f"{wid}.{ext}", ContentFile(response.content), save=True)
                            self.stats['downloaded'] += 1
                            time.sleep(delay)
                        elif response.status_code == 429:
                            self.stdout.write(self.style.WARNING(f"  [429] Rate limit hit. Cooling down for 10s..."))
                            time.sleep(10)
                        else:
                            self.stats['failed'] += 1
                    except Exception as e:
                        if verbose: self.stdout.write(f"  [Error] {wid}: {e}")
                        self.stats['failed'] += 1

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                self.stdout.write(f"  Processed {i+1} items. Speed: {(i+1)/elapsed:.1f} items/sec")

        duration = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Finished in {duration:.2f}s!\n"
            f"Created: {self.stats['created']}, Updated: {self.stats['updated']}, Downloaded: {self.stats['downloaded']}, Skipped (Garbage): {self.stats['skipped']}"
        ))
