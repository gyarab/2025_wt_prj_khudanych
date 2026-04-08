from django.core.management.base import BaseCommand
from django.db.models import Count
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = '🔍 Hloubková telemetrie a analýza závislých území (Dependencies) a duplicit.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("\n" + "="*70))
        self.stdout.write(self.style.NOTICE("🌍 DIAGNOSTIKA ZÁVISLÝCH ÚZEMÍ A DUPLICIT"))
        self.stdout.write(self.style.NOTICE("="*70 + "\n"))

        # --- 1. POHLED TABULKY COUNTRY ---
        country_territories = Country.objects.filter(status='territory')
        self.stdout.write(self.style.SUCCESS("📊 1. TABULKA COUNTRY (Oficiální ISO území)"))
        self.stdout.write(f"   Celkem území (status='territory'): {country_territories.count()}")
        
        has_owner = country_territories.filter(owner__isnull=False).count()
        self.stdout.write(f"   Z toho má nastaveného 'owner' stát: {has_owner}")
        self.stdout.write("-" * 70)

        # --- 2. POHLED TABULKY FLAGCOLLECTION ---
        flag_deps = FlagCollection.objects.filter(category='dependency')
        self.stdout.write(self.style.SUCCESS("\n🏳️ 2. TABULKA FLAGCOLLECTION (Vlajky Wikidat)"))
        self.stdout.write(f"   Celkem vlajek (category='dependency'): {flag_deps.count()}")
        
        linked = flag_deps.filter(country__isnull=False).count()
        orphaned = flag_deps.filter(country__isnull=True)
        
        self.stdout.write(f"   Propojeno s tabulkou Country: {linked}")
        self.stdout.write(self.style.WARNING(f"   Sirotci (bez vazby na Country): {orphaned.count()}"))
        self.stdout.write("-" * 70)

        # --- 3. SEZNAM NEJHORŠÍCH SIROTKŮ ---
        if orphaned.exists():
            self.stdout.write(self.style.WARNING("\n🕵️‍♂️ 3. UKÁZKA SIROTKŮ (Prvních 100 nezapojených vlajek):"))
            for orphan in orphaned[:100]:
                self.stdout.write(f"   - {orphan.name} (ID: {orphan.id})")
        self.stdout.write("-" * 70)

        # --- 4. HLEDÁNÍ DUPLICIT VE VLAJKÁCH ---
        self.stdout.write(self.style.ERROR("\n👯‍♀️ 4. PODEZŘENÍ NA DUPLICITY (Stejný název v kategorii 'dependency')"))
        
        duplicates = (
            FlagCollection.objects.filter(category='dependency')
            .values('name')
            .annotate(name_count=Count('name'))
            .filter(name_count__gt=1)
            .order_by('-name_count')
        )

        if duplicates:
            for dup in duplicates:
                self.stdout.write(self.style.WARNING(f"   ⚠️ '{dup['name']}' se v databázi nachází {dup['name_count']}x!"))
                # Vypíšeme detaily duplicit
                dup_flags = FlagCollection.objects.filter(category='dependency', name=dup['name'])
                for f in dup_flags:
                    vazba = f"-> Vázáno na: {f.country.name_common}" if f.country else "-> BEZ VAZBY (Sirotek)"
                    self.stdout.write(f"      ID {f.id}: {f.name_cs} | Public: {f.is_public} | {vazba}")
        else:
            self.stdout.write(self.style.SUCCESS("   Nenalezeny žádné zjevné duplicity podle přesného anglického názvu."))

        self.stdout.write(self.style.NOTICE("\n" + "="*70 + "\n"))