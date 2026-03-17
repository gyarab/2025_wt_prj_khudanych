import time
import requests
from urllib.parse import urlparse, unquote
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.db import IntegrityError
from SPARQLWrapper import SPARQLWrapper, JSON
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = 'Automated Flag Downloader from Wikidata to Django Media'

    def add_arguments(self, parser):
        parser.add_argument('--country', type=str, default='Q213', help='Wikidata QID of the country (default: Q213 for Czechia)')
        parser.add_argument('--limit', type=int, default=100, help='Limit the number of new results to fetch')
        parser.add_argument('--sync-existing', action='store_true', help='Download images for existing records that lack them')

    def download_flag(self, flag_url, wikidata_id):
        """Download image from Wikimedia and return a ContentFile."""
        headers = {
            'User-Agent': 'JustEnoughFlags/2.0 (educational project; contact: sergio@example.com)'
        }
        
        try:
            # We use the original Wikimedia URL (not the thumb.php) for downloading the full file
            # However, for huge SVGs, we might want to download a smaller version.
            # For this task, we follow the requirement to download the "image file".
            
            # If the URL is already a thumb.php, we might want the original.
            # But usually, Wikidata P41 gives the direct link to the file.
            
            response = requests.get(flag_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Determine extension
            parsed = urlparse(flag_url)
            ext = parsed.path.split('.')[-1].lower()
            if ext not in ['svg', 'png', 'jpg', 'jpeg', 'gif']:
                # Try to guess from content type if extension is missing
                ctype = response.headers.get('Content-Type', '')
                if 'svg' in ctype: ext = 'svg'
                elif 'png' in ctype: ext = 'png'
                elif 'jpeg' in ctype: ext = 'jpg'
                elif 'gif' in ctype: ext = 'gif'
                else: ext = 'bin'
            
            filename = f"{wikidata_id}.{ext}"
            return ContentFile(response.content, name=filename)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to download {flag_url}: {e}"))
            return None

    def get_category(self, type_labels):
        """Map Wikidata entity type labels to FlagCollection category choices."""
        tl = type_labels.lower()
        if any(w in tl for w in ['municipality', 'city', 'town', 'village', 'obec', 'město', 'district of prague']):
            return 'city'
        if any(w in tl for w in ['region', 'province', 'kraj', 'district', 'okres', 'voivodeship', 'oblast']):
            return 'state'
        if any(w in tl for w in ['territory', 'dependent']):
            return 'territory'
        return 'region'

    def handle(self, *args, **options):
        country_qid = options['country']
        limit = options['limit']
        sync_existing = options['sync_existing']
        
        # 1. Sync existing records if requested
        if sync_existing:
            self.stdout.write("Syncing existing records lacking local files...")
            to_sync = FlagCollection.objects.filter(image_file='').exclude(wikidata_id__isnull=True)
            self.stdout.write(f"Found {to_sync.count()} records to process.")
            
            for fc in to_sync:
                self.stdout.write(f"  Downloading for {fc.name} ({fc.wikidata_id})...")
                # Use the stored URL
                file_content = self.download_flag(fc.flag_image, fc.wikidata_id)
                if file_content:
                    fc.image_file.save(file_content.name, file_content, save=True)
                    self.stdout.write(self.style.SUCCESS(f"    Saved as {fc.image_file.name}"))
                time.sleep(0.5) # Respect limits

        # 2. Fetch new records from Wikidata
        self.stdout.write(f"Fetching new flags for country {country_qid} from Wikidata...")
        
        # Mapping for common countries to help linking
        QID_TO_CCA2 = {'Q213': 'CZ', 'Q183': 'DE', 'Q142': 'FR', 'Q145': 'GB', 'Q159': 'RU', 'Q30': 'US'}
        cca2 = QID_TO_CCA2.get(country_qid)
        country_obj = Country.objects.filter(cca2=cca2).first() if cca2 else None

        sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
        sparql.agent = "JustEnoughFlags/2.0 (educational project; contact: sergio@example.com)"
        
        query = f"""
        SELECT ?item 
               (SAMPLE(?itemLabel_) AS ?itemLabel) 
               (SAMPLE(?itemLabelCs_) AS ?itemLabelCs) 
               (SAMPLE(?flag_) AS ?flag) 
               (GROUP_CONCAT(DISTINCT ?typeLabel; separator=", ") AS ?typeLabels) 
        WHERE {{
          ?item wdt:P17 wd:{country_qid} .
          ?item wdt:P41 ?flag_ .
          ?item wdt:P31 ?type .
          SERVICE wikibase:label {{ 
            bd:serviceParam wikibase:language "en,cs". 
            ?item rdfs:label ?itemLabel_ .
            ?type rdfs:label ?typeLabel .
          }}
          OPTIONAL {{
            ?item rdfs:label ?itemLabelCs_ .
            FILTER(LANG(?itemLabelCs_) = "cs")
          }}
        }}
        GROUP BY ?item
        LIMIT {limit}
        """
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        
        try:
            results = sparql.query().convert()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Network error or SPARQL failure: {e}"))
            return

        items = results.get("results", {}).get("bindings", [])
        self.stdout.write(f"Found {len(items)} items in Wikidata.")

        success_count = 0
        for result in items:
            wid = result["item"]["value"].split('/')[-1]
            label_en = result.get("itemLabel", {}).get("value", "")
            label_cs = result.get("itemLabelCs", {}).get("value", "")
            flag_url = result.get("flag", {}).get("value", "")
            type_labels = result.get("typeLabels", {}).get("value", "Subdivision")

            name = label_cs if label_cs else label_en
            category = self.get_category(type_labels)

            # get_or_create to avoid duplicates
            obj, created = FlagCollection.objects.get_or_create(
                wikidata_id=wid,
                defaults={
                    'name': name[:200],
                    'category': category,
                    'flag_image': flag_url, # Store URL as fallback/reference
                    'country': country_obj,
                    'description': {"wikidata_type": type_labels, "label_en": label_en, "label_cs": label_cs}
                }
            )

            if created or not obj.image_file:
                self.stdout.write(f"  {'New' if created else 'Existing'}: {name} ({wid})...")
                file_content = self.download_flag(flag_url, wid)
                if file_content:
                    obj.image_file.save(file_content.name, file_content, save=True)
                    self.stdout.write(self.style.SUCCESS(f"    Saved as {obj.image_file.name}"))
                    success_count += 1
                time.sleep(0.5) # Small delay to respect Wikimedia limits
            else:
                self.stdout.write(f"  Skipping {name} ({wid}), local file already exists.")

        self.stdout.write(self.style.SUCCESS(f"Sync complete. Processed {success_count} downloads."))
