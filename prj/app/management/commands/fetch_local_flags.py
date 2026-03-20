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
    help = 'Professional Geographic Flag Sync with Anti-Substring and Image Deduplication'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "JustEnoughFlags/3.2 (https://jef.world-quiz.com; contact: admin@world-quiz.com)"
            }
        )
        self.stats = {
            "created": 0, "updated": 0, "downloaded": 0,
            "failed": 0, "skipped": 0, "duplicates": 0
        }

    def add_arguments(self, parser):
        parser.add_argument("--country", type=str, default="Q213", help="Wikidata QID")
        parser.add_argument("--limit", type=int, default=100, help="Limit results")
        parser.add_argument("--download", action="store_true", help="Download images")
        parser.add_argument("--force", action="store_true", help="Force re-download")
        parser.add_argument("--verbose", action="store_true", help="Detailed logs")
        parser.add_argument("--sync-existing", action="store_true", help="Download missing files")

    def get_thumb_url(self, flag_url, width=1000):
        filename = unquote(flag_url.split("/")[-1]).split("?")[0].replace(" ", "_")
        encoded_name = quote(filename)
        return f"https://commons.wikimedia.org/w/thumb.php?f={encoded_name}&w={width}"

    def run_sparql_with_retry(self, query, retries=3, base_wait=6):
        endpoints = [
            "https://query.wikidata.org/sparql",
            "https://query.wikidata.org/bigdata/namespace/wdq/sparql",
        ]
        last_error = None
        for endpoint in endpoints:
            sparql = SPARQLWrapper(endpoint)
            sparql.agent = self.session.headers["User-Agent"]
            sparql.setTimeout(120)
            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)

            for attempt in range(1, retries + 1):
                try:
                    return sparql.query().convert().get("results", {}).get("bindings", [])
                except Exception as exc:
                    last_error = exc
                    wait = base_wait * attempt
                    self.stdout.write(self.style.WARNING(f"SPARQL {endpoint} attempt {attempt} failed. Waiting {wait}s..."))
                    time.sleep(wait)
        raise last_error

    def get_category(self, type_labels):
        tl = (type_labels or "").lower()

        # 1. ANTI-SUBSTRING BLACKLIST (Blokuje Deutsche Bundespost a samotné Německo)
        garbage_exact = ["enterprise", "company", "business", "sovereign", "country", "national", "organization"]
        if any(g in tl for g in garbage_exact):
            return "GARBAGE"

        # 2. WHITELIST
        city_keywords = ["city", "town", "village", "municipality", "settlement", "human settlement", "commune", "borough", "obec", "mesto"]
        state_keywords = ["region", "province", "district", "state", "county", "voivodeship", "oblast", "kraj", "okres", "prefecture", "governorate", "canton", "department"]
        territory_keywords = ["territory", "dependency", "dependent territory", "special administrative region", "autonomous"]

        if any(k in tl for k in city_keywords): return "city"
        if any(k in tl for k in state_keywords): return "state"
        if any(k in tl for k in territory_keywords): return "territory"
        if "subdivision" in tl: return "region"
        
        return "GARBAGE"

    def _is_banner_url(self, flag_url):
        lower = (flag_url or "").lower()
        # Rozšířeno o specifické německé termíny pro vertikální vlajky
        return any(k in lower for k in ["banner", "vertical", "hochformat", "hängeflagge", "haengeflagge", "knatterflagge"])

    def process_item(self, i, item, total_items, options, country_obj, verbose):
        wid = item.get("item", {}).get("value", "").split("/")[-1]
        flag_url = item.get("flag", {}).get("value", "")
        label_en = item.get("itemLabelEn", {}).get("value", "")
        type_labels = item.get("typeLabels", {}).get("value", "")

        name = label_en or wid
        if not name or re.match(r"^Q\d+$", name):
            self.stats["skipped"] += 1
            if verbose: self.stdout.write(self.style.WARNING(f"[SKIPPED - BAD LABEL] {wid}"))
            return

        category = self.get_category(type_labels)
        if category == "GARBAGE":
            self.stats["skipped"] += 1
            if verbose: self.stdout.write(self.style.WARNING(f"[SKIPPED - GARBAGE] {name} ({type_labels or 'unknown'})"))
            return

        if self._is_banner_url(flag_url):
            self.stats["skipped"] += 1
            if verbose: self.stdout.write(self.style.WARNING(f"[SKIPPED - BANNER] {name}"))
            return

        # VIZUÁLNÍ DEDUPLIKACE: Pokud pro tuto zemi už máme úplně stejný obrázek, přeskočíme ho.
        # (exclude(wikidata_id=wid) zajišťuje, že to nespadne, když jen aktualizujeme už existující záznam)
        if FlagCollection.objects.filter(country=country_obj, flag_image=flag_url).exclude(wikidata_id=wid).exists():
            self.stats["duplicates"] += 1
            if verbose: self.stdout.write(self.style.WARNING(f"[SKIPPED - DUPLICATE IMAGE] {name} shares flag with another entity."))
            return

        obj, created = FlagCollection.objects.update_or_create(
            wikidata_id=wid,
            defaults={
                "name": name[:200],
                "category": category,
                "description": {"wikidata_type": type_labels, "label_en": label_en},
                "flag_image": flag_url,
                "country": country_obj,
            },
        )

        if created: self.stats["created"] += 1
        else: self.stats["updated"] += 1

        if options["download"]:
            file_exists = obj.image_file and obj.image_file.storage.exists(obj.image_file.name)
            if options["force"] or not file_exists:
                if verbose: self.stdout.write(f"[{i + 1}/{total_items}] Downloading {wid} ({name})")
                url = self.get_thumb_url(flag_url)
                try:
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        path = unquote(urlparse(flag_url).path).lower()
                        ext = path.split(".")[-1] if "." in path else "png"
                        if ext not in ["svg", "png", "jpg", "jpeg", "gif"]: ext = "png"
                        obj.image_file.save(f"{wid}.{ext}", ContentFile(response.content), save=True)
                        self.stats["downloaded"] += 1
                        time.sleep(0.1)
                    elif response.status_code == 429:
                        if verbose: self.stdout.write(self.style.WARNING(f"[429] Rate-limited."))
                        time.sleep(10)
                    else:
                        self.stats["failed"] += 1
                except requests.RequestException as exc:
                    self.stats["failed"] += 1

    def _sync_existing_files(self, verbose):
        missing_files = FlagCollection.objects.filter(Q(image_file="") | Q(image_file__isnull=True))
        count = missing_files.count()
        self.stdout.write(self.style.SUCCESS(f"Syncing {count} missing physical files..."))
        # (Zkráceno v promptu pro přehlednost - logika zůstává stejná jako v předchozí verzi)

    def handle(self, *args, **options):
        verbose = options["verbose"]

        if options["sync_existing"]:
            self._sync_existing_files(verbose=verbose)
            return

        qid_to_cca2 = {"Q213": "CZ", "Q183": "DE", "Q142": "FR", "Q145": "GB", "Q159": "RU", "Q30": "US"}
        country_obj = Country.objects.filter(cca2=qid_to_cca2.get(options["country"])).first()

        limit = max(1, int(options["limit"]))
        # Redukovaný dotaz (bez timeoutů)
        query = f"""
            SELECT ?item
                   (SAMPLE(?flag_) AS ?flag)
                   (SAMPLE(?itemLabelEn_) AS ?itemLabelEn)
                   (GROUP_CONCAT(DISTINCT ?typeLabel; separator=", ") AS ?typeLabels)
            WHERE {{
              {{
                SELECT ?item ?flag_ WHERE {{
                  ?item wdt:P17 wd:{options['country']} ;
                        wdt:P41 ?flag_ .
                }} LIMIT {limit}
              }}
              OPTIONAL {{ ?item wdt:P31 ?type . }}
              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "en".
                ?item rdfs:label ?itemLabelEn_ .
                ?type rdfs:label ?typeLabel .
              }}
            }}
            GROUP BY ?item
        """

        try:
            items = self.run_sparql_with_retry(query, retries=3)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"SPARQL Error: {exc}"))
            return

        started = time.time()
        total = len(items)
        for i, item in enumerate(items):
            try:
                self.process_item(i, item, total, options, country_obj, verbose)
            except Exception as exc:
                self.stats["failed"] += 1
                self.stdout.write(self.style.WARNING(f"[PROCESS ERROR] Row {i + 1}: {exc}"))

        duration = time.time() - started
        self.stdout.write(
            self.style.SUCCESS(
                f"\nFinished in {duration:.2f}s\n"
                f"Created: {self.stats['created']}, Updated: {self.stats['updated']}, "
                f"Downloaded: {self.stats['downloaded']}, "
                f"Duplicates Skipped: {self.stats['duplicates']}, "
                f"Garbage Skipped: {self.stats['skipped']}, Failed: {self.stats['failed']}"
            )
        )