import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand

from app.models import FlagCollection


class Command(BaseCommand):
    help = "Enrich existing flags with population, area, and coordinates from Wikipedia infoboxes."

    LANGUAGE_BY_CCA2 = {
        "CZ": "cs",
        "DE": "de",
        "FR": "fr",
        "GB": "en",
        "US": "en",
        "RU": "ru",
        "SK": "sk",
        "PL": "pl",
        "AT": "de",
        "CH": "de",
        "ES": "es",
        "IT": "it",
        "UA": "uk",
    }

    POPULATION_KEYS = [
        "population",
        "inhabitants",
        "einwohner",
        "obyvatel",
        "obyvatelstvo",
        "population totale",
        "poblacion",
        "popolazione",
        "naselenie",
    ]

    AREA_KEYS = [
        "area",
        "total area",
        "fläche",
        "rozloha",
        "superficie",
        "superficie totale",
        "ploschad",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "JustEnoughFlags-Enricher/1.0 (https://jef.world-quiz.com; contact: info@world-quiz.com)"
            }
        )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of flags to process")
        parser.add_argument("--country", type=str, default="", help="Filter by country CCA2 code")
        parser.add_argument("--only-empty", action="store_true", help="Only process flags missing enrichment fields")
        parser.add_argument("--dry-run", action="store_true", help="Do not save changes")
        parser.add_argument("--verbose", action="store_true", help="Detailed output")

    def _desc_dict(self, flag):
        if isinstance(flag.description, dict):
            return flag.description
        return {}

    def _listify(self, value):
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parts = [p.strip() for p in re.split(r"\|\||\n", value) if p.strip()]
            return parts
        return []

    def _title_candidates(self, flag):
        desc = self._desc_dict(flag)
        candidates = []
        candidates.extend(self._listify(desc.get("native_wiki_titles")))
        candidates.extend(self._listify(desc.get("label_native")))
        candidates.extend(self._listify(desc.get("native_label")))
        candidates.extend(self._listify(desc.get("label_en")))
        candidates.append(flag.name)

        seen = set()
        unique = []
        for item in candidates:
            normalized = item.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
        return unique

    def _lang_candidates(self, flag):
        preferred = []
        if flag.country and flag.country.cca2:
            lang = self.LANGUAGE_BY_CCA2.get(flag.country.cca2.upper())
            if lang:
                preferred.append(lang)

        for lang in ["en", "de", "fr", "cs", "es", "it", "pl", "ru", "uk", "sk"]:
            if lang not in preferred:
                preferred.append(lang)
        return preferred

    def _extract_numeric_value(self, text):
        cleaned = re.sub(r"\[[^\]]*\]", "", text)
        candidates = re.findall(r"\d[\d\s\.,]*", cleaned)
        if not candidates:
            return None

        token = max(candidates, key=len)
        token = token.replace("\u00a0", " ").replace(" ", "")

        if token.count(",") > 0 and token.count(".") > 0:
            if token.rfind(",") > token.rfind("."):
                token = token.replace(".", "").replace(",", ".")
            else:
                token = token.replace(",", "")
        elif token.count(",") == 1 and len(token.split(",")[-1]) <= 2:
            token = token.replace(",", ".")
        else:
            token = token.replace(",", "")

        try:
            return float(token)
        except ValueError:
            return None

    def _extract_infobox_stats(self, soup):
        population = None
        area_km2 = None

        infobox = soup.select_one("table.infobox")
        if not infobox:
            return population, area_km2

        for row in infobox.select("tr"):
            header_cell = row.select_one("th")
            value_cell = row.select_one("td")
            if not header_cell or not value_cell:
                continue

            header = header_cell.get_text(" ", strip=True).lower()
            value_text = value_cell.get_text(" ", strip=True)

            if population is None and any(key in header for key in self.POPULATION_KEYS):
                pop_num = self._extract_numeric_value(value_text)
                if pop_num is not None:
                    population = int(pop_num)

            if area_km2 is None and any(key in header for key in self.AREA_KEYS):
                area_num = self._extract_numeric_value(value_text)
                if area_num is not None:
                    area_km2 = float(area_num)

            if population is not None and area_km2 is not None:
                break

        return population, area_km2

    def _extract_coordinates(self, soup):
        geo = soup.select_one("span.geo")
        if geo:
            text = geo.get_text("", strip=True)
            if ";" in text:
                parts = text.split(";")
                if len(parts) == 2:
                    try:
                        return float(parts[0]), float(parts[1])
                    except ValueError:
                        pass

        lat_node = soup.select_one(".latitude")
        lon_node = soup.select_one(".longitude")
        if lat_node and lon_node:
            lat_text = lat_node.get_text(" ", strip=True)
            lon_text = lon_node.get_text(" ", strip=True)
            lat = self._extract_numeric_value(lat_text)
            lon = self._extract_numeric_value(lon_text)
            if lat is not None and lon is not None:
                return float(lat), float(lon)

        return None, None

    def _build_url(self, lang, title):
        title_for_url = title.replace(" ", "_")
        return f"https://{lang}.wikipedia.org/wiki/{quote(title_for_url)}"

    def _fetch_page(self, url):
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return None
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException:
            return None

    def _fetch_best_infobox(self, flag, verbose):
        titles = self._title_candidates(flag)
        langs = self._lang_candidates(flag)

        for lang in langs:
            for title in titles:
                url = self._build_url(lang, title)
                soup = self._fetch_page(url)
                time.sleep(1)
                if not soup:
                    continue

                population, area_km2 = self._extract_infobox_stats(soup)
                latitude, longitude = self._extract_coordinates(soup)

                if population is None and area_km2 is None and latitude is None and longitude is None:
                    continue

                if verbose:
                    self.stdout.write(f"[FOUND] {flag.name} -> {url}")

                return {
                    "population": population,
                    "area_km2": area_km2,
                    "latitude": latitude,
                    "longitude": longitude,
                    "source_url": url,
                }

        return None

    def handle(self, *args, **options):
        verbose = options["verbose"]
        dry_run = options["dry_run"]
        limit = max(0, int(options["limit"]))

        queryset = FlagCollection.objects.select_related("country").all()

        if options["country"]:
            queryset = queryset.filter(country__cca2=options["country"].upper())

        if options["only_empty"]:
            queryset = queryset.filter(
                population__isnull=True,
                area_km2__isnull=True,
                latitude__isnull=True,
                longitude__isnull=True,
            )

        queryset = queryset.order_by("id")
        if limit:
            queryset = queryset[:limit]

        processed = 0
        updated = 0
        failed = 0

        for flag in queryset:
            processed += 1
            try:
                enriched = self._fetch_best_infobox(flag, verbose=verbose)
                if not enriched:
                    if verbose:
                        self.stdout.write(self.style.WARNING(f"[SKIPPED] No infobox data for {flag.name}"))
                    continue

                changed_fields = []
                for field in ("population", "area_km2", "latitude", "longitude"):
                    new_value = enriched.get(field)
                    if new_value is not None and getattr(flag, field) != new_value:
                        setattr(flag, field, new_value)
                        changed_fields.append(field)

                if changed_fields:
                    if not dry_run:
                        flag.save(update_fields=changed_fields)
                    updated += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f"[UPDATED] {flag.name} ({', '.join(changed_fields)})"))
                elif verbose:
                    self.stdout.write(f"[UNCHANGED] {flag.name}")

            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.WARNING(f"[ERROR] {flag.name}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Enrichment finished. Processed: {processed}, Updated: {updated}, Failed: {failed}, Dry run: {dry_run}"
            )
        )
