import os
from django.core.management.base import BaseCommand
from app.models import FlagCollection

class Command(BaseCommand):
    help = 'Safely deletes flags and physical images with a confirmation prompt.'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Delete ALL flags in the database')
        parser.add_argument('--category', type=str, help='Delete flags of a specific category')
        parser.add_argument(
            '--noinput', '--no-input',
            action='store_true',
            help='Skip the confirmation prompt (useful for automated scripts)'
        )

    def handle(self, *args, **options):
        # 1. Bezpečnostní pojistka argumentů
        if not options['all'] and not options['category']:
            self.stdout.write(self.style.ERROR("BEZPEČNOSTNÍ ZÁMEK: Musíš specifikovat, co chceš smazat."))
            self.stdout.write(self.style.WARNING("Použij: python manage.py clean_flags --all"))
            self.stdout.write(self.style.WARNING("Nebo: python manage.py clean_flags --category <nazev>"))
            return

        # 2. Výběr dat podle argumentů
        if options['category']:
            flags = FlagCollection.objects.filter(category=options['category'])
            msg = f"kategorii '{options['category']}'"
        else:
            flags = FlagCollection.objects.all()
            msg = "ÚPLNĚ VŠECHNY vlajky"

        count = flags.count()
        if count == 0:
            self.stdout.write(self.style.WARNING(f"Žádné záznamy pro {msg} nebyly nalezeny. Není co mazat."))
            return

        # 3. Výpis vzorku a varování
        self.stdout.write(self.style.WARNING(f"⚠️ POZOR: Chystáš se smazat {count} záznamů pro {msg}!"))
        self.stdout.write("Zde je vzorek toho, co bude smazáno:")
        
        # Zobrazíme prvních 5 záznamů jako ukázku
        sample_flags = flags[:5]
        for f in sample_flags:
            self.stdout.write(f" - {f.name} (ID: {f.wikidata_id}, Kat: {f.category})")
        
        if count > 5:
            self.stdout.write(f" ... a dalších {count - 5} položek.")

        # 4. Potvrzení (Sanity Check ve stylu y/N)
        if not options['noinput']:
            confirm = input(f"\nOpravdu chceš nenávratně smazat těchto {count} záznamů a jejich obrázky? [y/N]: ")
            if confirm.strip().lower() != 'y':
                self.stdout.write(self.style.ERROR("Operace zrušena uživatelem. Nic nebylo smazáno."))
                return

        # 5. Fyzické mazání souborů
        self.stdout.write("Mažu fyzické soubory z disku...")
        deleted_files = 0
        for flag in flags:
            if flag.image_file and hasattr(flag.image_file, 'path') and os.path.exists(flag.image_file.path):
                try:
                    os.remove(flag.image_file.path)
                    deleted_files += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Chyba při mazání souboru: {e}"))

        # 6. Smazání z databáze
        self.stdout.write("Mažu záznamy z databáze...")
        flags.delete()

        self.stdout.write(self.style.SUCCESS(
            f"✅ Úklid hotov! Smazáno {count} záznamů z databáze a {deleted_files} fyzických obrázků z disku."
        ))