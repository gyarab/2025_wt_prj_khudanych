from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from app.models import Country, FlagCollection

class Command(BaseCommand):
    help = '🔍 Ultimátní Hloubková Telemetrie Databáze (Read-Only)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("\n" + "="*80))
        self.stdout.write(self.style.NOTICE("📊 ULTIMÁTNÍ DIAGNOSTIKA DATABÁZE (JUST ENOUGH FLAGS)"))
        self.stdout.write(self.style.NOTICE("="*80 + "\n"))

        # --- 1. ZÁKLADNÍ ENTITY (COUNTRY) ---
        self.stdout.write(self.style.SUCCESS("🌍 1. TABULKA COUNTRY (Geopolitické entity)"))
        countries = Country.objects.all()
        total_c = countries.count()
        sovereign = countries.filter(status='sovereign').count()
        territories = countries.filter(status='territory').count()
        
        self.stdout.write(f"   Celkem entit v tabulce: {total_c}")
        self.stdout.write(f"   - Suverénní státy: {sovereign}")
        self.stdout.write(f"   - Závislá území: {territories}")

        # Kvalita dat v Country
        pop_filled = countries.filter(population__gt=0).count()
        area_filled = countries.filter(area_km2__isnull=False).count()
        gov_filled = countries.filter(system_of_government__isnull=False).exclude(system_of_government="").count()
        
        self.stdout.write(self.style.WARNING("\n   [Kvalita dat v Country]"))
        self.stdout.write(f"   - Vyplněná populace: {pop_filled}/{total_c}")
        self.stdout.write(f"   - Vyplněná rozloha: {area_filled}/{total_c}")
        self.stdout.write(f"   - Vyplněný systém vlády: {gov_filled}/{sovereign} (počítáno jen pro státy)")
        self.stdout.write("-" * 80)

        # --- 2. VLAJKY A TEXTY (FLAG COLLECTION) ---
        self.stdout.write(self.style.SUCCESS("\n🏳️ 2. TABULKA FLAGCOLLECTION (Vlajky a encyklopedie)"))
        flags = FlagCollection.objects.all()
        total_f = flags.count()
        public_f = flags.filter(is_public=True).count()
        
        self.stdout.write(f"   Celkem záznamů: {total_f} (Z toho veřejných: {public_f})")
        
        self.stdout.write(self.style.WARNING("\n   [Rozpad podle kategorií (Všechny / Veřejné)]"))
        categories = flags.values('category').annotate(total=Count('id')).order_by('-total')
        for cat in categories:
            cat_name = cat['category']
            total_cat = cat['total']
            public_cat = flags.filter(category=cat_name, is_public=True).count()
            self.stdout.write(f"   - {cat_name:<15}: {total_cat:<6} / {public_cat:<6} veřejných")
        self.stdout.write("-" * 80)

        # --- 3. PROPOJENÍ A SIROTCI ---
        self.stdout.write(self.style.SUCCESS("\n🔗 3. INTEGRITA A PROPOJENÍ (Relace)"))
        
        # Kolik hlavních vlajek (country/dependency) nemá vazbu na tabulku Country?
        orphans = flags.filter(category__in=['country', 'dependency'], country__isnull=True, is_public=True).count()
        linked = flags.filter(category__in=['country', 'dependency'], country__isnull=False, is_public=True).count()
        
        self.stdout.write(f"   Propojené veřejné státy/teritoria s tabulkou Country: {linked}")
        if orphans > 0:
            self.stdout.write(self.style.ERROR(f"   ⚠️ KRITICKÁ CHYBA: Veřejní sirotci (country/dependency bez vazby): {orphans}"))
        else:
            self.stdout.write(f"   Sirotci u států a teritorií: 0 (Perfektní stav!)")
        self.stdout.write("-" * 80)

        # --- 4. VIP AI SKRIPT STATUS ---
        self.stdout.write(self.style.SUCCESS("\n🤖 4. STAV AI ZPRACOVÁNÍ (Fronta pro VIP Skript)"))
        
        # Zajímají nás jen entity, které reálně máme a které mají nějakou vlajku
        target_countries = Country.objects.filter(status__in=['sovereign', 'territory'], additional_flags__isnull=False).distinct()
        total_targets = target_countries.count()
        
        # Kolik z nich už má "is_verified=True" u své hlavní vlajky?
        verified_targets = target_countries.filter(additional_flags__is_verified=True).distinct().count()
        pending_targets = total_targets - verified_targets
        
        self.stdout.write(f"   Celkem entit pro AI zpracování: {total_targets}")
        self.stdout.write(self.style.WARNING(f"   - Čeká na AI zpracování (is_verified=False): {pending_targets}"))
        self.stdout.write(self.style.SUCCESS(f"   - Už je hotovo (is_verified=True): {verified_targets}"))
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.NOTICE("✅ TELEMETRIE DOKONČENA. Zkopíruj tento výpis a pošli ho ke kontrole."))
        self.stdout.write("="*80 + "\n")