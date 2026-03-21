import re
import time
from urllib.parse import quote, unquote, urlparse

import requests
from SPARQLWrapper import JSON, SPARQLWrapper
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q

from app.models import Country, FlagCollection


class Command(BaseCommand):
    help = "Professional Geographic Flag Sync with Anti-Substring, Deduplication and Smart Updates"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "JustEnoughFlags/3.6 (https://jef.world-quiz.com; contact: info@world-quiz.com)"
            }
        )
        self.stats = {
            "created": 0,
            "updated": 0,
            "downloaded": 0,
            "failed": 0,
            "garbage": 0,
            "duplicates": 0,
            "skipped_exists": 0,
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
                    self.stdout.write(
                        self.style.WARNING(
                            f"SPARQL {endpoint} attempt {attempt} failed. Waiting {wait}s..."
                        )
                    )
                    time.sleep(wait)

        raise last_error

    def get_category(self, type_labels):
        tl = (type_labels or "").lower()

        hard_garbage = [
            "team",
            "political party",
            "ethnic group",
            "human population",
            "sovereign state",
            "country",
            "state-owned enterprise",
            "delegation",
            "position",
            "general staff",
            "military",
            "air force"
        ]
        if any(g in tl for g in hard_garbage):
            return "GARBAGE"

        city_keywords = [
            "city",
            "town",
            "village",
            "municipality",
            "municipal part",
            "settlement",
            "commune",
            "borough",
            "quarter",
            "stadtteil",
            "ortsteil",
            "obec",
            "mesto",
            "capital",
            "cadastral area"
        ]
        state_keywords = [
            "region",
            "province",
            "district",
            "county",
            "voivodeship",
            "oblast",
            "kraj",
            "okres",
            "prefecture",
            "governorate",
            "canton",
            "department",
        ]

        if any(k in tl for k in city_keywords):
            return "city"
        if any(k in tl for k in state_keywords):
            return "state"
        if "territory" in tl or "autonomous" in tl:
            return "territory"
        if "subdivision" in tl:
            return "region"

        soft_garbage = ["enterprise", "company", "business", "national", "organization", "agency", "council"]
        if any(g in tl for g in soft_garbage):
            return "GARBAGE"

        return "GARBAGE"

    def _is_banner_url(self, flag_url):
        lower = (flag_url or "").lower()
        return any(
            k in lower
            for k in ["banner", "vertical", "hochformat", "hängeflagge", "haengeflagge", "knatterflagge"]
        )

    def _pick_disambiguated_name(self, en_name, native_name):
        if native_name and "(" in native_name and ")" in native_name:
            return native_name
        if en_name and "(" in en_name and ")" in en_name:
            return en_name
        return native_name or en_name

    def _parse_wikidata_point(self, point_value):
        if not point_value:
            return None, None

        match = re.match(r"^Point\(([-\d\.]+)\s+([-\d\.]+)\)$", point_value.strip())
        if not match:
            return None, None

        try:
            lon = float(match.group(1))
            lat = float(match.group(2))
            return lat, lon
        except ValueError:
            return None, None

    def process_item(self, i, item, total_items, options, country_obj, verbose):
        wid = item.get("item", {}).get("value", "").split("/")[-1]
        flag_url = item.get("flag", {}).get("value", "")
        label_en = item.get("itemLabelEn", {}).get("value", "")
        label_native = item.get("itemLabelNative", {}).get("value", "")
        coordinates = item.get("coordinates", {}).get("value", "")
        type_labels = item.get("typeLabels", {}).get("value", "")
        
        # Extract population and area directly from SPARQL results
        pop_str = item.get("population", {}).get("value", "")
        area_str = item.get("area", {}).get("value", "")
        
        latitude, longitude = self._parse_wikidata_point(coordinates)
        
        # Safely convert strings to numbers
        population = None
        if pop_str:
            try:
                population = int(float(pop_str))
            except ValueError:
                pass
                
        area_km2 = None
        if area_str:
            try:
                area_km2 = float(area_str)
            except ValueError:
                pass

        name = self._pick_disambiguated_name(label_en or wid, label_native)
        if not name or re.match(r"^Q\d+$", name):
            self.stats["garbage"] += 1
            if verbose:
                self.stdout.write(self.style.WARNING(f"[SKIPPED - BAD LABEL] {wid}"))
            return

        category = self.get_category(type_labels)
        if category == "GARBAGE":
            self.stats["garbage"] += 1
            if verbose:
                self.stdout.write(
                    self.style.WARNING(f"[SKIPPED - GARBAGE] {name} ({type_labels or 'unknown'})")
                )
            return

        if self._is_banner_url(flag_url):
            self.stats["garbage"] += 1
            if verbose:
                self.stdout.write(self.style.WARNING(f"[SKIPPED - BANNER] {name}"))
            return

        duplicate_check = FlagCollection.objects.filter(country=country_obj, flag_image=flag_url).exclude(
            wikidata_id=wid
        )
        if duplicate_check.exists():
            self.stats["duplicates"] += 1
            if verbose:
                self.stdout.write(
                    self.style.WARNING(
                        f"[SKIPPED - DUPLICATE IMAGE] {name} shares flag with another entity."
                    )
                )
            return

        old_flag_url = None
        existing_obj = FlagCollection.objects.filter(wikidata_id=wid).first()
        if existing_obj:
            old_flag_url = existing_obj.flag_image

        obj, created = FlagCollection.objects.update_or_create(
            wikidata_id=wid,
            defaults={
                "name": name[:200],
                "category": category,
                "description": {
                    "wikidata_type": type_labels,
                    "label_en": label_en,
                    "label_native": label_native,
                },
                "flag_image": flag_url,
                "latitude": latitude,
                "longitude": longitude,
                "population": population,
                "area_km2": area_km2,
                "country": country_obj,
            },
        )

        if created:
            self.stats["created"] += 1
        else:
            self.stats["updated"] += 1
            if old_flag_url and old_flag_url != flag_url:
                if obj.image_file:
                    obj.image_file.delete(save=False)
                obj.save()

        if options["download"]:
            file_exists = bool(
                obj.image_file and obj.image_file.name and obj.image_file.storage.exists(obj.image_file.name)
            )

            if options["force"] or not file_exists:
                if verbose:
                    self.stdout.write(f"[{i + 1}/{total_items}] Downloading {wid} ({name})")
                url = self.get_thumb_url(flag_url)
                try:
                    response = self.session.get(url, timeout=15)
                    if response.status_code == 200:
                        path = unquote(urlparse(flag_url).path).lower()
                        ext = path.split(".")[-1] if "." in path else "png"
                        if ext not in ["svg", "png", "jpg", "jpeg", "gif"]:
                            ext = "png"
                        obj.image_file.save(f"{wid}.{ext}", ContentFile(response.content), save=True)
                        self.stats["downloaded"] += 1
                        time.sleep(0.1)
                    elif response.status_code == 429:
                        if verbose:
                            self.stdout.write(self.style.WARNING("[429] Rate-limited."))
                        time.sleep(10)
                    else:
                        self.stats["failed"] += 1
                except requests.RequestException:
                    self.stats["failed"] += 1
            else:
                self.stats["skipped_exists"] += 1
                if verbose:
                    self.stdout.write(self.style.SUCCESS(f"[SKIPPED - FILE EXISTS] {wid} ({name})"))

    def _sync_existing_files(self, verbose):
        missing_files = FlagCollection.objects.filter(Q(image_file="") | Q(image_file__isnull=True))
        count = missing_files.count()
        self.stdout.write(self.style.SUCCESS(f"Syncing {count} missing physical files..."))
        
        for i, obj in enumerate(missing_files):
            if verbose:
                self.stdout.write(f"[{i + 1}/{count}] Recovering image for {obj.wikidata_id} ({obj.name})")
            url = self.get_thumb_url(obj.flag_image)
            try:
                response = self.session.get(url, timeout=15)
                if response.status_code == 200:
                    path = unquote(urlparse(obj.flag_image).path).lower()
                    ext = path.split(".")[-1] if "." in path else "png"
                    if ext not in ["svg", "png", "jpg", "jpeg", "gif"]:
                        ext = "png"
                    obj.image_file.save(f"{obj.wikidata_id}.{ext}", ContentFile(response.content), save=True)
                    self.stats["downloaded"] += 1
                    time.sleep(0.1)
                elif response.status_code == 429:
                    if verbose:
                        self.stdout.write(self.style.WARNING("[429] Rate-limited."))
                    time.sleep(10)
                else:
                    self.stats["failed"] += 1
            except requests.RequestException:
                self.stats["failed"] += 1

    def handle(self, *args, **options):
        verbose = options["verbose"]

        if options["sync_existing"]:
            self._sync_existing_files(verbose=verbose)
            
            self.stdout.write(self.style.SUCCESS(f"\n--- SYNC RECOVERY REPORT ---"))
            self.stdout.write(f"Images -> Recovered: {self.stats['downloaded']} | Failed: {self.stats['failed']}")
            return

        qid_to_cca2 = {"Q213": "CZ", "Q183": "DE", "Q142": "FR", "Q145": "GB", "Q159": "RU", "Q30": "US"}
        country_obj = Country.objects.filter(cca2=qid_to_cca2.get(options["country"])).first()

        qid_to_lang = {"Q213": "cs", "Q183": "de", "Q142": "fr", "Q145": "en", "Q159": "ru", "Q30": "en"}
        native_lang = qid_to_lang.get(options["country"], "en")

        limit = max(1, int(options["limit"]))

        query = f"""
            SELECT ?item
                   (SAMPLE(?flag_) AS ?flag)
                   (SAMPLE(?itemLabelEn_) AS ?itemLabelEn)
                   (SAMPLE(?itemLabelNative_) AS ?itemLabelNative)
                   (SAMPLE(?coordinates_) AS ?coordinates)
                   (MAX(?population_) AS ?population)
                   (MAX(?area_) AS ?area)
                   (GROUP_CONCAT(DISTINCT ?typeLabel; separator=", ") AS ?typeLabels)
            WHERE {{
              {{
                SELECT ?item ?flag_ WHERE {{
                  ?item wdt:P17 wd:{options['country']} ;
                        wdt:P41 ?flag_ .
                  # MAGIE: Vyfiltrujeme bannery dřív, než dojde k výběru!
                  FILTER(!REGEX(LCASE(STR(?flag_)), "banner|vertical|hochformat|hängeflagge|haengeflagge|knatterflagge"))
                }} LIMIT {limit}
              }}
              OPTIONAL {{ ?item wdt:P31 ?type . }}
              OPTIONAL {{ ?item wdt:P625 ?coordinates_ . }}
              OPTIONAL {{ ?item wdt:P1082 ?population_ . }}
              OPTIONAL {{ ?item wdt:P2046 ?area_ . }}
              OPTIONAL {{
                  ?item rdfs:label ?itemLabelNative_ .
                  FILTER(LANG(?itemLabelNative_) = "{native_lang}")
              }}
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

        self.stdout.write(self.style.SUCCESS(f"\n--- SYNC REPORT ({duration:.2f}s) ---"))
        self.stdout.write(f"DB Records -> Created: {self.stats['created']} | Updated: {self.stats['updated']}")
        self.stdout.write(
            f"Images     -> Downloaded: {self.stats['downloaded']} | Already Existed: {self.stats['skipped_exists']} | Failed: {self.stats['failed']}"
        )
        self.stdout.write(
            f"Skipped    -> Garbage/Banners: {self.stats['garbage']} | Duplicates: {self.stats['duplicates']}"
        )