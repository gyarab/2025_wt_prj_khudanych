import time
from django.core.management.base import BaseCommand
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = 'Backfill normalized search_name values for Country and FlagCollection records with telemetry.'

    def handle(self, *args, **options):
        # --- ZEMĚ (COUNTRIES) ---
        total_countries = Country.objects.count()
        self.stdout.write(self.style.NOTICE(f"🚀 Spouštím backfill pro {total_countries} zemí..."))
        
        country_count = 0
        start_time_c = time.time()
        
        for country in Country.objects.all().iterator(chunk_size=500):
            country.save()
            country_count += 1
            
            # Vykreslení telemetrie každých 10 záznamů nebo na konci
            if country_count % 10 == 0 or country_count == total_countries:
                percent = (country_count / total_countries) * 100 if total_countries > 0 else 100
                elapsed = time.time() - start_time_c
                speed = country_count / elapsed if elapsed > 0 else 0
                
                # \r zajistí, že se text nepřidává na nový řádek, ale přepisuje ten stávající
                self.stdout.write(f"\r   🔄 Průběh: {country_count}/{total_countries} ({percent:.1f}%) | Rychlost: {speed:.1f} it/s", ending="")
                self.stdout.flush()
                
        self.stdout.write(self.style.SUCCESS(f"\n✅ Země hotovy ({country_count} záznamů).\n"))

        # --- VLAJKY (FLAG COLLECTIONS) ---
        total_flags = FlagCollection.objects.count()
        self.stdout.write(self.style.NOTICE(f"🚀 Spouštím backfill pro {total_flags} vlajek..."))
        
        flag_count = 0
        start_time_f = time.time()
        
        for flag in FlagCollection.objects.all().iterator(chunk_size=500):
            flag.save()
            flag_count += 1
            
            # Vykreslení telemetrie každých 50 záznamů nebo na konci (aby to neblikalo příliš rychle)
            if flag_count % 50 == 0 or flag_count == total_flags:
                percent = (flag_count / total_flags) * 100 if total_flags > 0 else 100
                elapsed = time.time() - start_time_f
                speed = flag_count / elapsed if elapsed > 0 else 0
                
                self.stdout.write(f"\r   🔄 Průběh: {flag_count}/{total_flags} ({percent:.1f}%) | Rychlost: {speed:.1f} it/s", ending="")
                self.stdout.flush()

        self.stdout.write(self.style.SUCCESS(f"\n✅ Vlajky hotovy ({flag_count} záznamů).\n"))
        self.stdout.write(self.style.SUCCESS('🎉 Celý backfill úspěšně dokončen!'))