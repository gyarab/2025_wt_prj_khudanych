import time
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from app.models import Country, FlagCollection

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
REQUEST_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "JustEnoughFlags/etl-fetch-wikidata-flags (student project)",
}

CATEGORY_TYPE_ROOTS = {
    "state": ["Q35657", "Q107390"],
    "city": ["Q515"],
    "territory": ["Q46395", "Q3624078"],
    "historical": ["Q3024240", "Q28171280", "Q1790360"],
    "international": ["Q484652", "Q7210356", "Q1065"],
}


def _wikidata_id_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1] if uri else ""


def _binding_value(row: dict, key: str) -> str:
    return row.get(key, {}).get("value", "")


def _parse_float(value: str) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_int(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_wkt_point(point_literal: str) -> Tuple[Optional[float], Optional[float]]:
    """Parse WKT point in format Point(long lat)."""
    if not point_literal or not point_literal.startswith("Point(") or not point_literal.endswith(")"):
        return None, None

    payload = point_literal[len("Point("):-1].strip()
    parts = payload.split()
    if len(parts) != 2:
        return None, None

    lon = _parse_float(parts[0])
    lat = _parse_float(parts[1])
    return lat, lon


def _to_flag_image_url(flag_file_url: str) -> str:
    if not flag_file_url:
        return ""

    filename = flag_file_url.rsplit("/", 1)[-1]
    if filename:
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{filename}?width=640"
    return flag_file_url


def _build_query(root_qids: Iterable[str], limit: int) -> str:
    values = " ".join(f"wd:{qid}" for qid in root_qids)
    return f"""
SELECT DISTINCT ?item ?itemLabel ?flag ?population ?area ?coord ?countryIso3 ?typeLabel
WHERE {{
  VALUES ?rootType {{ {values} }}
  ?item wdt:P31/wdt:P279* ?rootType ;
        wdt:P41 ?flag .

  OPTIONAL {{ ?item wdt:P1082 ?population . }}
  OPTIONAL {{ ?item wdt:P2046 ?area . }}
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
  OPTIONAL {{
    ?item wdt:P17 ?country .
    ?country wdt:P298 ?countryIso3 .
  }}
  OPTIONAL {{
    ?item wdt:P31 ?itemType .
    ?itemType rdfs:label ?typeLabel .
    FILTER(LANG(?typeLabel) = "en")
  }}

  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT {int(limit)}
"""


def _run_sparql(query: str, retries: int = 4) -> List[dict]:
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=REQUEST_HEADERS,
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("results", {}).get("bindings", [])
        except requests.RequestException as exc:
            last_error = exc
            wait_seconds = 3 * attempt
            time.sleep(wait_seconds)

    raise CommandError(f"SPARQL request failed after {retries} attempts: {last_error}")


class Command(BaseCommand):
    help = "Fetch and upsert Wikidata flags for state/city/territory/historical/international categories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit-per-category",
            type=int,
            default=30000,
            help="Max SPARQL rows fetched per category",
        )
        parser.add_argument(
            "--categories",
            nargs="+",
            choices=sorted(CATEGORY_TYPE_ROOTS.keys()),
            default=sorted(CATEGORY_TYPE_ROOTS.keys()),
            help="Subset of categories to fetch",
        )

    def handle(self, *args, **options):
        selected_categories = options["categories"]
        limit_per_category = options["limit_per_category"]

        if limit_per_category <= 0:
            raise CommandError("--limit-per-category must be > 0")

        totals: Dict[str, Dict[str, int]] = {
            category: {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}
            for category in selected_categories
        }

        for category in selected_categories:
            roots = CATEGORY_TYPE_ROOTS[category]
            query = _build_query(roots, limit_per_category)
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== Fetching {category} flags ==="))

            try:
                rows = _run_sparql(query)
            except CommandError as exc:
                self.stderr.write(self.style.ERROR(str(exc)))
                continue

            totals[category]["fetched"] = len(rows)
            self.stdout.write(f"Fetched {len(rows)} rows for category '{category}'.")

            for row in rows:
                try:
                    item_uri = _binding_value(row, "item")
                    wikidata_id = _wikidata_id_from_uri(item_uri)
                    if not wikidata_id:
                        totals[category]["skipped"] += 1
                        continue

                    name = _binding_value(row, "itemLabel") or wikidata_id
                    flag_file = _binding_value(row, "flag")
                    flag_image = _to_flag_image_url(flag_file)
                    if not flag_image:
                        totals[category]["skipped"] += 1
                        continue

                    population = _parse_int(_binding_value(row, "population"))
                    area_km2 = _parse_float(_binding_value(row, "area"))
                    latitude, longitude = _parse_wkt_point(_binding_value(row, "coord"))
                    type_label = _binding_value(row, "typeLabel")

                    country_iso3 = _binding_value(row, "countryIso3").upper()
                    linked_country = None
                    if country_iso3:
                        linked_country = Country.objects.filter(cca3=country_iso3).first()

                    defaults = {
                        "name": name,
                        "category": category,
                        "flag_image": flag_image,
                        "population": population,
                        "area_km2": area_km2,
                        "latitude": latitude,
                        "longitude": longitude,
                        "country": linked_country,
                        "is_public": True,
                    }

                    if type_label:
                        defaults["description"] = {"wikidata_type": type_label}

                    with transaction.atomic():
                        obj, created = FlagCollection.objects.update_or_create(
                            wikidata_id=wikidata_id,
                            defaults=defaults,
                        )

                    if created:
                        totals[category]["created"] += 1
                    else:
                        totals[category]["updated"] += 1

                except Exception as exc:  # noqa: BLE001 - keep row-level ETL resilient
                    totals[category]["skipped"] += 1
                    self.stderr.write(self.style.WARNING(f"Skip row in {category}: {exc}"))

        self.stdout.write(self.style.SUCCESS("\nETL finished."))
        for category in selected_categories:
            stats = totals[category]
            self.stdout.write(
                f"{category}: fetched={stats['fetched']} created={stats['created']} "
                f"updated={stats['updated']} skipped={stats['skipped']}"
            )