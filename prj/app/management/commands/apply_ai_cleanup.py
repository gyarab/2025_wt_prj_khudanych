from django.core.management.base import BaseCommand
from app.models import FlagCollection
import json
from pathlib import Path

class Command(BaseCommand):
    help = 'Aplikuje rozhodnutí z action_map.json do databáze.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Pouze vypíše, co by se stalo, ale nic neuloží.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # 1. Načtení JSON slovníku
        map_path = Path('action_map.json')
        if not map_path.exists():
            self.stdout.write(self.style.ERROR("Soubor action_map.json nebyl nalezen!"))
            return

        with open(map_path, 'r', encoding='utf-8') as f:
            action_map = json.load(f)

        self.stdout.write(f"Načteno {len(action_map)} instrukcí z JSON mapy.")

        # 2. Aplikace změn
        stats = {'hidden': 0, 'recategorized': 0, 'marked_ambiguous': 0}

        for qid, payload in action_map.items():
            actions = payload.get("actions", {})
            if not actions:
                continue

            try:
                flag = FlagCollection.objects.get(wikidata_id=qid)
                changed = False

                if 'is_public' in actions and actions['is_public'] is False:
                    flag.is_public = False
                    stats['hidden'] += 1
                    changed = True
                    self.stdout.write(self.style.WARNING(f"[SKRÝT] {flag.name} (Důvod: {payload.get('reasons')})"))

                if 'category' in actions and flag.category != actions['category']:
                    old_cat = flag.category
                    flag.category = actions['category']
                    stats['recategorized'] += 1
                    changed = True
                    self.stdout.write(self.style.SUCCESS(f"[KATEGORIE] {flag.name}: {old_cat} -> {actions['category']}"))

                if 'is_verified' in actions and actions['is_verified'] is False:
                    # Nechceme měnit public status, jen to označit pro tebe do Admina
                    flag.is_verified = False
                    stats['marked_ambiguous'] += 1
                    changed = True
                    # Vypisovat nebudeme, ať nespamujeme konzoli (těch je hodně)

                if changed and not dry_run:
                    flag.save()

            except FlagCollection.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Chyba: QID {qid} ({payload.get('name')}) nenalezeno v DB."))

        # 3. Výpis výsledků
        self.stdout.write(self.style.SUCCESS(f"\n--- HOTOVO ---"))
        if dry_run:
            self.stdout.write(self.style.WARNING("TOTO BYL POUZE DRY-RUN. Nic nebylo uloženo."))
        self.stdout.write(f"Skryto: {stats['hidden']}")
        self.stdout.write(f"Přeřazeno: {stats['recategorized']}")
        self.stdout.write(f"Označeno k ruční kontrole (ambiguous): {stats['marked_ambiguous']}")