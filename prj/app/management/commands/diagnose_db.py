from django.core.management.base import BaseCommand
from django.db.models import Count, Q
import re
from app.models import FlagCollection, Country

class Command(BaseCommand):
    help = 'Hloubková diagnostika a telemetrie databáze (Read-Only).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("\n" + "="*50))
        self.stdout.write(self.style.NOTICE("🚀 SPOUŠTÍM KOMPLEXNÍ DIAGNOSTIKU DATABÁZE"))
        self.stdout.write(self.style.NOTICE("="*50 + "\n"))

        # --- 1. ZÁKLADNÍ TABULKA: COUNTRY ---
        total_countries = Country.objects.count()
        un_members = Country.objects.filter(un_member=True).count()
        self.stdout.write(self.style.SUCCESS(f"🌍 TABULKA 'Country' (Základní státy):"))
        self.stdout.write(f"   Celkem záznamů: {total_countries}")
        self.stdout.write(f"   Z toho UN members: {un_members}")
        self.stdout.write("-" * 40)

        # --- 2. HLAVNÍ TABULKA: FLAG COLLECTION ---
        total_flags = FlagCollection.objects.count()
        public_flags = FlagCollection.objects.filter(is_public=True).count()
        verified_flags = FlagCollection.objects.filter(is_verified=True).count()
        
        self.stdout.write(self.style.SUCCESS(f"\n🏳️ TABULKA 'FlagCollection' (Vlajky):"))
        self.stdout.write(f"   Celkem vlajek: {total_flags}")
        self.stdout.write(f"   Veřejné (is_public=True): {public_flags} (Tohle by měl vidět web)")
        self.stdout.write(f"   Ověřené AI (is_verified=True): {verified_flags}")
        self.stdout.write(f"   Čeká na kontrolu (is_verified=False): {total_flags - verified_flags}")
        self.stdout.write("-" * 40)

        # --- 3. ROZPAD PODLE KATEGORIÍ ---
        self.stdout.write(self.style.SUCCESS(f"\n📊 ROZPAD KATEGORIÍ (Všechny / Veřejné):"))
        categories = FlagCollection.objects.values('category').annotate(total=Count('id')).order_by('-total')
        for cat in categories:
            cat_name = cat['category']
            total_cat = cat['total']
            public_cat = FlagCollection.objects.filter(category=cat_name, is_public=True).count()
            cat_label = cat_name if cat_name else "BEZ KATEGORIE (NULL)"
            self.stdout.write(f"   - {cat_label:<20} {total_cat:<6} / {public_cat:<6} public")
        self.stdout.write("-" * 40)

        # --- 4. KONTROLA INTEGRITY (Chyby a anomálie) ---
        self.stdout.write(self.style.WARNING(f"\n⚠️ KONTROLA INTEGRITY A CHYB:"))
        
        # Státy bez vazby
        orphaned_countries = FlagCollection.objects.filter(category='country', country__isnull=True).count()
        self.stdout.write(f"   Falešné státy bez vazby na tabulku Country: {orphaned_countries}")

        # Vlajky úplně bez vazby na zemi (nemusí být nutně chyba u junk/international)
        orphans_total = FlagCollection.objects.filter(country__isnull=True).count()
        self.stdout.write(f"   Položky absolutně bez vazby na jakoukoliv zemi: {orphans_total}")

        # Q-Nodes check (Regex)
        # Protože SQLite nemusí mít nativní Regex podporu přes ORM stejnou jako PostgreSQL, uděláme to bezpečně:
        q_count = 0
        unicode_err_count = 0
        missing_cs_name = 0
        
        # Iterujeme po větších dávkách pro šetření paměti
        for f in FlagCollection.objects.all().iterator(chunk_size=2000):
            # Kontrola Q-Node
            if f.name and re.match(r'^Q\d+$', f.name):
                q_count += 1
            # Kontrola rozbité diakritiky (\u)
            if (f.name_cs and '\\u' in f.name_cs) or (f.name_de and '\\u' in f.name_de):
                unicode_err_count += 1
            # Kontrola chybějícího českého názvu
            if not f.name_cs:
                missing_cs_name += 1

        self.stdout.write(f"   Zbývající Q-Nodes v poli 'name': {q_count}")
        self.stdout.write(f"   Rozbitá diakritika (\\u kódy v name_cs/de): {unicode_err_count}")
        self.stdout.write(f"   Chybějící český název (name_cs je prázdné): {missing_cs_name}")
        self.stdout.write("-" * 40)

        # --- 5. VIP FRONTA ---
        self.stdout.write(self.style.NOTICE(f"\n💎 PŘIPRAVENOST PRO VIP SKRIPT:"))
        vip_queue = FlagCollection.objects.filter(category__in=['country', 'dependency'], is_verified=False).count()
        vip_done = FlagCollection.objects.filter(category__in=['country', 'dependency'], is_verified=True).count()
        
        self.stdout.write(f"   Čeká na VIP zpracování: {vip_queue}")
        self.stdout.write(f"   Již hotovo VIP agentem: {vip_done}")
        
        self.stdout.write(self.style.NOTICE("\n" + "="*50))
        self.stdout.write(self.style.NOTICE("✅ DIAGNOSTIKA DOKONČENA"))
        self.stdout.write(self.style.NOTICE("="*50 + "\n"))