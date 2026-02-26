"""
Management command: populate_wikidata
--------------------------------------
Phase 1 – Countries  (~260 rows, stored in Country model)
Phase 2 – Subdivisions, historical entities, cities, organisations …
           (stored in FlagCollection, typically 800-1500+ rows)

Everything comes from the Wikidata SPARQL endpoint.

Usage:
    python manage.py populate_wikidata              # update all
    python manage.py populate_wikidata --clear      # wipe & re-import
    python manage.py populate_wikidata --phase 1    # only countries
    python manage.py populate_wikidata --phase 2    # only extra flags
"""

import time
import requests
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from app.models import Region, Country, FlagCollection


# ── Constants ────────────────────────────────────────────────────────────────

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "JustEnoughFlags/2.0 (educational project; https://github.com)",
}

REGION_DESCRIPTIONS = {
    "Africa":    "The second-largest and second-most populous continent.",
    "Americas":  "Comprising North America, Central America, South America and the Caribbean.",
    "Antarctic": "The southernmost continent, surrounding the South Pole.",
    "Asia":      "The largest and most populous continent.",
    "Europe":    "The second-smallest continent, known for its rich history.",
    "Oceania":   "A geographic region including Australasia, Melanesia, Micronesia and Polynesia.",
}

CONTINENT_QID_MAP = {
    "Q15": "Africa", "Q48": "Asia", "Q46": "Europe",
    "Q49": "Americas", "Q828": "Americas", "Q18": "Americas",
    "Q27611": "Americas", "Q664609": "Americas",
    "Q538": "Oceania", "Q51": "Antarctic",
}
CONTINENT_LABEL_MAP = {
    "africa": "Africa", "asia": "Asia", "europe": "Europe",
    "north america": "Americas", "south america": "Americas",
    "central america": "Americas", "caribbean": "Americas",
    "americas": "Americas", "oceania": "Oceania",
    "australia": "Oceania", "antarctica": "Antarctic",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def run_sparql(query: str, retries: int = 3) -> list:
    for attempt in range(retries):
        try:
            r = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  Rate-limited – waiting {wait}s …")
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(5)
            else:
                raise
        except requests.exceptions.RequestException:
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise
    return []


def val(row: dict, key: str) -> str:
    return row.get(key, {}).get("value", "")


def qid(uri: str) -> str:
    """Extract Wikidata QID from a full URI."""
    return uri.rsplit("/", 1)[-1] if uri else ""


def iso2_to_emoji(iso2: str) -> str:
    if len(iso2) != 2 or not iso2.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


def commons_thumb(svg_url: str, width: int = 320) -> str:
    if not svg_url:
        return ""
    filename = svg_url.split("/")[-1]
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width={width}"


# ── SPARQL Queries ───────────────────────────────────────────────────────────

# Phase 1: sovereign countries + territories that have ISO alpha-2 codes
QUERY_COUNTRIES = """
SELECT ?country ?isoA2
       (SAMPLE(?isoA3_)         AS ?isoA3)
       (SAMPLE(?nameEn_)        AS ?nameEn)
       (MAX(?pop_)              AS ?population)
       (SAMPLE(?flag_)          AS ?flagSvg)
       (SAMPLE(?capitalName_)   AS ?capital)
       (MAX(?area_)             AS ?areaKm2)
       (SAMPLE(?continent_)     AS ?continentQID)
       (SAMPLE(?continentName_) AS ?continentLabel)
WHERE {
  ?country wdt:P297 ?isoA2.
  OPTIONAL { ?country wdt:P298 ?isoA3_. }
  OPTIONAL { ?country rdfs:label ?nameEn_. FILTER(LANG(?nameEn_) = "en") }
  OPTIONAL { ?country wdt:P1082 ?pop_. }
  OPTIONAL { ?country wdt:P41  ?flag_. }
  OPTIONAL {
    ?country wdt:P36 ?cap_.
    ?cap_ rdfs:label ?capitalName_.
    FILTER(LANG(?capitalName_) = "en")
  }
  OPTIONAL { ?country wdt:P2046 ?area_. }
  OPTIONAL {
    ?country wdt:P30 ?cont_.
    BIND(STR(?cont_) AS ?continent_)
    ?cont_ rdfs:label ?continentName_.
    FILTER(LANG(?continentName_) = "en")
  }
}
GROUP BY ?country ?isoA2
ORDER BY ?isoA2
"""

# Phase 2a: Entities with flags, split by country batches to avoid timeouts.
# No FILTER NOT EXISTS (too expensive) — we skip countries in Python instead.
QUERY_FLAGS_BY_COUNTRIES = """
SELECT ?item ?itemLabel ?flag ?countryISO
WHERE {{
  VALUES ?countryISO {{ {values} }}
  ?country wdt:P297 ?countryISO .
  ?item wdt:P17 ?country .
  ?item wdt:P41 ?flag .
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 400
"""

# Countries grouped into small batches (5-8 per query) for reliability
COUNTRY_BATCHES = [
    ["DE", "FR", "GB", "IT", "ES"],
    ["NL", "BE", "PL", "AT", "CZ"],
    ["CH", "SE", "NO", "DK", "FI"],
    ["PT", "IE", "HU", "RO", "HR"],
    ["GR", "BG", "RS", "SK", "SI"],
    ["LT", "LV", "EE", "LU", "IS"],
    ["UA", "RU", "BY", "AL", "MK"],
    ["BA", "ME", "MD", "MT", "CY"],
    ["US", "CA", "MX", "BR", "AR"],
    ["CO", "CL", "PE", "VE", "EC"],
    ["BO", "PY", "UY", "CR", "PA"],
    ["CU", "DO", "GT", "HN", "SV"],
    ["CN", "JP", "IN", "ID", "KR"],
    ["TH", "PH", "VN", "MY", "SG"],
    ["PK", "BD", "LK", "MM", "NP"],
    ["TR", "IR", "IQ", "SA", "AE"],
    ["IL", "JO", "KW", "QA", "OM"],
    ["KZ", "UZ", "GE", "AM", "AZ"],
    ["ZA", "NG", "EG", "KE", "ET"],
    ["GH", "TZ", "CI", "CM", "SN"],
    ["MA", "DZ", "TN", "SD", "UG"],
    ["AU", "NZ", "FJ", "PG", "WS"],
]

# Phase 2b: historical countries / former countries (direct instance-of, no transitive)
QUERY_HISTORICAL = """
SELECT ?item ?itemLabel ?flag
WHERE {
  ?item wdt:P41 ?flag .
  ?item wdt:P31 ?type .
  FILTER(?type IN (wd:Q3024240, wd:Q1790360, wd:Q133311, wd:Q839954,
                   wd:Q28171280, wd:Q15642541, wd:Q3624078))
  MINUS { ?item wdt:P297 [] }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 500
"""

# Phase 2c: international / intergovernmental organisations with flags (direct)
QUERY_INTERNATIONAL = """
SELECT ?item ?itemLabel ?flag
WHERE {
  ?item wdt:P41 ?flag .
  ?item wdt:P31 ?type .
  FILTER(?type IN (wd:Q484652, wd:Q7210356, wd:Q3918328, wd:Q1335818,
                   wd:Q1065, wd:Q47543, wd:Q1043481))
  MINUS { ?item wdt:P17 [] }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 300
"""


# ── Command ──────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Populate countries + 1000+ extra flags from Wikidata SPARQL"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true",
                            help="Wipe all data before importing")
        parser.add_argument("--phase", type=int, default=0,
                            help="Run only phase 1 (countries) or 2 (extras). 0 = both.")

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1 – Countries
    # ─────────────────────────────────────────────────────────────────────────
    def phase1_countries(self, regions):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Phase 1: Countries ==="))
        self.stdout.write("Querying Wikidata for countries ...")
        rows = run_sparql(QUERY_COUNTRIES)
        self.stdout.write(f"  Got {len(rows)} rows")

        created = updated = skipped = 0
        for i, row in enumerate(rows, 1):
            iso2 = val(row, "isoA2").strip().upper()
            iso3 = val(row, "isoA3").strip().upper()
            name = val(row, "nameEn").strip()
            if not name or not iso2:
                skipped += 1
                continue
            if name.startswith("Q") and name[1:].isdigit():
                skipped += 1
                continue
            if not iso3:
                iso3 = "X" + iso2

            pop_raw = val(row, "population")
            try:
                population = int(float(pop_raw)) if pop_raw else 0
            except ValueError:
                population = 0

            flag_svg_wm = val(row, "flagSvg")
            if flag_svg_wm and flag_svg_wm.lower().endswith(".svg"):
                flag_svg = flag_svg_wm
                flag_png = commons_thumb(flag_svg_wm, 320)
            else:
                flag_svg = f"https://flagcdn.com/{iso2.lower()}.svg"
                flag_png = f"https://flagcdn.com/w320/{iso2.lower()}.png"

            capital = val(row, "capital").strip()
            area_raw = val(row, "areaKm2")
            try:
                area = float(area_raw) if area_raw else None
            except ValueError:
                area = None

            cont_uri = val(row, "continentQID")
            cont_qid = qid(cont_uri)
            cont_label = val(row, "continentLabel").strip().lower()
            region_name = CONTINENT_QID_MAP.get(cont_qid) or CONTINENT_LABEL_MAP.get(cont_label)
            region = regions.get(region_name)

            defaults = {
                "name_common": name, "name_official": name,
                "cca2": iso2, "capital": capital, "region": region,
                "population": population,
                "flag_svg": flag_svg, "flag_png": flag_png,
                "flag_emoji": iso2_to_emoji(iso2),
            }
            if area is not None:
                defaults["area"] = area

            try:
                _, was_created = Country.objects.update_or_create(cca3=iso3, defaults=defaults)
                created += 1 if was_created else 0
                updated += 0 if was_created else 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"  [{iso2}] {name}: {exc}"))
                skipped += 1

            if i % 50 == 0:
                self.stdout.write(f"  ... {i}/{len(rows)}")

        total = Country.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  Phase 1 done -- created {created}, updated {updated}, "
            f"skipped {skipped}, total in DB: {total}"
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2 – Everything else -> FlagCollection
    # ─────────────────────────────────────────────────────────────────────────
    def _country_lookup(self) -> dict:
        """Build {iso2: Country} mapping for FK linking."""
        return {c.cca2: c for c in Country.objects.all()}

    def _save_flag(self, name, flag_url, category, wikidata_id,
                   country_iso2, country_map, seen, description=""):
        """Save one FlagCollection row. Returns True if new row created."""
        if not name or not flag_url:
            return False
        dedup_key = wikidata_id or name
        if dedup_key in seen:
            return False
        seen.add(dedup_key)
        if name.startswith("Q") and name[1:].isdigit():
            return False

        country_obj = country_map.get(country_iso2.upper()) if country_iso2 else None

        if flag_url.lower().endswith(".svg"):
            image_url = commons_thumb(flag_url, 320)
        else:
            image_url = flag_url

        if wikidata_id:
            _, created = FlagCollection.objects.update_or_create(
                wikidata_id=wikidata_id,
                defaults={
                    "name": name[:200],
                    "category": category,
                    "description": (description or "")[:500],
                    "flag_image": image_url,
                    "country": country_obj,
                },
            )
        else:
            _, created = FlagCollection.objects.get_or_create(
                name=name[:200], category=category,
                defaults={
                    "description": (description or "")[:500],
                    "flag_image": image_url,
                    "country": country_obj,
                    "wikidata_id": "",
                },
            )
        return created

    def _classify_name(self, name):
        """Guess a category from the entity label."""
        nl = name.lower()
        if any(w in nl for w in (" city", " town", " municipal", " commune",
                                  " borough", " metropol")):
            return "city"
        if any(w in nl for w in ("province", "state of", "canton", "prefecture",
                                  "voivodeship", "oblast", "department",
                                  "governorate", "emirate", "county of",
                                  "autonomous community", "district")):
            return "state"
        if any(w in nl for w in ("territory", "dependent", "overseas")):
            return "territory"
        return "region"  # default for subdivision-like entities

    def phase2_extras(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Phase 2: Extra Flags ==="))
        country_map = self._country_lookup()
        # Build set of Wikidata QIDs for countries (to skip them in phase 2a)
        country_qids = set()
        # We don't have QIDs stored, but we can skip by name match against Country table
        country_names = set(Country.objects.values_list("name_common", flat=True))
        seen = set()
        total_created = 0

        # ── 2a: flagged entities in batches by country ──────────────
        self.stdout.write("  [2a] Flagged entities by country batches ...")
        for idx, batch in enumerate(COUNTRY_BATCHES):
            values_str = " ".join(f'"{iso}"' for iso in batch)
            query = QUERY_FLAGS_BY_COUNTRIES.format(values=values_str)
            self.stdout.write(f"       Batch {idx+1}/{len(COUNTRY_BATCHES)} ({', '.join(batch)}) ...")
            try:
                rows = run_sparql(query)
                batch_created = 0
                for row in rows:
                    wid = qid(val(row, "item"))
                    entity_name = val(row, "itemLabel").strip()
                    # Skip if this is actually a country (already in Phase 1)
                    if entity_name in country_names:
                        continue
                    cat = self._classify_name(entity_name)
                    batch_created += self._save_flag(
                        name=entity_name,
                        flag_url=val(row, "flag"),
                        category=cat,
                        wikidata_id=wid,
                        country_iso2=val(row, "countryISO").strip(),
                        country_map=country_map,
                        seen=seen,
                    )
                total_created += batch_created
                self.stdout.write(f"         -> {len(rows)} rows, {batch_created} new")
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"         -> failed: {exc}"))
            time.sleep(2)

        time.sleep(3)

        # ── 2b: historical ──────────────────────────────────────────
        self.stdout.write("  [2b] Historical countries ...")
        try:
            rows = run_sparql(QUERY_HISTORICAL)
            self.stdout.write(f"       Got {len(rows)} rows")
            for row in rows:
                wid = qid(val(row, "item"))
                total_created += self._save_flag(
                    name=val(row, "itemLabel").strip(),
                    flag_url=val(row, "flag"),
                    category="historical",
                    wikidata_id=wid,
                    country_iso2="",
                    country_map=country_map,
                    seen=seen,
                )
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"       Historical query failed: {exc}"))

        time.sleep(3)

        # ── 2c: international organisations ─────────────────────────
        self.stdout.write("  [2c] International organisations ...")
        try:
            rows = run_sparql(QUERY_INTERNATIONAL)
            self.stdout.write(f"       Got {len(rows)} rows")
            for row in rows:
                wid = qid(val(row, "item"))
                total_created += self._save_flag(
                    name=val(row, "itemLabel").strip(),
                    flag_url=val(row, "flag"),
                    category="international",
                    wikidata_id=wid,
                    country_iso2="",
                    country_map=country_map,
                    seen=seen,
                )
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"       International query failed: {exc}"))

        fc_total = FlagCollection.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"  Phase 2 done -- new flags created: {total_created}, "
            f"total in FlagCollection: {fc_total}"
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # handle()
    # ─────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing all data ...")
            FlagCollection.objects.all().delete()
            Country.objects.all().delete()
            Region.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("  Done."))

        # Ensure regions exist
        regions = {}
        for name, desc in REGION_DESCRIPTIONS.items():
            obj, _ = Region.objects.get_or_create(
                name=name, defaults={"slug": slugify(name), "description": desc})
            regions[name] = obj

        phase = options.get("phase", 0)
        if phase in (0, 1):
            self.phase1_countries(regions)
        if phase in (0, 2):
            self.phase2_extras()

        # Final summary
        c_count = Country.objects.count()
        f_count = FlagCollection.objects.count()
        grand_total = c_count + f_count
        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 50}\n"
            f"  Grand total flags: {grand_total}\n"
            f"    Countries:     {c_count}\n"
            f"    Extra flags:   {f_count}\n"
            f"{'=' * 50}"
        ))
