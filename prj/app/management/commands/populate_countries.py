"""
Management command to populate the database with ALL 250 countries.
Uses local JSON data from mledoze/countries (GitHub) + flagcdn.com for flag URLs.
"""

import json
import os
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from app.models import Region, Country, FlagCollection


# Region descriptions for nicer display
REGION_DESCRIPTIONS = {
    'Africa': 'The second-largest and second-most populous continent, home to 54 countries.',
    'Americas': 'Comprising North America, Central America, South America and the Caribbean.',
    'Antarctic': 'The southernmost continent, surrounding the South Pole.',
    'Asia': 'The largest and most populous continent, spanning from the Middle East to the Pacific.',
    'Europe': 'The second-smallest continent, known for its rich history and cultural diversity.',
    'Oceania': 'A geographic region including Australasia, Melanesia, Micronesia and Polynesia.',
}


class Command(BaseCommand):
    help = 'Populate the database with ALL 250 countries from local JSON data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            FlagCollection.objects.all().delete()
            Country.objects.all().delete()
            Region.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Data cleared'))

        # Load local JSON data (downloaded from mledoze/countries on GitHub)
        data_file = Path(__file__).resolve().parent.parent.parent / 'data' / 'countries.json'
        if not data_file.exists():
            raise CommandError(
                f'Country data file not found at {data_file}.\n'
                'Run: python -c "import requests,json,os; '
                "os.makedirs('app/data',exist_ok=True); "
                "r=requests.get('https://raw.githubusercontent.com/mledoze/countries/master/countries.json'); "
                "json.dump(r.json(), open('app/data/countries.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)\""
            )

        with open(data_file, 'r', encoding='utf-8') as f:
            countries_data = json.load(f)

        self.stdout.write(self.style.SUCCESS(f'Loaded {len(countries_data)} countries from local data'))

        try:
            # ── Create regions ───────────────────────────────────────
            regions = {}
            for name, desc in REGION_DESCRIPTIONS.items():
                slug = name.lower()
                region, _ = Region.objects.get_or_create(
                    name=name,
                    defaults={'slug': slug, 'description': desc},
                )
                regions[name] = region

            self.stdout.write(self.style.SUCCESS(f'Regions ready ({len(regions)})'))

            # ── Process countries ────────────────────────────────────
            created_count = 0
            updated_count = 0

            for i, entry in enumerate(countries_data, 1):
                try:
                    name_data = entry.get('name', {})
                    name_common = name_data.get('common', 'Unknown')
                    name_official = name_data.get('official', name_common)

                    cca2 = entry.get('cca2', '')
                    cca3 = entry.get('cca3', '')
                    if not cca2 or not cca3:
                        continue

                    # Capital
                    capitals = entry.get('capital', [])
                    capital = capitals[0] if capitals and isinstance(capitals, list) else ''

                    # Region  (use the 'region' field from data)
                    region_name = entry.get('region', '')
                    region = regions.get(region_name)

                    subregion = entry.get('subregion', '') or ''

                    # Coordinates
                    latlng = entry.get('latlng', [])
                    latitude = latlng[0] if latlng else None
                    longitude = latlng[1] if len(latlng) > 1 else None

                    # Area
                    area = entry.get('area')

                    # Flags  (build from flagcdn.com using cca2)
                    cca2_lower = cca2.lower()
                    flag_svg = f'https://flagcdn.com/{cca2_lower}.svg'
                    flag_png = f'https://flagcdn.com/w320/{cca2_lower}.png'
                    flag_emoji = entry.get('flag', '')

                    # Currencies & languages
                    currencies = entry.get('currencies', {}) or {}
                    languages = entry.get('languages', {}) or {}

                    # Borders
                    borders = entry.get('borders', []) or []

                    # Political
                    independent = entry.get('independent', True)
                    if independent is None:
                        independent = False
                    un_member = entry.get('unMember', False)

                    # Continents  (derive from region)
                    continents = [region_name] if region_name else []

                    # Create or update
                    country, created = Country.objects.update_or_create(
                        cca3=cca3,
                        defaults={
                            'name_common': name_common,
                            'name_official': name_official,
                            'cca2': cca2,
                            'capital': capital,
                            'region': region,
                            'subregion': subregion,
                            'population': 0,   # dataset has no population
                            'area': area,
                            'latitude': latitude,
                            'longitude': longitude,
                            'flag_svg': flag_svg,
                            'flag_png': flag_png,
                            'flag_emoji': flag_emoji,
                            'coat_of_arms_svg': '',
                            'coat_of_arms_png': '',
                            'currencies': currencies,
                            'languages': languages,
                            'timezones': [],
                            'continents': continents,
                            'borders': borders,
                            'independent': independent,
                            'un_member': un_member,
                        }
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

                    if i % 50 == 0:
                        self.stdout.write(f'  … {i}/{len(countries_data)}')

                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'Error processing {entry.get("name", {}).get("common", "?")}: {e}'
                    ))

            self.stdout.write(self.style.SUCCESS(
                f'\nDone!  Created: {created_count}  |  Updated: {updated_count}  '
                f'|  Total in DB: {Country.objects.count()}'
            ))

        except Exception as e:
            raise CommandError(f'Error populating database: {e}')
