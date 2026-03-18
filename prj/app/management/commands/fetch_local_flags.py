import time
import requests
import re
from urllib.parse import urlparse, quote, unquote
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.db.models import Q
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
        parser.add_argument('--sync-existing', action='store_true', help='Download missing files for existing records')

    def get_thumb_url(self, flag_url, width=1000):
        filename = unquote(flag_url.split('/')[-1]).split('?')[0].replace(' ', '_')
        encoded_name = quote(filename)
        return f"https://commons.wikimedia.org/w/thumb.php?f={encoded_name}&w={width}"

    def get_category(self, type_labels, entity_name):
        tl = type_labels.lower()
        en = entity_name.lower()
        
        # Detect garbage entities
        garbage_keywords = ['ethnic group', 'people', 'sports team', 'organization', 'political party', 'diaspora', 'movement']
        if any(w in tl for w in garbage_keywords) or any(w in en for w in garbage_keywords):
            return 'GARBAGE'
            
        if any(w in tl for w in ['municipality', 'city', 'town', 'village', 'obec', 'město', 'district of prague']):
            return 'city'
        if any(w in tl for w in ['region', 'province', 'kraj', 'district', 'okres', 'voivodeship', 'oblast']):
            return 'state'
        if any(w in tl for w in ['territory', 'dependent']):
            return 'territory'
        if any(w in en for w in ['city', 'town', 'municipal']):
            return 'city'
        return 'region'

    def process_item(self, i, item, total_items, options, country_obj, verbose, delay):
        wid = item["item"]["value"].split('/')[-1]
        flag_url = item.get("flag", {}).get("value", "")
        
        # Naming Fallback
        label_en = item.get("itemLabelEn", {}).get("value", "")
        native_label = item.get("nativeLabel", {}).get("value", "")
        fallback_label = item.get("fallbackLabel", {}).get("value", wid)
        type_labels = item.get("typeLabels", {}).get("value", "Subdivision")
        
        name = fallback_label
        if label_en and not re.match(r'^Q\d+$', label_en):
            name = label_en
        elif native_label:
            name = native_label
            
        # Category and Garbage Filter
        category = self.get_category(type_labels, name)
        if category == 'GARBAGE':
            if verbose: self.stdout.write(self.style.WARNING(f"  [Skipped] Garbage entity (type/name): {name} ({wid})"))
            self.stats['skipped'] += 1
            return

        # Vertical Banner Blocker
        flag_url_lower = flag_url.lower()
        if any(kw in flag_url_lower for kw in ['banner', 'vertical', 'hochformat', 'hangefahne', 'hängefahne']):
            if verbose: self.stdout.write(self.style.WARNING(f"  [Skipped] Vertical banner: {name} ({wid})"))
            self.stats['skipped'] += 1
            return

        # 1. Atomic DB Update
        obj, created = FlagCollection.objects.update_or_create(
            wikidata_id=wid,
            defaults={
                'name': name[:200],
                'category': category,
                'description': {"wikidata_type": type_labels, "label_en": label_en, "native_label": native_label},
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
                if verbose: self.stdout.write(f"  [{i+1}/{total_items}] Downloading {wid} ({name})...")
                
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

    def handle(self, *args, **options):
        verbose = options['verbose']
        delay = options['delay']
        
        # 1. Sync Existing Logic (Download missing physical files)
        if options['sync_existing']:
            missing_files = FlagCollection.objects.filter(Q(image_file='') | Q(image_file__isnull=True))
            count = missing_files.count()
            self.stdout.write(self.style.SUCCESS(f"🔄 Syncing {count} missing physical files..."))
            
            for i, obj in enumerate(missing_files):
                if verbose: self.stdout.write(f"  [{i+1}/{count}] Downloading {obj.wikidata_id} ({obj.name})...")
                
                url = self.get_thumb_url(obj.flag_image)
                try:
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        path = unquote(urlparse(obj.flag_image).path).lower()
                        ext = path.split('.')[-1] if '.' in path else 'png'
                        if ext not in ['svg', 'png', 'jpg', 'jpeg', 'gif']: ext = 'png'
                        obj.image_file.save(f"{obj.wikidata_id}.{ext}", ContentFile(response.content), save=True)
                        self.stats['downloaded'] += 1
                        time.sleep(0.1)  # Respect Wikimedia's servers
                    elif response.status_code == 429:
                        self.stdout.write(self.style.WARNING(f"  [429] Rate limit hit. Cooling down for 10s..."))
                        time.sleep(10)
                except Exception as e:
                    if verbose: self.stdout.write(f"  [Error] {obj.wikidata_id}: {e}")
                    self.stats['failed'] += 1

            self.stdout.write(self.style.SUCCESS(f"✅ Sync complete. Downloaded: {self.stats['downloaded']}, Failed: {self.stats['failed']}"))
            return

        # 2. Main SPARQL Sync
        self.stdout.write(self.style.SUCCESS(f"🚀 Starting Universal Geographic Flag Sync"))

        cca2_map = {'Q213': 'CZ', 'Q183': 'DE', 'Q142': 'FR', 'Q145': 'GB', 'Q159': 'RU', 'Q30': 'US'}
        country_obj = Country.objects.filter(cca2=cca2_map.get(options['country'])).first()

        sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        sparql.agent = self.session.headers['User-Agent']
        sparql.setTimeout(120)  # Increase timeout to 2 minutes
        
        query = f"""
            SELECT ?item 
                   (SAMPLE(?itemLabelEn_) AS ?itemLabelEn) 
                   (SAMPLE(?nativeLabel_) AS ?nativeLabel)
                   (SAMPLE(?fallbackLabel_) AS ?fallbackLabel)
                   (SAMPLE(?flag_) AS ?flag) 
                   (GROUP_CONCAT(DISTINCT ?typeLabel; separator=", ") AS ?typeLabels) 
            WHERE {{
                # 1. BLESKOVÝ PODDOTAZ S LIMITACÍ (Tohle je ta záchrana!)
                {{
                    SELECT ?item ?flag_ WHERE {{
                        ?item wdt:P17 wd:{options['country']} ;
                              wdt:P41 ?flag_ .
                        FILTER NOT EXISTS {{ ?item wdt:P576 ?dissolved }}
                    }} LIMIT {options['limit']}
                }}
                
                # 2. Typy a labely se teď hledají jen pro těch max nalezených
                OPTIONAL {{ ?item wdt:P31 ?type . }}
                OPTIONAL {{ ?item wdt:P1705 ?nativeLabel_ . }}
                
                # Filter out ethnic groups and organizations
                FILTER NOT EXISTS {{ ?type wdt:P279* wd:Q41710 }}
                FILTER NOT EXISTS {{ ?type wdt:P279* wd:Q43229 }}
                
                SERVICE wikibase:label {{ 
                    bd:serviceParam wikibase:language "en". 
                    ?item rdfs:label ?itemLabelEn_ . 
                    ?item rdfs:label ?fallbackLabel_ . 
                    ?type rdfs:label ?typeLabel . 
                }}
            }} GROUP BY ?item
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
            try:
                self.process_item(i, item, len(items), options, country_obj, verbose, delay)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [Critical Error] Failed to process item {i+1}: {e}"))
                self.stats['failed'] += 1

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                self.stdout.write(f"  Processed {i+1} items. Speed: {(i+1)/elapsed:.1f} items/sec")

        duration = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Finished in {duration:.2f}s!\n"
            f"Created: {self.stats['created']}, Updated: {self.stats['updated']}, Downloaded: {self.stats['downloaded']}, Skipped (Banner): {self.stats['skipped']}, Failed: {self.stats['failed']}"
        ))