from django.core.management.base import BaseCommand
from app.models import FlagCollection, Country

class Command(BaseCommand):
    help = 'Synchronizuje population a area z FlagCollection do tabulky Country.'

    def handle(self, *args, **options):
        self.stdout.write("🔄 Startuji synchronizaci dat...")
        
        # Najdeme všechny vlajky, které jsou už ověřené a jsou to země
        verified_flags = FlagCollection.objects.filter(is_verified=True, category='country')
        count = 0

        for flag in verified_flags:
            if flag.country: # Pokud má vlajka vazbu na tabulku Country
                country = flag.country
                
                # Zkopírujeme data, pokud v tabulce Country chybí (jsou 0)
                updated = False
                if country.population == 0 and flag.population:
                    country.population = flag.population
                    updated = True
                
                if (country.area_km2 == 0 or country.area_km2 is None) and flag.area_km2:
                    country.area_km2 = flag.area_km2
                    updated = True
                
                if updated:
                    country.save()
                    count += 1
                    self.stdout.write(f" ✅ Aktualizována země: {country.name_common} (Pop: {country.population})")

        self.stdout.write(self.style.SUCCESS(f"🏁 Hotovo! Synchronizováno {count} zemí. Teď už by se měly na webu zobrazit."))