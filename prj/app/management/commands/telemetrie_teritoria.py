from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from app.models import Country, FlagCollection # Přidán import FlagCollection

class Command(BaseCommand):
    help = 'Vyhodí macatou telemetrii o Závislých územích a propojení s vlajkami.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('\n=== 🌍 TELEMETRIE: ZÁVISLÁ ÚZEMÍ A VLAJKY ===\n'))

        # --- SEKCE 1: TABULKA COUNTRY ---
        territories = Country.objects.filter(Q(independent=False) | Q(owner__isnull=False))
        stats = territories.aggregate(
            total=Count('id'),
            has_capital=Count('id', filter=Q(capital__isnull=False) & ~Q(capital='')),
            has_parent=Count('id', filter=Q(owner__isnull=False)),
            has_map_data=Count('id', filter=Q(latitude__isnull=False) & Q(longitude__isnull=False))
        )

        self.stdout.write(self.style.WARNING('📊 TABULKA COUNTRY (Fyzická území):'))
        self.stdout.write(f"  Celkem teritorií:         {stats['total']}")
        self.stdout.write(f"  Má nastavené hl. město:   {stats['has_capital']}")
        self.stdout.write('-' * 40)

        # --- SEKCE 2: TABULKA FLAG COLLECTION (Záhada 75 vlajek) ---
        # Tady použij přesný název kategorie, který máš v DB (předpokládám 'dependency' nebo 'Dependencies')
        # Uprav string, pokud to v DB máš s velkým písmenem!
        flags_dependency = FlagCollection.objects.filter(category__icontains='dependency')
        flags_total = flags_dependency.count()
        
        # Hledáme "Sirotky" - vlajky bez propojeného území
        orphans = flags_dependency.filter(country__isnull=True)
        orphans_count = orphans.count()

        self.stdout.write(self.style.WARNING('\n📊 TABULKA FLAG COLLECTION (Galerie na webu):'))
        self.stdout.write(f"  Vlajek v kategorii Dependency: {flags_total}")
        self.stdout.write(f"  Vlajek BEZ propojení na Country (Sirotci): {orphans_count}")
        
        if orphans_count > 0:
            self.stdout.write(self.style.ERROR('\n🐛 LOV BUGŮ 3: TYTO VLAJKY TĚ PŘI KLIKNUTÍ PŘESMĚRUJÍ (Chybí propojení)'))
            for flag in orphans[:100]:  # Ukážeme prvních 100 sirotků
                self.stdout.write(f"  - ID vlajky: {flag.id} | Jméno: {flag.name}")

        self.stdout.write(self.style.SUCCESS('\n=== KONEC TELEMETRIE ===\n'))