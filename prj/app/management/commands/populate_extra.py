"""
Management command: populate_extra
-----------------------------------
Populates FlagCollection with historical, international, and territory flags
that were missed by the main populate_wikidata command.

Uses many small, focused SPARQL queries to avoid Wikidata timeouts.

Usage:
    python manage.py populate_extra              # run all categories
    python manage.py populate_extra --category historical
    python manage.py populate_extra --category international
    python manage.py populate_extra --category territory
"""

import time
import requests
from django.core.management.base import BaseCommand
from app.models import Country, FlagCollection


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "JustEnoughFlags/2.1 (educational project; https://github.com)",
}


def run_sparql(query, retries=3, timeout=90):
    for attempt in range(retries):
        try:
            r = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=HEADERS,
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["results"]["bindings"]
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"  Rate-limited – waiting {wait}s …")
                time.sleep(wait)
            elif exc.response is not None and exc.response.status_code == 504:
                print(f"  Timeout (504) – attempt {attempt + 1}/{retries}")
                time.sleep(5 * (attempt + 1))
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


def val(row, key):
    return row.get(key, {}).get("value", "")


def qid(uri):
    return uri.rsplit("/", 1)[-1] if uri else ""


def commons_thumb(svg_url, width=320):
    if not svg_url:
        return ""
    filename = svg_url.split("/")[-1]
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width={width}"


# ═══════════════════════════════════════════════════════════════════════════
# SPARQL QUERIES — small & focused to avoid Wikidata timeouts
# ═══════════════════════════════════════════════════════════════════════════

# ─── HISTORICAL ───────────────────────────────────────────────────────────
# Multiple queries targeting different Wikidata classes for historical entities

