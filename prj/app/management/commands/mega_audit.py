from django.core.management.base import BaseCommand
from django.db.models import Q
from app.models import FlagCollection, Country
import json

class Command(BaseCommand):
    help = 'Hloubkový forenzní audit konkrétní entity napříč tabulkami.'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='Název hledané entity (např. Afghanistan)')

    def handle(self, *args, **options):
        q = options['query']
        self.stdout.write(self.style.NOTICE(f"\n🔍 SPUŠTĚN FORENZNÍ AUDIT PRO: '{q}'"))
        self.stdout.write("="*60)

        # --- 1. HLEDÁNÍ V TABULCE COUNTRY ---
        countries = Country.objects.filter(
            Q(name_common__icontains=q) | Q(name_official__icontains=q) | Q(cca3__iexact=q)
        )
        
        self.stdout.write(self.style.SUCCESS(f"\n🌍 Tabulka COUNTRY (Nalezeno {countries.count()} záznamů):"))
        for c in countries:
            self.stdout.write(f"   [ID: {c.id}] | ISO: {c.cca3} | Common: {c.name_common}")
            self.stdout.write(f"     - Počet obyvatel (population): {c.population}")
            # Zkusíme detekovat všechna možná pole pro rozlohu
            area_fields = {f.name: getattr(c, f.name) for f in c._meta.fields if 'area' in f.name.lower()}
            self.stdout.write(f"     - Pole s rozlohou: {area_fields}")
            self.stdout.write(f"     - DB Objekt: {c.__dict__}")

        # --- 2. HLEDÁNÍ V TABULCE FLAGCOLLECTION ---
        flags = FlagCollection.objects.filter(Q(name__icontains=q) | Q(name_cs__icontains=q))
        
        self.stdout.write(self.style.SUCCESS(f"\n🏳️ Tabulka FLAGCOLLECTION (Nalezeno {flags.count()} záznamů):"))
        for f in flags:
            parent_info = f"ID: {f.country.id} ({f.country.cca3})" if f.country else "!!! ŽÁDNÁ VAZBA !!!"
            self.stdout.write(f"   [ID: {f.id}] | Name: {f.name} | Category: {f.category}")
            self.stdout.write(f"     - Vazba na Country: {parent_info}")
            self.stdout.write(f"     - Populace v modelu Vlajky: {f.population}")
            self.stdout.write(f"     - Rozloha v modelu Vlajky: {f.area_km2}")
            self.stdout.write(f"     - Ověřeno: {f.is_verified} | Veřejné: {f.is_public}")

        # --- 3. KONTROLA VIEW KONTEXTU ---
        self.stdout.write(self.style.WARNING(f"\n💡 RADY PRO DEBUGGING:"))
        if countries.count() > 1:
            self.stdout.write("   ❌ ERROR: Máš duplicity v tabulce Country! Smaž ten záznam, co nemá ISO kód.")
        
        if countries.count() == 1 and flags.count() > 0:
            c = countries.first()
            f = flags.first()
            if f.country and f.country.id != c.id:
                self.stdout.write(f"   ❌ ERROR: Vlajka '{f.name}' ukazuje na jine ID země ({f.country.id}) než je tvůj hlavní model ({c.id})!")
        
        self.stdout.write("\n" + "="*60 + "\n")