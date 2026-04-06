from django.core.management.base import BaseCommand
from app.models import FlagCollection, Country

class Command(BaseCommand):
    help = 'Drastická oprava a synchronizace kategorií podle referenčního modelu Country.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🚀 Spouštím drastickou opravu kategorií..."))

        # 1. KROK: Povýšení skutečných států
        # Najdeme všechny vlajky, které jsou fyzicky napojené na tvých ~250 reálných států
        sovereign_flags = FlagCollection.objects.filter(country__isnull=False)
        fixed_countries = 0

        for flag in sovereign_flags:
            # Pokud se jméno vlajky shoduje se jménem připojené země (ochrana proti tomu, 
            # aby se z města v Japonsku nestalo celé Japonsko)
            if flag.name == flag.country.name_common or flag.name == flag.country.name_official:
                if flag.category != 'country':
                    self.stdout.write(f"   ⬆️ Povyšuji: {flag.name} ({flag.category} -> country)")
                    flag.category = 'country'
                    flag.save(update_fields=['category'])
                    fixed_countries += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Opraveno/Povýšeno {fixed_countries} skutečných států."))

        # 2. KROK: Degradace falešných států
        # Najdeme vlajky, které se tváří jako 'country', ale NEMAJÍ vazbu na model Country
        fake_countries = FlagCollection.objects.filter(category='country', country__isnull=True)
        fake_count = fake_countries.count()
        
        if fake_count > 0:
            self.stdout.write(self.style.WARNING(f"⚠️ Nalezeno {fake_count} falešných států (např. AI se spletla)."))
            for fc in fake_countries:
                self.stdout.write(f"   ⬇️ Degraduji: {fc.name} (country -> region)")
            
            # Změníme jim kategorii a odškrtneme is_verified, aby je AI později zkusila zařadit znovu
            fake_countries.update(category='region', is_verified=False)
            self.stdout.write(self.style.SUCCESS(f"✅ Falešné státy degradovány na regiony."))

        # 3. KROK: Shrnutí
        countries_count = FlagCollection.objects.filter(category='country').count()
        dependencies_count = FlagCollection.objects.filter(category='dependency').count()

        self.stdout.write(self.style.NOTICE(f"\n📊 FINÁLNÍ STAV V DATABÁZI:"))
        self.stdout.write(f"   🌍 Countries: {countries_count}")
        self.stdout.write(f"   🏝️ Dependencies: {dependencies_count}")
        
        if dependencies_count > 100:
            self.stdout.write(self.style.WARNING(
                "\n💡 Tip: Počet dependencies je stále dost vysoký. AI pravděpodobně označila "
                "i běžné regiony (např. kraje ve Francii) jako dependencies. "
                "Pro VIP skript to ale tolik nevadí, maximálně dostanou hezký text."
            ))