HISTORICAL_QUERIES = [
    # 1. Historical countries (Q3024240) — broad, includes many former states
    (
        "Historical countries (Q3024240)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q3024240 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 500
        """,
    ),
    # 2. Former countries (Q1790360)
    (
        "Former countries (Q1790360)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q1790360 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 3. Former sovereign states — dissolved (have P576 = dissolved date)
    (
        "Dissolved sovereign states",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q3624078 .
          ?item wdt:P576 ?dissolved .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 4. Colonies (Q133156)
    (
        "Colonies (Q133156)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q133156 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 5. Former administrative territorial entities (Q28171280)
    (
        "Former admin territories",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q28171280 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 6. Ancient civilizations / historical states (Q839954)
    (
        "Ancient civilizations / city-states",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q839954 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 7. Former polities (Q15642541 = historical administrative division)
    (
        "Historical admin divisions",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q15642541 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 8. Historical empires/kingdoms by P576 (dissolution date) + flag
    (
        "Entities with dissolution date + flag",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P576 ?dissolved .
          ?item wdt:P41 ?flag .
          FILTER(YEAR(?dissolved) < 2000)
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 500
        """,
    ),
    # 9. Client states / puppet states (Q1451600)
    (
        "Client states (Q1451600)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q1451600 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 10. Mandate territories (Q205895)
    (
        "Mandates/protectorates",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?type { wd:Q205895 wd:Q164142 }
          ?item wdt:P31 ?type .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 11. Directly request specific famous historical entities
    (
        "Famous historical entities (direct QIDs)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?item {
            wd:Q7318    # Nazi Germany
            wd:Q15180   # Soviet Union
            wd:Q12544   # Byzantine Empire
            wd:Q12560   # Ottoman Empire
            wd:Q45670   # Kingdom of Prussia
            wd:Q83286   # Kingdom of Yugoslavia
            wd:Q43287   # German Empire
            wd:Q172107  # Kingdom of Italy
            wd:Q153136  # Austro-Hungarian Empire
            wd:Q174306  # Kingdom of Hungary
            wd:Q41304   # Confederation of the Rhine
            wd:Q155059  # Czechoslovakia
            wd:Q36704   # Yugoslavia
            wd:Q170541  # Kingdom of Romania
            wd:Q159683  # Kingdom of Poland
            wd:Q2184    # Russian SFSR
            wd:Q170072  # Ukrainian SSR
            wd:Q180573  # Byelorussian SSR
            wd:Q11198   # Confederate States of America
            wd:Q30059   # East Germany (GDR)
            wd:Q713750  # West Germany (FRG)
            wd:Q34266   # Russian Empire
            wd:Q83164   # Spanish Empire
            wd:Q172579  # Portuguese Empire
            wd:Q8675    # British Empire
            wd:Q131964  # Austrian Empire
            wd:Q154741  # Weimar Republic
            wd:Q9903    # Ming Dynasty
            wd:Q8733    # Qing Dynasty
            wd:Q148540  # Mughal Empire
            wd:Q12536   # Mongol Empire
            wd:Q12564   # Holy Roman Empire
            wd:Q148    # People's Republic of China (excluded - it's current!)
            wd:Q178038  # Republic of China (1912-1949)
            wd:Q170587  # Republic of Vietnam (South Vietnam)
            wd:Q172640  # North Vietnam
            wd:Q26678   # North Korea? No, it's current — skip
            wd:Q192     # South Korea? Current — skip
            wd:Q83860   # Zulu Kingdom
            wd:Q199442  # Abbasid Caliphate
            wd:Q12490   # Roman Empire
            wd:Q3400    # Republic of Venice
            wd:Q193714  # Papal States
            wd:Q48984   # Kingdom of Sardinia
            wd:Q42585   # Kingdom of the Two Sicilies
            wd:Q107862  # Kingdom of Bohemia
            wd:Q4948    # Republic of Florence
            wd:Q170072  # Ukrainian SSR
            wd:Q170467  # Georgian SSR
            wd:Q170460  # Uzbek SSR
            wd:Q170478  # Kazakh SSR
            wd:Q170895  # Azerbaijan SSR
            wd:Q169652  # Lithuanian SSR
            wd:Q170208  # Moldavian SSR
            wd:Q170154  # Latvian SSR
            wd:Q170264  # Estonian SSR
            wd:Q170443  # Tajik SSR
            wd:Q170350  # Armenian SSR
            wd:Q170236  # Turkmen SSR
            wd:Q170318  # Kirghiz SSR
            wd:Q713750  # West Germany
            wd:Q116750  # Kingdom of Bavaria
            wd:Q152750  # Kingdom of Saxony
            wd:Q153015  # Kingdom of Hanover
            wd:Q83286   # Kingdom of Yugoslavia
            wd:Q330672  # Second Spanish Republic
            wd:Q133346  # Kingdom of Greece
            wd:Q33946   # Czechoslovakia (alternative id)
            wd:Q1054923 # Manchukuo
            wd:Q859563  # Empire of Japan
            wd:Q129053  # French Indochina
            wd:Q399      # Armenia
            wd:Q174193  # United Kingdom of GB & Ireland
            wd:Q174306  # Kingdom of Hungary
          }
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        """,
    ),
]


# ─── INTERNATIONAL / ORGANIZATIONS ───────────────────────────────────────

INTERNATIONAL_QUERIES = [
    # 1. International organizations (Q484652) — broad class
    (
        "International organizations (Q484652)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q484652 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 400
        """,
    ),
    # 2. Supranational organisations (Q1335818)
    (
        "Supranational organisations (Q1335818)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q1335818 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 3. Intergovernmental organisations (Q245065)
    (
        "Intergovernmental organisations (Q245065)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q245065 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 4. Military alliances (Q1127126) — NATO etc.
    (
        "Military alliances (Q1127126)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q1127126 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """,
    ),
    # 5. Trade blocs (Q7781198)
    (
        "Trade blocs (Q7781198)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q7781198 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """,
    ),
    # 6. International sports federations, Olympic committees, etc. with flags
    (
        "Sports organizations with flags",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?type { wd:Q270028 wd:Q1194970 wd:Q4438121 }
          ?item wdt:P31 ?type .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 7. Direct famous international org QIDs
    (
        "Famous international orgs (direct QIDs)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?item {
            wd:Q1065    # United Nations
            wd:Q458     # European Union
            wd:Q7184    # NATO
            wd:Q7825    # African Union
            wd:Q7768    # ASEAN
            wd:Q8908    # OPEC
            wd:Q17495   # Arab League
            wd:Q7785    # Commonwealth of Nations
            wd:Q47764   # Red Cross / ICRC
            wd:Q41550   # UNESCO
            wd:Q7795    # WHO
            wd:Q1969730 # CERN (European Organization for Nuclear Research)
            wd:Q134102  # Interpol
            wd:Q1065    # United Nations
            wd:Q340195  # OSCE
            wd:Q81299   # EFTA
            wd:Q170481  # COMECON
            wd:Q191384  # CIS (Commonwealth of Independent States)
            wd:Q7809    # WTO
            wd:Q8350    # OECD
            wd:Q7825    # African Union
            wd:Q33946   # BRICS? No this is Czecho...
            wd:Q899770  # Pacific Islands Forum
            wd:Q1779504 # CARICOM
            wd:Q189946  # Mercosur
            wd:Q156884  # Benelux
            wd:Q8680    # ESA
            wd:Q7184    # NATO
            wd:Q7159     # IOC
            wd:Q40857    # FIFA
            wd:Q131535   # World Scout Movement
            wd:Q7804     # NAFTA? May not have flag
            wd:Q193376   # Organization of American States
            wd:Q129286   # Nordic Council
            wd:Q47543    # Franc Zone? 
            wd:Q975405   # GUAM
            wd:Q1137381  # Shanghai Cooperation Organisation
            wd:Q389867   # Visegrad Group
            wd:Q28222    # European Space Agency
            wd:Q742023   # Eurasian Economic Union
            wd:Q1191332  # Organisation of Islamic Cooperation
            wd:Q9072     # International Red Cross
            wd:Q37470    # International Olympic Committee
            wd:Q170481   # COMECON
            wd:Q178122   # SEATO
            wd:Q15042    # Warsaw Pact
            wd:Q15042    # Warsaw Pact
            wd:Q25277    # League of Nations
            wd:Q487907   # Pacific Community
            wd:Q45546    # G8 / G7
            wd:Q28231    # Council of Europe
          }
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        """,
    ),
]


# ─── TERRITORIES ──────────────────────────────────────────────────────────

TERRITORY_QUERIES = [
    # 1. Dependent territories (Q161243)
    (
        "Dependent territories (Q161243)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q161243 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 2. Overseas territory (Q783733)
    (
        "Overseas territories (Q783733)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q783733 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 3. Unincorporated territory (Q1763527)
    (
        "Unincorporated territories (Q1763527)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q1763527 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 4. Crown Dependencies (Q185086)
    (
        "Crown dependencies (Q185086)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q185086 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 50
        """,
    ),
    # 5. Autonomous territories / autonomous regions (various classes)
    (
        "Autonomous territories",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?type { wd:Q1048835 wd:Q15916867 wd:Q1187015 wd:Q327333 }
          ?item wdt:P31 ?type .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 300
        """,
    ),
    # 6. Special administrative regions (Q779415)
    (
        "Special administrative regions",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          ?item wdt:P31 wd:Q779415 .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 100
        """,
    ),
    # 7. Disputed territories (Q15239622)
    (
        "Disputed territories",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?type { wd:Q15239622 wd:Q13107770 }
          ?item wdt:P31 ?type .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 8. British Overseas Territories (Q46395) + French overseas territories
    (
        "British & French overseas territories",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?type { wd:Q46395 wd:Q719487 wd:Q202216 }
          ?item wdt:P31 ?type .
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        LIMIT 200
        """,
    ),
    # 9. Direct QIDs for well-known territories
    (
        "Famous territories (direct QIDs)",
        """
        SELECT ?item ?itemLabel ?flag WHERE {
          VALUES ?item {
            wd:Q5765     # Puerto Rico
            wd:Q16641    # Guam
            wd:Q11703    # US Virgin Islands
            wd:Q26988    # American Samoa
            wd:Q16644    # Northern Mariana Islands
            wd:Q36823    # Turks & Caicos
            wd:Q25228    # Bermuda
            wd:Q35555    # Cayman Islands
            wd:Q25230    # British Virgin Islands
            wd:Q13353    # Anguilla
            wd:Q25305    # Montserrat
            wd:Q29999    # Gibraltar
            wd:Q23681    # Falkland Islands
            wd:Q35672    # Pitcairn Islands
            wd:Q46197    # St Helena
            wd:Q23635    # South Georgia
            wd:Q13218    # Åland Islands
            wd:Q25279    # Curaçao
            wd:Q26273    # Aruba
            wd:Q26180    # Sint Maarten
            wd:Q25396    # Bonaire
            wd:Q17012    # Faroe Islands
            wd:Q223      # Greenland
            wd:Q17054    # New Caledonia
            wd:Q30971    # French Polynesia
            wd:Q17070    # Wallis and Futuna
            wd:Q3769     # French Guiana
            wd:Q17054    # New Caledonia
            wd:Q126125   # Réunion
            wd:Q17063    # Mayotte
            wd:Q25362    # Guadeloupe
            wd:Q17054    # Martinique wrong, fix below
            wd:Q17349    # Cook Islands
            wd:Q34020    # Niue
            wd:Q34754    # Tokelau
            wd:Q35580    # Norfolk Island
            wd:Q18221    # Christmas Island
            wd:Q36004    # Cocos (Keeling) Islands
            wd:Q3311985  # Ashmore and Cartier Islands
            wd:Q131198   # Hong Kong
            wd:Q14773    # Macau
            wd:Q34366    # Taiwan (Republic of China)
            wd:Q1246     # Kosovo
            wd:Q219      # Western Sahara (disputed)
            wd:Q25279    # Curaçao
            wd:Q23427    # Svalbard
            wd:Q31057    # Jan Mayen
            wd:Q2280    # Isle of Man
            wd:Q25230    # BVI
            wd:Q3311     # Jersey
            wd:Q3405     # Guernsey
            wd:Q9676     # Isle of Man
          }
          ?item wdt:P41 ?flag .
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        }
        """,
    ),
]


class Command(BaseCommand):
    help = "Populate historical, international, and territory flags from Wikidata"

    def add_arguments(self, parser):
        parser.add_argument(
            "--category", type=str, default="all",
            choices=["all", "historical", "international", "territory"],
            help="Which category to populate (default: all)",
        )

    def save_flag(self, name, flag_url, category, wikidata_id, seen):
        """Save one FlagCollection row. Returns True if new row created."""
        if not name or not flag_url:
            return False
        # Skip QID-only labels (unresolved labels)
        if name.startswith("Q") and name[1:].isdigit():
            return False
        dedup_key = wikidata_id or name
        if dedup_key in seen:
            return False
        seen.add(dedup_key)

        # Check if this is already a Country in our DB (skip duplicates)
        if Country.objects.filter(name_common__iexact=name).exists():
            return False

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
                    "flag_image": image_url,
                },
            )
        else:
            _, created = FlagCollection.objects.get_or_create(
                name=name[:200], category=category,
                defaults={
                    "flag_image": image_url,
                    "wikidata_id": "",
                },
            )
        return created

    def run_category(self, category, queries, seen):
        """Run all SPARQL queries for a given category."""
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'=' * 60}\n  Category: {category.upper()}\n{'=' * 60}"
        ))
        cat_created = 0
        cat_updated = 0

        for label, query in queries:
            self.stdout.write(f"  [{label}] ...")
            try:
                rows = run_sparql(query)
                created = 0
                for row in rows:
                    wid = qid(val(row, "item"))
                    name = val(row, "itemLabel").strip()
                    flag = val(row, "flag")
                    if self.save_flag(name, flag, category, wid, seen):
                        created += 1
                cat_created += created
                self.stdout.write(
                    self.style.SUCCESS(f"    -> {len(rows)} results, {created} new flags")
                )
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f"    -> FAILED: {exc}")
                )
            # Be polite to Wikidata
            time.sleep(3)

        count = FlagCollection.objects.filter(category=category).count()
        self.stdout.write(self.style.SUCCESS(
            f"\n  {category}: {cat_created} new — total in DB: {count}"
        ))
        return cat_created

    def handle(self, *args, **options):
        category = options["category"]

        # Load existing wikidata_ids to deduplicate across queries
        existing_ids = set(
            FlagCollection.objects.exclude(wikidata_id="")
            .values_list("wikidata_id", flat=True)
        )
        seen = set(existing_ids)
        total = 0

        if category in ("all", "historical"):
            total += self.run_category("historical", HISTORICAL_QUERIES, seen)

        if category in ("all", "international"):
            total += self.run_category("international", INTERNATIONAL_QUERIES, seen)

        if category in ("all", "territory"):
            total += self.run_category("territory", TERRITORY_QUERIES, seen)

        # ── Dedup / cleanup step ──
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Deduplication & cleanup ..."))
        self._cleanup()

        # Final summary
        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 60}\n"
            f"  DONE — {total} new flags added\n"
            f"  Historical:    {FlagCollection.objects.filter(category='historical').count()}\n"
            f"  International: {FlagCollection.objects.filter(category='international').count()}\n"
            f"  Territory:     {FlagCollection.objects.filter(category='territory').count()}\n"
            f"  Total DB:      {FlagCollection.objects.count()} + "
            f"{Country.objects.count()} countries\n"
            f"{'=' * 60}"
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Cleanup: remove duplicate-image entries and noise (sports teams etc.)
    # ─────────────────────────────────────────────────────────────────────
    def _cleanup(self):
        from django.db.models import Count as C, Q

        removed = 0

        # 1. Remove entries whose flag_image matches a Country.flag_png
        country_pngs = set(
            Country.objects.exclude(flag_png="").values_list("flag_png", flat=True)
        )
        qs = FlagCollection.objects.filter(flag_image__in=country_pngs)
        n = qs.count()
        if n:
            qs.delete()
            removed += n
            self.stdout.write(f"    Removed {n} entries duplicating Country flags")

        # 2. Remove sports teams / noise entries
        NOISE = [
            "football team", "basketball team", "handball team",
            "volleyball team", "hockey team", "rugby team",
            "cricket team", "baseball team", "olympic", "paralympic",
            "under-17", "under-18", "under-19", "under-20", "under-21",
            "under-23", "women's national", "men's national",
            "national team", "at the 20", "at the 19", "grand prix",
            "marine corps", "coast guard", "national guard",
        ]
        q = Q()
        for p in NOISE:
            q |= Q(name__icontains=p)
        qs = FlagCollection.objects.filter(q)
        n = qs.count()
        if n:
            qs.delete()
            removed += n
            self.stdout.write(f"    Removed {n} sports/noise entries")

        # 3. Deduplicate same flag_image — keep best name per image
        dupes = (
            FlagCollection.objects
            .values("flag_image")
            .annotate(cnt=C("id"))
            .filter(cnt__gt=1)
        )
        for group in dupes:
            entries = list(
                FlagCollection.objects.filter(flag_image=group["flag_image"])
            )
            entries.sort(key=lambda e: len(e.name))  # keep shortest name
            ids_to_remove = [e.id for e in entries[1:]]
            FlagCollection.objects.filter(id__in=ids_to_remove).delete()
            removed += len(ids_to_remove)

        if removed:
            self.stdout.write(
                self.style.SUCCESS(f"    Total cleaned: {removed} duplicate/noise entries")
            )
